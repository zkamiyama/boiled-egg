#!/usr/bin/env python3
"""Evaluate a two-resolution pitch-shift blend from existing render trees.

The low branch is normally the validated Transient profile (1024/256) and the
high branch is the 512/64 research diagnostic. A complementary linear-phase FIR
keeps the low branch below the crossover and replaces only the high-frequency
content with the shorter-window branch.

Third-party/reference audio stays outside the repository. This tool consumes
render directories produced by eval_elastique_pitch.py and writes only local
research outputs/results.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
from collections import defaultdict
from pathlib import Path

import numpy as np
import soundfile as sf
from scipy import signal

from eval_elastique_pitch import metrics


def load_audio(path: Path) -> tuple[np.ndarray, int]:
    audio, sample_rate = sf.read(path, always_2d=True, dtype="float32")
    return audio.astype(np.float64), sample_rate


def complementary_fir(sample_rate: int, crossover_hz: float, taps: int) -> tuple[np.ndarray, np.ndarray]:
    if taps < 3 or taps % 2 == 0:
        raise ValueError("FIR tap count must be odd and >= 3")
    if not 20.0 < crossover_hz < sample_rate * 0.45:
        raise ValueError("crossover is outside the supported range")
    lowpass = signal.firwin(taps, crossover_hz, fs=sample_rate, window=("kaiser", 8.0))
    highpass = -lowpass.copy()
    highpass[taps // 2] += 1.0
    return lowpass, highpass


def blend(low: np.ndarray, high: np.ndarray, lowpass: np.ndarray, highpass: np.ndarray) -> np.ndarray:
    if low.shape != high.shape:
        raise ValueError("branch shape mismatch")
    output = np.empty_like(low, dtype=np.float64)
    for channel in range(low.shape[1]):
        output[:, channel] = (
            signal.oaconvolve(low[:, channel], lowpass, mode="same")
            + signal.oaconvolve(high[:, channel], highpass, mode="same")
        )
    return output.astype(np.float32)


def rms(audio: np.ndarray) -> float:
    return float(np.sqrt(np.mean(np.asarray(audio, dtype=np.float64) ** 2) + 1.0e-30))


def locate_condition(root: Path, stem: str, percent: str) -> Path:
    exact = root / "renders" / stem / f"{percent}_per"
    if exact.exists():
        return exact
    candidates = list((root / "renders" / stem).glob("*_per"))
    if not candidates:
        raise FileNotFoundError(f"no render condition for {stem} / {percent}")
    return min(candidates, key=lambda path: abs(float(path.name[:-4]) - float(percent)))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--low-root", type=Path, required=True, help="eval_elastique_pitch output for the low/full-band branch")
    parser.add_argument("--high-root", type=Path, required=True, help="eval_elastique_pitch output for the short-window high branch")
    parser.add_argument("--ref-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--system", choices=("harmonic", "monophonic", "off"), default="harmonic")
    parser.add_argument("--crossover", type=float, default=6000.0)
    parser.add_argument("--taps", type=int, default=129)
    parser.add_argument("--write-renders", action="store_true")
    args = parser.parse_args()

    args.output.mkdir(parents=True, exist_ok=True)
    low_rows = [
        row for row in csv.DictReader((args.low_root / "metrics.csv").open(encoding="utf-8"))
        if row["system"] == args.system
    ]
    if not low_rows:
        raise SystemExit("no matching low-branch metric rows")

    coefficient_cache: dict[int, tuple[np.ndarray, np.ndarray]] = {}
    rows: list[dict[str, object]] = []

    for index, row in enumerate(low_rows, 1):
        stem = row["stem"]
        percent = row["percent"]
        reference, sample_rate = load_audio(args.ref_dir / f"{stem}.wav")
        low_dir = locate_condition(args.low_root, stem, percent)
        high_dir = locate_condition(args.high_root, stem, percent)
        low, low_rate = load_audio(low_dir / f"boiled_{args.system}.wav")
        high, high_rate = load_audio(high_dir / f"boiled_{args.system}.wav")
        derived_elastique, elastique_rate = load_audio(low_dir / "elastique.wav")
        if sample_rate != low_rate or sample_rate != high_rate or sample_rate != elastique_rate:
            raise SystemExit(f"sample-rate mismatch for {stem} / {percent}")
        if low.shape != high.shape or low.shape != reference.shape or derived_elastique.shape != reference.shape:
            raise SystemExit(f"duration/channel mismatch for {stem} / {percent}")

        filters = coefficient_cache.get(sample_rate)
        if filters is None:
            filters = complementary_fir(sample_rate, args.crossover, args.taps)
            coefficient_cache[sample_rate] = filters
        hybrid = blend(low, high, *filters)

        hybrid_env, hybrid_onset, hybrid_rms, hybrid_peak = metrics(reference, hybrid, sample_rate)
        low_env, low_onset, low_rms, low_peak = metrics(reference, low, sample_rate)
        elastique_env, elastique_onset, _, _ = metrics(reference, derived_elastique, sample_rate)

        result = {
            "stem": stem,
            "category": row["category"],
            "percent": percent,
            "semitones": float(row["semitones"]),
            "crossover_hz": args.crossover,
            "fir_taps": args.taps,
            "env_rmse_db": hybrid_env,
            "onset_corr": hybrid_onset,
            "env_delta_vs_elastique_db": hybrid_env - elastique_env,
            "onset_delta_vs_elastique": hybrid_onset - elastique_onset,
            "env_delta_vs_low_db": hybrid_env - low_env,
            "onset_delta_vs_low": hybrid_onset - low_onset,
            "rms_delta_vs_low_db": 20.0 * math.log10(hybrid_rms / max(low_rms, 1.0e-30)),
            "peak_ratio_vs_low": hybrid_peak / max(low_peak, 1.0e-30),
            "duration_error_frames": len(hybrid) - len(reference),
        }
        rows.append(result)

        if args.write_renders:
            destination = args.output / "renders" / stem / f"{percent}_per"
            destination.mkdir(parents=True, exist_ok=True)
            sf.write(destination / "boiled_multires.wav", hybrid, sample_rate, subtype="FLOAT")

        if index % 10 == 0:
            print(f"condition {index}/{len(low_rows)}", flush=True)

    fields = list(rows[0])
    with (args.output / "metrics.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)

    by_category: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in rows:
        by_category[str(row["category"])].append(row)

    def mean(field: str, subset: list[dict[str, object]] = rows) -> float:
        return float(np.mean([float(row[field]) for row in subset]))

    summary = {
        "conditions": len(rows),
        "system": args.system,
        "crossover_hz": args.crossover,
        "fir_taps": args.taps,
        "mean_env_delta_vs_elastique_db": mean("env_delta_vs_elastique_db"),
        "env_wins_vs_elastique": sum(float(row["env_delta_vs_elastique_db"]) < 0.0 for row in rows),
        "mean_onset_delta_vs_elastique": mean("onset_delta_vs_elastique"),
        "onset_wins_vs_elastique": sum(float(row["onset_delta_vs_elastique"]) > 0.0 for row in rows),
        "mean_env_delta_vs_low_db": mean("env_delta_vs_low_db"),
        "worst_env_delta_vs_low_db": max(float(row["env_delta_vs_low_db"]) for row in rows),
        "mean_onset_delta_vs_low": mean("onset_delta_vs_low"),
        "onset_wins_vs_low": sum(float(row["onset_delta_vs_low"]) > 0.0 for row in rows),
        "mean_rms_delta_vs_low_db": mean("rms_delta_vs_low_db"),
        "p95_abs_rms_delta_vs_low_db": float(np.percentile(np.abs([float(row["rms_delta_vs_low_db"]) for row in rows]), 95)),
        "p95_peak_ratio_vs_low": float(np.percentile([float(row["peak_ratio_vs_low"]) for row in rows], 95)),
        "max_peak_ratio_vs_low": max(float(row["peak_ratio_vs_low"]) for row in rows),
        "max_duration_error_frames": max(abs(int(row["duration_error_frames"])) for row in rows),
        "by_category": {
            category: {
                "cases": len(subset),
                "mean_env_delta_vs_elastique_db": mean("env_delta_vs_elastique_db", subset),
                "mean_onset_delta_vs_elastique": mean("onset_delta_vs_elastique", subset),
                "mean_env_delta_vs_low_db": mean("env_delta_vs_low_db", subset),
                "mean_onset_delta_vs_low": mean("onset_delta_vs_low", subset),
            }
            for category, subset in sorted(by_category.items())
        },
    }
    (args.output / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
