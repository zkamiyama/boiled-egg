#!/usr/bin/env python3
"""Create an exact-grid, three-way reference-only blind pack with a local player.

Distribute only listener/. Keep analyst/ and its answer key away from listeners.
This is not the four-way derived-Elastique pack and cannot replace that gate.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import html
import itertools
import json
import random
import tempfile
from collections import defaultdict
from pathlib import Path
from urllib.parse import quote

import numpy as np
import soundfile as sf

from eval_reference_profiles import PITCHES, PROFILES, SCHEMA, summarize
from eval_multires_corpus import fingerprint
from make_blind_multires_pack import level_match, load_trial

PACK_SCHEMA = 'boiled-egg.reference-profile-pack.v1'
CRITERIA = ('overall', 'attack', 'formant', 'stability')
RATING_FIELDS = ('pack_id', 'listener_id', 'trial_id', 'label', *CRITERIA, 'notes')


def inside(root: Path, relative: str) -> Path:
    if not relative or Path(relative).is_absolute() or '\\' in relative:
        raise ValueError('expected relative corpus path')
    path = (root/relative).resolve(strict=True)
    if not path.is_relative_to(root.resolve()) or not path.is_file():
        raise ValueError('corpus path escapes its root or is not a file')
    return path


def read_grid(root: Path) -> tuple[dict, list[dict]]:
    summary = json.loads((root/'summary.json').read_text())
    if summary['schema'] != SCHEMA or summary['external_baseline'] != 'none' or summary['mos_transfer'] is not False:
        raise ValueError('not a reference-only profile evaluation')
    if fingerprint(root/'metrics.csv') != summary['metrics_sha256']:
        raise ValueError('metrics fingerprint mismatch')
    with (root/'metrics.csv').open(newline='', encoding='utf-8') as stream:
        rows = list(csv.DictReader(stream))
    for row in rows:
        for key in ('pitch_semitones', 'sample_rate', 'frames', 'channels', 'duration_error_frames'):
            row[key] = int(row[key])
        for key in ('env', 'onset', 'rms', 'peak', 'control_ratio'):
            row[key] = float(row[key])
            if not np.isfinite(row[key]):
                raise ValueError('non-finite metric in reference grid')
    summarize(rows, summary['sources'], summary['formants'])
    sources = {s['stem']: s for s in summary['sources']}
    if len(sources) != len(summary['sources']):
        raise ValueError('duplicate source provenance')
    for row in rows:
        source = sources[row['stem']]
        if any(row[key] != source[key] for key in
               ('category', 'reference_name', 'reference_sha256', 'sample_rate', 'frames', 'channels')):
            raise ValueError('inconsistent source provenance')
        expected_ratio = float(np.float32(2.0**(row['pitch_semitones']/12)))
        if row['control_ratio'] != expected_ratio or row['duration_error_frames'] != 0:
            raise ValueError('wrong control ratio or duration')
    return summary, rows


def player(trials: list[dict], pack_id: str) -> str:
    sections = []
    for trial in trials:
        tid = trial['trial_id']
        variants = []
        for label in 'ABC':
            inputs = ''.join(
                f'<label>{criterion}<select data-trial="{tid}" data-label="{label}" data-criterion="{criterion}">'
                '<option value=""></option>'+''.join(f'<option>{i}</option>' for i in range(1,6))+'</select></label>'
                for criterion in CRITERIA)
            variants.append(f'<div class="variant"><h3>{label}</h3><audio controls preload="none" '
                            f'src="audio/{tid}/{label}.wav"></audio><div class="scores">{inputs}</div>'
                            f'<input data-notes="{tid}/{label}" placeholder="Notes"></div>')
        sections.append(f'<section><h2>{tid} · {html.escape(trial["category"])} · '
                        f'{trial["pitch_semitones"]:+d} st</h2><p>Unshifted reference</p>'
                        f'<audio controls preload="none" src="audio/{tid}/reference.wav"></audio>'
                        +''.join(variants)+'</section>')
    # Only blind trial IDs appear in browser metadata; no answer key or seed.
    return '''<!doctype html><html lang="en"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Blind profile listening</title><style>
body{font:16px system-ui;max-width:1000px;margin:2em auto;padding:0 1em;line-height:1.5}
section{border-top:1px solid #aaa;margin:2em 0;padding-top:1em}.variant{padding:1em;background:#f4f4f4;margin:.6em 0}
audio{width:min(100%,540px)}.scores{display:flex;gap:1em;flex-wrap:wrap}select{margin:.5em}input{padding:.5em}
button{padding:.8em;font-size:1em}h3{margin:.3em 0}
</style><h1>Blind profile listening</h1>
<p>Three anonymous candidates; no external baseline. Rate 1 (poor) to 5 (excellent).
For stability, 5 means no audible pumping or wavering. The unshifted reference is a
source/timbre reference, not a pitch-matched hidden anchor. Keep playback volume fixed.</p>
<p>Complete all four scores for each rated candidate. Overall / attack clarity /
formant-timbre naturalness / stability. Export before closing; this page does not autosave.</p>
<label>Listener ID <input id="listener" autocomplete="off"></label>
<button id="export">Export ratings CSV</button><span id="status" role="status"></span>
'''+''.join(sections)+'''<script>
'use strict';
const packId = '''+json.dumps(pack_id)+''';
const trials = '''+json.dumps([t['trial_id'] for t in trials])+''';
const criteria = ['overall','attack','formant','stability'];
const csvCell = v => '"' + String(v).replaceAll('"','""') + '"';
document.addEventListener('play', e => {
  document.querySelectorAll('audio').forEach(a => {if(a !== e.target) a.pause();});
}, true);
document.getElementById('export').onclick = () => {
  const listener = document.getElementById('listener').value.trim();
  if(!listener) {document.getElementById('status').textContent=' Enter a listener ID.'; return;}
  const rows = [['pack_id','listener_id','trial_id','label',...criteria,'notes']];
  for(const trial of trials) for(const label of ['A','B','C']) {
    const values = criteria.map(c => document.querySelector(
      `[data-trial="${trial}"][data-label="${label}"][data-criterion="${c}"]`).value);
    if(values.some(Boolean) && !values.every(Boolean)) {
      document.getElementById('status').textContent=` Complete all four scores for ${trial}/${label}.`; return;
    }
    rows.push([packId,listener,trial,label,...values,
      document.querySelector(`[data-notes="${trial}/${label}"]`).value]);
  }
  const url = URL.createObjectURL(new Blob([rows.map(r => r.map(csvCell).join(',')).join('\\r\\n')+'\\r\\n'],
    {type:'text/csv;charset=utf-8'}));
  const link = document.createElement('a'); link.href=url; link.download='ratings.csv'; link.click();
  setTimeout(() => URL.revokeObjectURL(url),1000);
  document.getElementById('status').textContent=' Exported. Keep the CSV.';
};
</script></html>'''


def make_pack(evaluation: Path, references: Path, output: Path, formant: str,
              per_category: int = 1, seed: int = 20260913) -> dict:
    if per_category < 1:
        raise ValueError('per-category must be positive')
    summary, rows = read_grid(evaluation)
    if formant not in summary['formants']:
        raise ValueError('requested formant policy was not evaluated')
    categories = defaultdict(list)
    for source in summary['sources']:
        categories[source['category']].append(source['stem'])
    selected = []
    rng = random.Random(seed)
    for category, stems in sorted(categories.items()):
        if len(stems) < per_category:
            raise ValueError(f'insufficient sources in category {category}')
        selected.extend(rng.sample(sorted(stems), per_category))
    grid = defaultdict(dict)
    for row in rows:
        if row['stem'] in selected and row['formant'] == formant:
            grid[(row['stem'], row['pitch_semitones'])][row['profile']] = row
    # Use all six label permutations per source, balanced across pitch cells.
    candidates = []
    for stem in selected:
        permutations = list(itertools.permutations(PROFILES))
        rng.shuffle(permutations)
        for pitch, permutation in zip(PITCHES, permutations):
            candidates.append((stem, pitch, permutation))
    rng.shuffle(candidates)
    identity = dict(evaluation_summary_sha256=fingerprint(evaluation/'summary.json'),
                    formant=formant, per_category=per_category, seed=seed)
    pack_id = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()
    key = dict(schema=PACK_SCHEMA, pack_id=pack_id, **identity,
               corpus_label=summary['corpus_label'], external_baseline='none',
               category_policy=summary['category_policy'], trials=[])
    trials = []
    output = output.resolve()
    if output.exists() and (not output.is_dir() or any(output.iterdir())):
        raise ValueError('output must be absent or empty')
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.profile-pack-', dir=output.parent) as tmp:
        staging = Path(tmp)/'pack'
        listener = staging/'listener'
        analyst = staging/'analyst'
        listener.mkdir(parents=True); analyst.mkdir()
        for i, (stem, pitch, permutation) in enumerate(candidates, 1):
            paired = grid[(stem, pitch)]
            row = paired['general']
            source = inside(references, row['reference_name'])
            paths = {p: inside(evaluation, r['render_path']) for p,r in paired.items()}
            if fingerprint(source) != row['reference_sha256']:
                raise ValueError('reference fingerprint mismatch')
            if any(fingerprint(paths[p]) != paired[p]['render_sha256'] for p in PROFILES):
                raise ValueError('render fingerprint mismatch')
            reference, audio, rate = load_trial(source, paths)
            if rate != row['sample_rate'] or reference.shape != (row['frames'], row['channels']):
                raise ValueError('trial metadata mismatch')
            reference, audio = level_match(reference, audio)
            tid = f'T{i:03d}'
            folder = listener/'audio'/tid
            folder.mkdir(parents=True)
            sf.write(folder/'reference.wav', reference, rate, subtype='PCM_16')
            mapping = dict(zip('ABC', permutation))
            for label, profile in mapping.items():
                sf.write(folder/f'{label}.wav', audio[profile], rate, subtype='PCM_16')
            public = dict(trial_id=tid, category=row['category'], pitch_semitones=pitch)
            trials.append(public)
            key['trials'].append(dict(**public, stem=stem, formant=formant, labels=mapping,
                reference_sha256=row['reference_sha256'],
                raw_render_sha256={p:paired[p]['render_sha256'] for p in PROFILES}))
        public = dict(schema=PACK_SCHEMA, pack_id=pack_id, trials=trials,
                      criteria=list(CRITERIA), external_baseline='none',
                      audio_policy='RMS match capped +/-6 dB; common peak headroom 0.95; PCM16')
        (listener/'manifest.json').write_text(json.dumps(public, indent=2)+'\n')
        (listener/'index.html').write_text(player(trials, pack_id), encoding='utf-8')
        with (listener/'ratings.csv').open('w', newline='', encoding='utf-8') as stream:
            writer = csv.DictWriter(stream, fieldnames=RATING_FIELDS)
            writer.writeheader()
            for trial in trials:
                for label in 'ABC':
                    writer.writerow(dict(pack_id=pack_id, trial_id=trial['trial_id'], label=label))
        key['listener_sha256'] = {p.relative_to(listener).as_posix():fingerprint(p)
                                  for p in sorted(listener.rglob('*')) if p.is_file()}
        (analyst/'answer_key.json').write_text(json.dumps(key, indent=2)+'\n')
        if output.exists():
            output.rmdir()
        staging.rename(output)
    return dict(pack_id=pack_id, trials=len(trials), sources=len(selected),
                categories=sorted(categories), pitch_grid=list(PITCHES),
                external_baseline='none', listening_status='not_listened')


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('evaluation', 'ref-dir', 'output'):
        parser.add_argument('--'+name, type=Path, required=True)
    parser.add_argument('--formant', default='harmonic')
    parser.add_argument('--per-category', type=int, default=1)
    parser.add_argument('--seed', type=int, default=20260913)
    args = parser.parse_args()
    print(json.dumps(make_pack(args.evaluation, args.ref_dir, args.output, args.formant,
                               args.per_category, args.seed), indent=2))


if __name__ == '__main__':
    main()
