#!/usr/bin/env python3
"""Audit raw four-way renders within +/-12 st; never infer audible artifacts.

Envelope/onset values come from the supplied evaluator CSVs. Amplitude and
sample/channel metadata are measured again from the unnormalized WAVs.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from pathlib import Path

import numpy as np

if __package__:
    from . import make_blind_multires_pack as blind
else:
    import make_blind_multires_pack as blind

TARGET_LIMIT = 12.0001  # Same boundary tolerance as the blind-pack selector.
CATEGORIES = ("voice", "solo", "polyphonic", "mix")
REQUESTED_PITCHES = (-12, -7, -3, 3, 7, 12)
FIELDS = (
    "stem", "category", "percent", "semitones", "system", "sample_rate",
    "channels", "frames", "duration_error_frames", "peak", "peak_dbfs", "rms",
    "rms_dbfs", "crest_db", "peak_ratio_vs_reference", "peak_ratio_vs_transient",
    "rms_delta_vs_reference_db", "rms_delta_vs_transient_db",
    "crest_delta_vs_transient_db", "peak_time_seconds", "peak_channel",
    "env_rmse_db", "onset_corr", "review_flags", "artifact_assessment",
    "listening_notes", "audio_path", "audio_sha256",
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def ratio(numerator: float, denominator: float) -> float | None:
    return numerator / denominator if denominator > 0.0 else None


def db(value: float | None) -> float | None:
    return 20.0 * math.log10(value) if value is not None and value > 0.0 else None


def amplitude(audio: np.ndarray, sample_rate: int) -> dict[str, float | int | None]:
    absolute = np.abs(audio)
    peak = float(np.max(absolute))
    rms = float(np.sqrt(np.mean(np.square(audio, dtype=np.float64))))
    index = int(np.argmax(absolute))
    channels = audio.shape[1]
    return dict(peak=peak, peak_dbfs=db(peak), rms=rms, rms_dbfs=db(rms),
                crest_db=db(ratio(peak, rms)), peak_time_seconds=(index // channels) / sample_rate,
                peak_channel=index % channels)


def write_csv(path: Path, rows: list[dict], fields: tuple[str, ...]) -> None:
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def build_report(args: argparse.Namespace) -> tuple[list[dict], list[dict], dict]:
    for value in (args.peak_threshold, args.peak_ratio_threshold):
        if not math.isfinite(value) or value <= 0.0:
            raise ValueError("review thresholds must be finite and positive")
    inputs = {name: blind.load_rows(getattr(args, f"{name}_metrics"))
              for name in ("general", "transient", "multires")}
    # No per-category truncation: audit every complete target-range condition.
    selected = blind.select_conditions(inputs["general"], inputs["transient"],
                                       inputs["multires"], max(1, len(inputs["general"])))
    maps = {
        "derived_elastique": blind.standard_map(inputs["general"], "elastique"),
        "general_harmonic": blind.standard_map(inputs["general"], "harmonic"),
        "transient_harmonic": blind.standard_map(inputs["transient"], "harmonic"),
        "multires_harmonic": blind.multires_map(inputs["multires"]),
    }
    excluded = [{field: row[field] for field in ("stem", "category", "percent", "semitones")}
                for row in maps["general_harmonic"].values()
                if abs(float(row["semitones"])) > TARGET_LIMIT]
    rows: list[dict] = []
    references: list[dict] = []
    for condition in sorted(selected, key=lambda row: (str(row["stem"]), float(row["semitones"]))):
        key = blind.condition_key(str(condition["stem"]), str(condition["percent"]))
        reference_path, system_paths = blind.trial_paths(args, condition)
        reference, systems, sample_rate = blind.load_trial(reference_path, system_paths)
        ref_stats = amplitude(reference, sample_rate)
        stats = {name: amplitude(audio, sample_rate) for name, audio in systems.items()}
        transient = stats["transient_harmonic"]
        references.append(dict(stem=condition["stem"], percent=condition["percent"],
                               path=str(reference_path.resolve()), sha256=sha256(reference_path)))
        for name, audio in systems.items():
            current = stats[name]
            peak_ratio = ratio(current["peak"], transient["peak"])
            crest_delta = (current["crest_db"] - transient["crest_db"]
                           if current["crest_db"] is not None and transient["crest_db"] is not None else None)
            flags = []
            if current["peak"] > args.peak_threshold:
                flags.append("peak_above_review_threshold")
            if peak_ratio is not None and peak_ratio > args.peak_ratio_threshold:
                flags.append("peak_ratio_vs_transient_above_review_threshold")
            if transient["peak"] == 0.0 and current["peak"] > 0.0:
                flags.append("nonzero_output_vs_silent_transient")
            if ref_stats["peak"] == 0.0 and current["peak"] > 0.0:
                flags.append("nonzero_output_vs_silent_reference")
            metric = maps[name][key]
            env_key, onset_key = ("env", "onset") if name == "multires_harmonic" else ("env_rmse_db", "onset_corr")
            rows.append({
                **{field: condition[field] for field in ("stem", "category", "percent", "semitones")},
                "system": name, "sample_rate": sample_rate, "channels": audio.shape[1],
                "frames": len(audio), "duration_error_frames": len(audio) - len(reference),
                **current,
                "peak_ratio_vs_reference": ratio(current["peak"], ref_stats["peak"]),
                "peak_ratio_vs_transient": peak_ratio,
                "rms_delta_vs_reference_db": db(ratio(current["rms"], ref_stats["rms"])),
                "rms_delta_vs_transient_db": db(ratio(current["rms"], transient["rms"])),
                "crest_delta_vs_transient_db": crest_delta,
                "env_rmse_db": float(metric[env_key]), "onset_corr": float(metric[onset_key]),
                "review_flags": ";".join(flags), "artifact_assessment": "not_listened",
                "listening_notes": "", "audio_path": str(system_paths[name].resolve()),
                "audio_sha256": sha256(system_paths[name]),
            })
    coverage = {}
    for category in sorted(set(CATEGORIES) | {str(row["category"]) for row in selected}):
        pitches = sorted(float(row["semitones"]) for row in selected if row["category"] == category)
        coverage[category] = dict(conditions=len(pitches), actual_semitones=pitches,
                                 missing_requested_semitones=[pitch for pitch in REQUESTED_PITCHES
                                     if not any(abs(actual - pitch) <= 0.0001 for actual in pitches)])
    summary = {
        "schema_version": 1, "target_limit_st": 12.0, "boundary_tolerance_st": 0.0001,
        "conditions": len(selected), "system_rows": len(rows),
        "excluded_stress_conditions": len(excluded),
        "flagged_rows": sum(bool(row["review_flags"]) for row in rows),
        "peak_review_threshold": args.peak_threshold,
        "peak_ratio_vs_transient_review_threshold": args.peak_ratio_threshold,
        "coverage_tolerance_st": 0.0001, "coverage": coverage,
        "metric_inputs": {name: dict(path=str(getattr(args, f"{name}_metrics").resolve()),
                                    sha256=sha256(getattr(args, f"{name}_metrics"))) for name in inputs},
        "references": references,
        "notes": [
            "Investigator report, not a blind listener manifest or a promotion gate.",
            "Amplitude measured on raw WAVs before RMS matching, attenuation or limiting.",
            "Envelope/onset copied from supplied CSVs; not recomputed by this tool.",
            "Derived Elastique is TSM plus offline resampling, not native pitch-shifter output.",
            "Peak increases and samples above 1.0 do not by themselves prove an audible artifact.",
            "Undefined ratios and silence dB values are null in JSON / blank in CSV, not floored.",
            "Excluded stress rows are metadata only; their audio is not evaluated here.",
        ],
    }
    return rows, excluded, summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("general", "transient", "multires"):
        parser.add_argument(f"--{name}-metrics", type=Path, required=True)
        parser.add_argument(f"--{name}-renders", type=Path, required=True)
    parser.add_argument("--ref-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--peak-threshold", type=float, default=1.0, help="review flag, not a quality gate")
    parser.add_argument("--peak-ratio-threshold", type=float, default=1.10, help="ratio vs Transient; review only")
    args = parser.parse_args()
    if args.output.exists() and (not args.output.is_dir() or any(args.output.iterdir())):
        parser.error("output must be absent or empty")
    try:
        rows, excluded, summary = build_report(args)
    except (ValueError, KeyError, OSError) as error:
        parser.error(str(error))
    outliers = sorted((row for row in rows if row["review_flags"]), key=lambda row: (
        -(row["peak_ratio_vs_transient"] if row["peak_ratio_vs_transient"] is not None else math.inf),
        -row["peak"], row["stem"], row["semitones"], row["system"]))
    args.output.mkdir(parents=True, exist_ok=True)
    write_csv(args.output / "all_conditions.csv", rows, FIELDS)
    write_csv(args.output / "peak_outliers.csv", outliers, FIELDS)
    write_csv(args.output / "excluded_stress.csv", excluded, ("stem", "category", "percent", "semitones"))
    (args.output / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
    print(f"audited {summary['conditions']} conditions / {len(rows)} renders; {len(outliers)} review flags; "
          f"{len(excluded)} stress conditions excluded")


if __name__ == "__main__":
    main()
