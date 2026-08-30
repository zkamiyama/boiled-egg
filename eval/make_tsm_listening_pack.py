#!/usr/bin/env python3
"""Create a deterministic blind listening pack for matched TSM renders."""
from __future__ import annotations

import argparse
import csv
import hashlib
import html
import json
import random
import shutil
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "eval"))
from tsm_dataset import read_manifest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path, default=ROOT / "data" / "external" / "tsm_test")
    parser.add_argument("--boiled-manifest", type=Path, default=ROOT / "data" / "external" / "tsm_test" / "boiled_egg" / "manifest.csv")
    parser.add_argument("--pv-results", type=Path, default=ROOT / "results" / "pv_experiment" / "metrics.csv")
    parser.add_argument("--output", type=Path, default=ROOT / "results" / "listening_pack")
    parser.add_argument("--trials", type=int, default=20)
    parser.add_argument("--seed", type=int, default=20260830)
    parser.add_argument("--include-pv", action="store_true")
    args = parser.parse_args()

    dataset = args.dataset.resolve(); output = args.output.resolve()
    if output.exists(): shutil.rmtree(output)
    audio_dir = output / "audio"; audio_dir.mkdir(parents=True)
    baseline = read_manifest(dataset / "manifest.csv"); boiled = read_manifest(args.boiled_manifest)
    by_case: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for row in baseline:
        key = (row["reference_name"], f"{float(row['ratio']):.3f}")
        by_case[key].append({"system": row["method"], "path": str(dataset / row["processed_path"]), "mos": row.get("mos", "")})
    for row in boiled:
        keys = [k for k in by_case if k[0] == row["reference_name"]]
        if not keys: continue
        key = min(keys, key=lambda k: abs(float(k[1]) - float(row["ratio"])))
        by_case[key].append({"system": "boiled-egg", "path": str(dataset / row["processed_path"]), "mos": ""})
    if args.include_pv and args.pv_results.exists():
        for row in read_manifest(args.pv_results):
            keys = [k for k in by_case if k[0] == row["reference_name"]]
            if not keys: continue
            key = min(keys, key=lambda k: abs(float(k[1]) - float(row["ratio"])))
            by_case[key].append({"system": f"PV-{row['mode']}", "path": str(args.pv_results.parent / row["output_path"]), "mos": ""})

    rng = random.Random(args.seed)
    available = [k for k, systems in by_case.items() if any(s["system"] == "boiled-egg" for s in systems)]
    buckets: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for key in available: buckets[key[1]].append(key)
    for values in buckets.values(): rng.shuffle(values)
    selected = []
    while len(selected) < min(args.trials, len(available)):
        progressed = False
        for ratio in sorted(buckets):
            if buckets[ratio] and len(selected) < args.trials:
                selected.append(buckets[ratio].pop()); progressed = True
        if not progressed: break

    key_rows = []; public_trials = []
    for trial_index, key in enumerate(selected, 1):
        reference_name, ratio = key; systems = list(by_case[key]); rng.shuffle(systems)
        trial_code = f"T{trial_index:03d}"
        ref_source = next(r for r in baseline if r["reference_name"] == reference_name)
        original_src = dataset / ref_source["reference_path"]
        original_dst = audio_dir / f"{trial_code}_original{original_src.suffix.lower()}"; shutil.copy2(original_src, original_dst)
        choices = []
        for choice_index, system in enumerate(systems):
            source = Path(system["path"])
            if not source.exists(): continue
            token = hashlib.sha1(f"{args.seed}\0{trial_code}\0{choice_index}\0{system['system']}".encode()).hexdigest()[:8]
            label = chr(ord("A") + len(choices)); destination = audio_dir / f"{trial_code}_{label}_{token}{source.suffix.lower()}"
            shutil.copy2(source, destination); choices.append({"label": label, "file": destination.relative_to(output).as_posix()})
            key_rows.append({"trial": trial_code, "reference_name": reference_name, "ratio": ratio, "choice": label, "system": system["system"], "dataset_mos": system["mos"], "file": destination.relative_to(output).as_posix()})
        public_trials.append({"trial": trial_code, "source": reference_name, "ratio": ratio, "original": original_dst.relative_to(output).as_posix(), "choices": choices})

    with (output / "KEY.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(key_rows[0])); writer.writeheader(); writer.writerows(key_rows)
    (output / "trials.json").write_text(json.dumps(public_trials, indent=2), encoding="utf-8")
    trial_html = []
    for trial in public_trials:
        choices = []
        for choice in trial["choices"]:
            choices.append(f'''<section class="choice"><h3>Choice {html.escape(choice['label'])}</h3><audio controls preload="none" src="{html.escape(choice['file'])}"></audio><label>Quality 1–5 <input type="range" min="1" max="5" step="0.1" value="3" data-trial="{html.escape(trial['trial'])}" data-choice="{html.escape(choice['label'])}"><output>3.0</output></label></section>''')
        trial_html.append(f'''<article class="trial"><h2>{html.escape(trial['trial'])} — ratio {html.escape(trial['ratio'])}</h2><p>Original source (orientation only)</p><audio controls preload="none" src="{html.escape(trial['original'])}"></audio><div class="choices">{''.join(choices)}</div><label>Notes <textarea data-notes="{html.escape(trial['trial'])}"></textarea></label></article>''')
    page = f'''<!doctype html><html lang="en"><meta charset="utf-8"><title>boiled egg blind TSM listening pack</title><style>body{{font:16px system-ui,sans-serif;max-width:1100px;margin:2rem auto;padding:0 1rem}}.trial{{border-top:2px solid #888;padding:1rem 0 2rem}}.choices{{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:1rem}}.choice{{border:1px solid #bbb;border-radius:.5rem;padding:1rem}}audio{{width:100%}}label{{display:block;margin-top:.75rem}}textarea{{width:100%;min-height:4rem}}button{{font-size:1rem;padding:.7rem 1rem}}</style><h1>boiled egg blind TSM listening pack</h1><p>Use headphones, avoid looking at <code>KEY.csv</code>, and rate audible quality/artifacts rather than preference for tempo.</p>{''.join(trial_html)}<button id="export">Export ratings JSON</button><script>for(const s of document.querySelectorAll('input[type=range]')){{s.addEventListener('input',()=>s.nextElementSibling.value=Number(s.value).toFixed(1));}}document.getElementById('export').addEventListener('click',()=>{{const ratings=[];for(const s of document.querySelectorAll('input[type=range]'))ratings.push({{trial:s.dataset.trial,choice:s.dataset.choice,rating:Number(s.value)}});const notes={{}};for(const a of document.querySelectorAll('textarea'))notes[a.dataset.notes]=a.value;const blob=new Blob([JSON.stringify({{ratings,notes}},null,2)],{{type:'application/json'}});const a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download='ratings.json';a.click();URL.revokeObjectURL(a.href);}});</script></html>'''
    (output / "index.html").write_text(page, encoding="utf-8"); print(output / "index.html")


if __name__ == "__main__":
    main()
