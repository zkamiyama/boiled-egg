#!/usr/bin/env python3
"""Create an attack-sensitive blind comparison of General and Transient profiles."""
from __future__ import annotations

import argparse
import csv
import html
import math
import random
from collections import defaultdict
from pathlib import Path

import numpy as np
import soundfile as sf


def load_rows(path: Path) -> list[dict[str, str]]:
    return list(csv.DictReader(path.open(encoding="utf-8")))


def load_audio(path: Path) -> tuple[np.ndarray, int]:
    audio, sample_rate = sf.read(path, always_2d=True, dtype="float32")
    return audio.astype(np.float64), sample_rate


def rms(audio: np.ndarray) -> float:
    return math.sqrt(float(np.mean(audio * audio)) + 1.0e-30)


def level_match(reference: np.ndarray, systems: dict[str, np.ndarray]) -> tuple[np.ndarray, dict[str, np.ndarray]]:
    reference_rms = rms(reference)
    limit = 10.0 ** (6.0 / 20.0)
    matched: dict[str, np.ndarray] = {}
    for name, audio in systems.items():
        gain = float(np.clip(reference_rms / max(rms(audio), 1.0e-30), 1.0 / limit, limit))
        matched[name] = audio * gain
    max_peak = max(
        float(np.max(np.abs(reference))),
        *(float(np.max(np.abs(audio))) for audio in matched.values()),
    )
    common = min(1.0, 0.95 / max(max_peak, 1.0e-30))
    return reference * common, {name: audio * common for name, audio in matched.items()}


def select_attack_sensitive(
    general_rows: list[dict[str, str]],
    transient_rows: list[dict[str, str]],
    per_category: int,
) -> list[dict[str, object]]:
    general = {
        (row["stem"], row["percent"]): row
        for row in general_rows
        if row["system"] == "harmonic"
    }
    transient = {
        (row["stem"], row["percent"]): row
        for row in transient_rows
        if row["system"] == "harmonic"
    }
    groups: dict[str, list[dict[str, object]]] = defaultdict(list)
    for key, row in general.items():
        candidate = transient.get(key)
        if candidate is None:
            continue
        item: dict[str, object] = dict(row)
        item["transient_onset_gain"] = float(candidate["onset_corr"]) - float(row["onset_corr"])
        item["transient_env_delta_db"] = float(candidate["env_rmse_db"]) - float(row["env_rmse_db"])
        groups[row["category"]].append(item)

    selected: list[dict[str, object]] = []
    for category in sorted(groups):
        ranked = sorted(groups[category], key=lambda row: float(row["transient_onset_gain"]), reverse=True)
        selected.extend(ranked[:per_category])
    return selected


def source_dir(root: Path, stem: str, percent: str) -> Path:
    exact = root / stem / f"{percent}_per"
    if exact.exists():
        return exact
    candidates = list((root / stem).glob("*_per"))
    if not candidates:
        raise FileNotFoundError(f"no render directory for {stem} / {percent}")
    return min(candidates, key=lambda path: abs(float(path.name[:-4]) - float(percent)))


