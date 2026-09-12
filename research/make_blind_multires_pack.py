#!/usr/bin/env python3
"""Create a balanced four-way blind listening pack for the current quality candidates."""
from __future__ import annotations

import argparse
import csv
import html
import math
import random
from collections import defaultdict
from decimal import Decimal, InvalidOperation
from pathlib import Path

import numpy as np
import soundfile as sf


def load_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as stream:
        return list(csv.DictReader(stream))


def load_audio(path: Path) -> tuple[np.ndarray, int]:
    audio, sample_rate = sf.read(path, always_2d=True, dtype="float32")
    if audio.size == 0 or not np.isfinite(audio).all():
        raise ValueError(f"empty or non-finite audio: {path}")
    return audio.astype(np.float64), sample_rate


def load_trial(reference_path: Path, system_paths: dict[str, Path]) -> tuple[np.ndarray, dict[str, np.ndarray], int]:
    reference, sample_rate = load_audio(reference_path)
    systems: dict[str, np.ndarray] = {}
    for name, path in system_paths.items():
        audio, rate = load_audio(path)
        if rate != sample_rate:
            raise ValueError(f"sample-rate mismatch: {path} ({rate} != {sample_rate})")
        if audio.shape != reference.shape:
            raise ValueError(f"duration/channel mismatch: {path} ({audio.shape} != {reference.shape})")
        systems[name] = audio
    return reference, systems, sample_rate


def rms(audio: np.ndarray) -> float:
    return math.sqrt(float(np.mean(audio * audio)) + 1.0e-30)


def level_match(reference: np.ndarray, systems: dict[str, np.ndarray]) -> tuple[np.ndarray, dict[str, np.ndarray]]:
    reference_rms = rms(reference)
    limit = 10.0 ** (6.0 / 20.0)
    matched: dict[str, np.ndarray] = {}
    for name, audio in systems.items():
        gain = float(np.clip(reference_rms / max(rms(audio), 1.0e-30), 1.0 / limit, limit))
        matched[name] = audio * gain
    maximum_peak = max(
        float(np.max(np.abs(reference))),
        *(float(np.max(np.abs(audio))) for audio in matched.values()),
    )
    common = min(1.0, 0.95 / max(maximum_peak, 1.0e-30))
    return reference * common, {name: audio * common for name, audio in matched.items()}


def condition_key(stem: str, percent: str) -> tuple[str, Decimal]:
    # Numeric spelling may differ between CSV and directory names (150/150.0),
    # but a nearby TSM factor is never the same listening condition.
    if not stem or stem in {".", ".."} or "/" in stem or "\\" in stem:
        raise ValueError(f"invalid source stem: {stem!r}")
    try:
        value = Decimal(percent)
    except InvalidOperation as error:
        raise ValueError(f"invalid condition percent: {percent!r}") from error
    if not value.is_finite() or value <= 0:
        raise ValueError(f"invalid condition percent: {percent!r}")
    return stem, value


def condition_map(rows: list[dict[str, str]]) -> dict[tuple[str, Decimal], dict[str, str]]:
    result: dict[tuple[str, Decimal], dict[str, str]] = {}
    for row in rows:
        key = condition_key(row["stem"], row["percent"])
        if key in result:
            raise ValueError(f"duplicate metric condition: {key}")
        result[key] = row
    return result


def standard_map(rows: list[dict[str, str]], system: str) -> dict[tuple[str, Decimal], dict[str, str]]:
    return condition_map([row for row in rows if row["system"] == system])


def multires_map(rows: list[dict[str, str]]) -> dict[tuple[str, Decimal], dict[str, str]]:
    return condition_map(rows)


