#!/usr/bin/env python3
"""Reproduce realtime multires pitch diagnostics on supplied Elastique TSM pairs.

No MOS transfer: the baseline is TSM followed by offline resampling, not a
native Elastique pitch shifter. All supplied conditions are retained; +/-12 st
and wider stress conditions are summarized separately. Audio remains local.
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import csv
import hashlib
import json
import math
import subprocess
from pathlib import Path

import numpy as np
import soundfile as sf

from eval_elastique_pitch import PAT, category, exact_resample, metrics


def fingerprint(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1048576), b''):
            digest.update(block)
    return digest.hexdigest()


def checked_audio(path: Path) -> tuple[np.ndarray, int]:
    audio, rate = sf.read(path, always_2d=True, dtype='float32')
    if not audio.size or not np.isfinite(audio).all():
        raise ValueError(f'empty/non-finite audio: {path}')
    return audio, rate


def evaluate(job: tuple[Path, Path, Path, Path, str]) -> dict:
    cli, references, test, output, formant = job
    match = PAT.fullmatch(test.name)
    if match is None:
        raise ValueError(f'invalid condition: {test.name}')
    stem, percent = match['stem'], match['percent']
    reference_path = references / f'{stem}.wav'
    reference, rate = checked_audio(reference_path)
    tsm, tsm_rate = checked_audio(test)
    if tsm_rate != rate or tsm.shape[1] != reference.shape[1]:
        raise ValueError(f'rate/channel mismatch: {test}')
    ratio = len(tsm) / len(reference)
    semitones = 12.0 * math.log2(ratio)
    destination = output / 'renders' / stem / f'{percent}_per'
    destination.mkdir(parents=True, exist_ok=True)
    rendered = destination / f'multires_{formant}.wav'
    command = [str(cli), str(reference_path), str(rendered), '--time', '1',
               '--pitch-ratio', f'{ratio:.12g}', '--formant', formant, '--block', '256']
    subprocess.run(command, check=True, capture_output=True, text=True, timeout=120)
    audio, out_rate = checked_audio(rendered)
    if out_rate != rate or audio.shape != reference.shape:
        raise ValueError(f'render shape/rate mismatch: {rendered}')
    derived = exact_resample(tsm, len(reference))
    env, onset, rms, peak = metrics(reference, audio, rate)
    el_env, el_onset, _, _ = metrics(reference, derived, rate)
    return dict(stem=stem, category=category(stem), percent=percent,
                pitch_ratio=ratio, semitones=semitones, formant=formant,
                env=env, onset=onset, rms=rms, peak=peak,
                env_delta_vs_elastique_db=env-el_env,
                onset_delta_vs_elastique=onset-el_onset,
                duration_error_frames=len(audio)-len(reference),
                reference_sha256=fingerprint(reference_path),
                tsm_sha256=fingerprint(test), render_sha256=fingerprint(rendered))


def summarize(rows: list[dict]) -> dict:
    if not rows:
        return {'conditions': 0}
    return dict(conditions=len(rows),
                mean_env_delta_vs_elastique_db=float(np.mean([r['env_delta_vs_elastique_db'] for r in rows])),
                mean_onset_delta_vs_elastique=float(np.mean([r['onset_delta_vs_elastique'] for r in rows])),
                env_wins=sum(r['env_delta_vs_elastique_db'] < 0 for r in rows),
                onset_wins=sum(r['onset_delta_vs_elastique'] > 0 for r in rows),
                max_peak=max(r['peak'] for r in rows),
                max_duration_error_frames=max(abs(r['duration_error_frames']) for r in rows))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('cli', 'ref-dir', 'test-dir', 'output'):
        parser.add_argument('--'+name, type=Path, required=True)
    parser.add_argument('--source-commit', required=True)
    parser.add_argument('--workers', type=int, default=3)
    parser.add_argument('--formant', choices=('off', 'harmonic', 'monophonic'), default='harmonic')
    args = parser.parse_args()
    if args.workers < 1:
        parser.error('workers must be positive')
    args.cli = args.cli.resolve(strict=True)
    tests = sorted(args.test_dir.glob('*_Elastique_*_per.wav'))
    if not tests:
        raise ValueError('no supplied Elastique conditions')
    # Validate all source pair metadata before invoking any render.
    for test in tests:
        match = PAT.fullmatch(test.name)
        if match is None:
            raise ValueError(f'invalid condition: {test}')
        x, sr = checked_audio(args.ref_dir / f'{match["stem"]}.wav')
        y, sr2 = checked_audio(test)
        if sr != sr2 or x.shape[1] != y.shape[1]:
            raise ValueError(f'rate/channel mismatch: {test}')
    if args.output.exists() and (not args.output.is_dir() or any(args.output.iterdir())):
        raise ValueError('output must be absent or empty')
    args.output.mkdir(parents=True, exist_ok=True)
    jobs = [(args.cli, args.ref_dir, p, args.output, args.formant) for p in tests]
    with cf.ProcessPoolExecutor(max_workers=args.workers) as executor:
        rows = []
        for i, row in enumerate(executor.map(evaluate, jobs), 1):
            rows.append(row)
            print(f'condition {i}/{len(jobs)}', flush=True)
    with (args.output/'metrics.csv').open('w', newline='', encoding='utf-8') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    summary = dict(source_commit=args.source_commit, cli_sha256=fingerprint(args.cli),
                   formant=args.formant, block=256,
                   all_conditions=summarize(rows),
                   target=summarize([r for r in rows if abs(r['semitones']) <= 12.0001]),
                   stress=summarize([r for r in rows if abs(r['semitones']) > 12.0001]),
                   listening_status='not_listened')
    text = json.dumps(summary, indent=2, allow_nan=False)
    (args.output/'summary.json').write_text(text+'\n', encoding='utf-8')
    print(text)


if __name__ == '__main__':
    main()