def write_html(path: Path, rows: list[dict[str, object]], labels: tuple[str, ...]) -> None:
    sections = []
    for row in rows:
        trial = int(row["trial"])
        options = "".join(
            f'<div><b>{label}</b> <audio controls preload="none" src="{html.escape(str(row[label]))}"></audio> '
            f'<label><input type="radio" name="overall-{trial}" value="{label}"> Overall best</label> '
            f'<label><input type="radio" name="attack-{trial}" value="{label}"> Attack/clarity best</label></div>'
            for label in labels
        )
        sections.append(
            f'<section><h3>Trial {trial} — {html.escape(str(row["category"]))} — '
            f'{float(row["semitones"]):+.2f} st</h3>'
            f'<div><b>Reference</b> <audio controls preload="none" src="{html.escape(str(row["reference"]))}"></audio></div>'
            f'{options}</section>'
        )

    document = '''<!doctype html><meta charset="utf-8"><title>boiled egg General vs Transient blind test</title>
<style>body{font-family:sans-serif;max-width:1050px;margin:2rem auto;padding:0 1rem}section{border-top:1px solid #aaa;padding:1rem 0}audio{width:420px;vertical-align:middle;margin:.3rem 1rem}.toolbar{position:sticky;top:0;background:#fff;padding:.6rem}</style>
<h1>boiled egg General vs Transient blind test</h1>
<p>A-C are anonymized. Compare each against Reference. Choose an Overall best and an Attack/clarity best. Open answer_key.csv only after finishing.</p>
<div class="toolbar"><button onclick="save()">Export choices.csv</button></div>''' + "".join(sections) + '''<script>
function save(){let lines=['trial,overall,attack'];document.querySelectorAll('section').forEach((s,i)=>{let o=s.querySelector('input[name^="overall-"]:checked'),a=s.querySelector('input[name^="attack-"]:checked');lines.push((i+1)+','+(o?o.value:'')+','+(a?a.value:''));});let b=new Blob([lines.join('\\n')+'\\n'],{type:'text/csv'}),a=document.createElement('a');a.href=URL.createObjectURL(b);a.download='choices.csv';a.click();}
</script>'''
    path.write_text(document, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--general-metrics", type=Path, required=True)
    parser.add_argument("--general-renders", type=Path, required=True)
    parser.add_argument("--transient-metrics", type=Path, required=True)
    parser.add_argument("--transient-renders", type=Path, required=True)
    parser.add_argument("--ref-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--per-category", type=int, default=6)
    parser.add_argument("--seed", type=int, default=20260830)
    args = parser.parse_args()

    selected = select_attack_sensitive(
        load_rows(args.general_metrics),
        load_rows(args.transient_metrics),
        args.per_category,
    )
    rng = random.Random(args.seed)
    rng.shuffle(selected)
    args.output.mkdir(parents=True, exist_ok=True)

    labels = ("A", "B", "C")
    manifest: list[dict[str, object]] = []
    answer_key: list[dict[str, object]] = []

    for trial, condition in enumerate(selected, 1):
        stem = str(condition["stem"])
        percent = str(condition["percent"])
        general_dir = source_dir(args.general_renders, stem, percent)
        transient_dir = source_dir(args.transient_renders, stem, percent)
        reference, sample_rate = load_audio(args.ref_dir / f"{stem}.wav")
        systems = {
            "derived_elastique": load_audio(general_dir / "elastique.wav")[0],
            "general_harmonic": load_audio(general_dir / "boiled_harmonic.wav")[0],
            "transient_harmonic": load_audio(transient_dir / "boiled_harmonic.wav")[0],
        }
        if any(len(audio) != len(reference) for audio in systems.values()):
            raise SystemExit(f"length mismatch for {stem} / {percent}")
        reference, systems = level_match(reference, systems)

        trial_dir = args.output / f"trial_{trial:02d}"
        trial_dir.mkdir(exist_ok=True)
        sf.write(trial_dir / "reference.wav", reference, sample_rate, subtype="FLOAT")
        order = list(systems)
        rng.shuffle(order)

        row: dict[str, object] = {
            "trial": trial,
            "category": condition["category"],
            "stem": stem,
            "percent": percent,
            "semitones": condition["semitones"],
            "transient_onset_gain": condition["transient_onset_gain"],
            "transient_env_delta_db": condition["transient_env_delta_db"],
            "reference": f"trial_{trial:02d}/reference.wav",
        }
        key = {name: row[name] for name in (
            "trial", "category", "stem", "percent", "semitones",
            "transient_onset_gain", "transient_env_delta_db",
        )}
        for label, system in zip(labels, order):
            filename = f"{label}.wav"
            sf.write(trial_dir / filename, systems[system], sample_rate, subtype="FLOAT")
            row[label] = f"trial_{trial:02d}/{filename}"
            key[label] = system
        manifest.append(row)
        answer_key.append(key)

    manifest_fields = [
        "trial", "category", "stem", "percent", "semitones",
        "transient_onset_gain", "transient_env_delta_db", "reference", *labels,
    ]
    with (args.output / "manifest.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=manifest_fields)
        writer.writeheader()
        writer.writerows(manifest)
    with (args.output / "answer_key.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=[field for field in manifest_fields if field != "reference"])
        writer.writeheader()
        writer.writerows(answer_key)

    write_html(args.output / "index.html", manifest, labels)
    mean_gain = float(np.mean([float(row["transient_onset_gain"]) for row in selected])) if selected else 0.0
    (args.output / "README.txt").write_text(
        "Attack-sensitive blind profile comparison. Systems are derived Elastique, General 2048/256 + Harmonic formant, and Transient 1024/128 + Harmonic formant. "
        "Audio is RMS matched within each trial. Open index.html and inspect answer_key.csv only after finishing.\n"
        f"Selected trials: {len(selected)}; mean Transient onset-correlation gain over General: {mean_gain:+.4f}.\n",
        encoding="utf-8",
    )
    print(f"wrote {len(selected)} trials; mean selected onset gain={mean_gain:+.4f}")


if __name__ == "__main__":
    main()