def select_conditions(
    general_rows: list[dict[str, str]],
    transient_rows: list[dict[str, str]],
    multires_rows: list[dict[str, str]],
    per_category: int,
) -> list[dict[str, object]]:
    if per_category <= 0:
        raise ValueError("per-category must be positive")
    general = standard_map(general_rows, "harmonic")
    transient = standard_map(transient_rows, "harmonic")
    elastique = standard_map(general_rows, "elastique")
    multires = multires_map(multires_rows)
    groups: dict[str, list[dict[str, object]]] = defaultdict(list)

    for key, general_row in general.items():
        semitones = float(general_row["semitones"])
        if not math.isfinite(semitones):
            raise ValueError(f"non-finite pitch for {key}")
        if abs(semitones) > 12.0001:
            continue
        if key not in transient or key not in elastique or key not in multires:
            raise ValueError(f"missing paired metrics for {key}")
        for paired in (transient[key], elastique[key], multires[key]):
            if paired["category"] != general_row["category"] or not math.isclose(
                float(paired["semitones"]), semitones, rel_tol=0.0, abs_tol=1.0e-6
            ):
                raise ValueError(f"inconsistent paired metadata for {key}")
        onset = [
            float(elastique[key]["onset_corr"]),
            float(general_row["onset_corr"]),
            float(transient[key]["onset_corr"]),
            float(multires[key]["onset"]),
        ]
        envelope = [
            float(elastique[key]["env_rmse_db"]),
            float(general_row["env_rmse_db"]),
            float(transient[key]["env_rmse_db"]),
            float(multires[key]["env"]),
        ]
        if not all(math.isfinite(value) for value in onset + envelope):
            raise ValueError(f"non-finite metrics for {key}")
        # Prefer trials where the objective systems differ enough to make a
        # listening decision informative. This score is used only for trial
        # selection and is never shown to the listener.
        score = (max(onset) - min(onset)) + 0.04 * (max(envelope) - min(envelope))
        groups[general_row["category"]].append(
            {
                "stem": key[0],
                "percent": general_row["percent"],
                "category": general_row["category"],
                "semitones": semitones,
                "selection_score": score,
            }
        )

    selected: list[dict[str, object]] = []
    for category in sorted(groups):
        ranked = sorted(groups[category], key=lambda row: float(row["selection_score"]), reverse=True)
        selected.extend(ranked[:per_category])
    if not selected:
        raise ValueError("no complete conditions within +/-12 semitones")
    return selected


def source_dir(root: Path, stem: str, percent: str) -> Path:
    key = condition_key(stem, percent)
    matches: list[Path] = []
    for path in sorted((root / stem).glob("*_per")):
        if not path.is_dir():
            continue
        try:
            candidate = condition_key(stem, path.name[:-4])
        except ValueError:
            continue
        if candidate == key:
            matches.append(path)
    if not matches:
        raise FileNotFoundError(f"no exact render condition for {stem} / {percent} under {root}")
    if len(matches) != 1:
        raise ValueError(f"ambiguous render condition for {stem} / {percent}: {matches}")
    return matches[0]


def trial_paths(args: argparse.Namespace, condition: dict[str, object]) -> tuple[Path, dict[str, Path]]:
    stem, percent = str(condition["stem"]), str(condition["percent"])
    general = source_dir(args.general_renders, stem, percent)
    transient = source_dir(args.transient_renders, stem, percent)
    multires = source_dir(args.multires_renders, stem, percent)
    return args.ref_dir / f"{stem}.wav", {
        "derived_elastique": general / "elastique.wav",
        "general_harmonic": general / "boiled_harmonic.wav",
        "transient_harmonic": transient / "boiled_harmonic.wav",
        "multires_harmonic": multires / "multires_harmonic.wav",
    }


def write_html(path: Path, manifest: list[dict[str, object]], labels: tuple[str, ...]) -> None:
    sections = []
    for row in manifest:
        trial = int(row["trial"])
        options = "".join(
            f'<div><b>{label}</b> <audio controls preload="none" src="{html.escape(str(row[label]))}"></audio> '
            f'<label><input type="radio" name="overall-{trial}" value="{label}"> Overall</label> '
            f'<label><input type="radio" name="attack-{trial}" value="{label}"> Attack/clarity</label> '
            f'<label><input type="radio" name="tone-{trial}" value="{label}"> Tonal/formant</label></div>'
            for label in labels
        )
        sections.append(
            f'<section><h3>Trial {trial} — {html.escape(str(row["category"]))} — '
            f'{float(row["semitones"]):+.2f} st</h3>'
            f'<div><b>Reference</b> <audio controls preload="none" src="{html.escape(str(row["reference"]))}"></audio></div>'
            f'{options}</section>'
        )

    document = '''<!doctype html><meta charset="utf-8"><title>boiled egg blind quality test</title>
<style>body{font-family:sans-serif;max-width:1100px;margin:2rem auto;padding:0 1rem}section{border-top:1px solid #aaa;padding:1rem 0}audio{width:420px;vertical-align:middle;margin:.3rem 1rem}.bar{position:sticky;top:0;background:#fff;padding:.6rem}</style>
<h1>boiled egg blind quality test</h1>
<p>A-D are anonymized and RMS-matched. Compare each with Reference. Choose Overall, Attack/clarity, and Tonal/formant naturalness independently. Do not open answer_key.csv until finished.</p>
<div class="bar"><button onclick="save()">Export choices.csv</button></div>''' + "".join(sections) + '''<script>
function save(){let lines=['trial,overall,attack,tone'];document.querySelectorAll('section').forEach((s,i)=>{let f=n=>s.querySelector('input[name^="'+n+'-"]:checked');let o=f('overall'),a=f('attack'),t=f('tone');lines.push((i+1)+','+(o?o.value:'')+','+(a?a.value:'')+','+(t?t.value:''));});let b=new Blob([lines.join('\\n')+'\\n'],{type:'text/csv'}),a=document.createElement('a');a.href=URL.createObjectURL(b);a.download='choices.csv';a.click();}
</script>'''
    path.write_text(document, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--general-metrics", type=Path, required=True)
    parser.add_argument("--general-renders", type=Path, required=True)
    parser.add_argument("--transient-metrics", type=Path, required=True)
    parser.add_argument("--transient-renders", type=Path, required=True)
    parser.add_argument("--multires-metrics", type=Path, required=True)
    parser.add_argument("--multires-renders", type=Path, required=True)
    parser.add_argument("--ref-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--per-category", type=int, default=6)
    parser.add_argument("--seed", type=int, default=20260830)
    args = parser.parse_args()

    selected = select_conditions(
        load_rows(args.general_metrics),
        load_rows(args.transient_metrics),
        load_rows(args.multires_metrics),
        args.per_category,
    )
    rng = random.Random(args.seed)
    rng.shuffle(selected)
    if args.output.exists() and (not args.output.is_dir() or any(args.output.iterdir())):
        raise ValueError(f"output must be absent or empty: {args.output}")
    # Validate every selected trial before writing any listening audio. Keep
    # memory bounded to one trial; the writing pass reloads the checked paths.
    paths = [trial_paths(args, condition) for condition in selected]
    for reference_path, system_paths in paths:
        load_trial(reference_path, system_paths)
    args.output.mkdir(parents=True, exist_ok=True)

    labels = ("A", "B", "C", "D")
    manifest: list[dict[str, object]] = []
    answer_key: list[dict[str, object]] = []

    for trial, condition in enumerate(selected, 1):
        stem = str(condition["stem"])
        percent = str(condition["percent"])
        reference, systems, sample_rate = load_trial(*paths[trial - 1])
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
            "reference": f"trial_{trial:02d}/reference.wav",
        }
        key = {name: row[name] for name in ("trial", "category", "stem", "percent", "semitones")}
        for label, system in zip(labels, order):
            filename = f"{label}.wav"
            sf.write(trial_dir / filename, systems[system], sample_rate, subtype="FLOAT")
            row[label] = f"trial_{trial:02d}/{filename}"
            key[label] = system
        manifest.append(row)
        answer_key.append(key)

    fields = ["trial", "category", "stem", "percent", "semitones", "reference", *labels]
    with (args.output / "manifest.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(manifest)
    key_fields = [field for field in fields if field != "reference"]
    with (args.output / "answer_key.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=key_fields)
        writer.writeheader()
        writer.writerows(answer_key)

    write_html(args.output / "index.html", manifest, labels)
    (args.output / "README.txt").write_text(
        "Blind comparison: derived Elastique diagnostic, General 2048/256 Harmonic, Transient 1024/256 Harmonic, and realtime Multi-resolution 1024/256 + 512/192 Harmonic. "
        "Conditions are restricted to +/-12 semitones and balanced by source category. Audio is RMS matched within each trial. Open index.html; inspect answer_key.csv only after listening.\n",
        encoding="utf-8",
    )
    print(f"wrote {len(manifest)} trials")


if __name__ == "__main__":
    main()
