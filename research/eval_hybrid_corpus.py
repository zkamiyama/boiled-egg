#!/usr/bin/env python3
"""Paired offline HPSS/WSOLA experiments; direct TSM is separate from pitch.

Frozen exploratory presets, not tuned on test scores. HPSS uses existing C++
PV for harmonic content and short OLA for the complementary percussive content.
No new method here is claimed realtime-safe or perceptually superior.
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import csv
import json
import math
import subprocess
from collections import defaultdict
from pathlib import Path

import numpy as np
import soundfile as sf

from eval_elastique_pitch import PAT, category, exact_resample, metrics
from eval_multires_corpus import checked_audio, fingerprint
from hpss_wsola_reference import output_frames, overlap_add, separate, wsola


def cpp_render(cli: Path, source: Path, destination: Path, time: float,
               pitch: float, fft: int | None) -> tuple[np.ndarray, int]:
    command = [str(cli), str(source), str(destination), '--time', f'{time:.12g}',
               '--pitch-ratio', f'{pitch:.12g}', '--formant',
               'off' if pitch == 1 else 'harmonic', '--block', '256']
    if fft is not None:
        command += ['--mode', 'locked', '--fft', str(fft), '--hop', '256']
    subprocess.run(command, check=True, capture_output=True, text=True, timeout=120)
    return checked_audio(destination)


def source_job(job: tuple) -> list[dict]:
    args, stem, tests = job
    source = args.ref_dir / f'{stem}.wav'
    x, rate = checked_audio(source)
    root = args.output / 'renders' / stem
    root.mkdir(parents=True)
    h, p = separate(x)
    harmonic_source = root / 'harmonic_input.wav'
    sf.write(harmonic_source, h, rate, subtype='FLOAT')
    rows = []
    for test in tests:
        match = PAT.fullmatch(test.name)
        if match is None:
            raise ValueError(f'invalid condition {test}')
        tsm, sr = checked_audio(test)
        if sr != rate or tsm.shape[1] != x.shape[1]:
            raise ValueError(f'source/TSM mismatch {test}')
        ratio = len(tsm)/len(x)
        semitones = 12*math.log2(ratio)
        # Match the research C ABI float control value exactly.
        control_ratio = float(np.float32(ratio))
        output_frames(len(x), control_ratio)
        cond = root / f'{match["percent"]}_per'
        cond.mkdir()
        for task in ('tsm', 'pitch'):
            if task == 'pitch' and abs(semitones) > 12.0001:
                continue
            folder = cond/task
            folder.mkdir()
            time_ratio = control_ratio if task == 'tsm' else 1.0
            pitch_ratio = 1.0 if task == 'tsm' else control_ratio
            expected = output_frames(len(x), time_ratio)
            native = tsm if task == 'tsm' else exact_resample(tsm, len(x))
            baseline = 'elastique_tsm' if task == 'tsm' else 'derived_elastique'
            systems = {baseline: native}
            if task == 'tsm':
                for name, cli, fft in (
                    ('general', args.pv_cli, 2048),
                    ('transient', args.pv_cli, 1024),
                    ('multires', args.multires_cli, None),
                ):
                    audio, sr2 = cpp_render(cli, source, folder/f'{name}.wav', time_ratio, 1, fft)
                    if sr2 != rate or audio.shape != (expected, x.shape[1]):
                        raise ValueError(f'C++ duration/channel/rate failure {name}/{stem}')
                    systems[name] = audio
                systems['wsola'] = wsola(x, time_ratio)
            percussive = overlap_add(p, control_ratio)
            if task == 'pitch':
                percussive = exact_resample(percussive, len(x))
            for name, fft in (('hpss_general', 2048), ('hpss_transient', 1024)):
                audio, sr2 = cpp_render(args.pv_cli, harmonic_source, folder/f'{name}_h.wav',
                                        time_ratio, pitch_ratio, fft)
                if sr2 != rate or audio.shape != percussive.shape:
                    raise ValueError(f'HPSS branch mismatch {name}/{stem}')
                systems[name] = audio+percussive
            for system, y in systems.items():
                dst = folder/f'{system}.wav'
                sf.write(dst, y, rate, subtype='FLOAT')
                y, sr2 = checked_audio(dst)
                if sr2 != rate or y.shape[1] != x.shape[1]:
                    raise ValueError(f'bad output metadata {dst}')
                if system != baseline and len(y) != expected:
                    raise ValueError(f'bad output duration {dst}')
                env, onset, rms, peak = metrics(x, y, rate)
                rows.append(dict(task=task, stem=stem, category=category(stem),
                    percent=match['percent'], duration_ratio=ratio,
                    control_ratio=control_ratio, semitones=semitones,
                    system=system, env=env, onset=onset, rms=rms, peak=peak,
                    frames=len(y), duration_error_frames=len(y)-expected,
                    reference_sha256=fingerprint(source), tsm_sha256=fingerprint(test),
                    render_sha256=fingerprint(dst),
                    render_path=str(dst.relative_to(args.output))))
    return rows


def summarize(rows: list[dict]) -> dict:
    grouped = defaultdict(dict)
    for r in rows:
        grouped[(r['task'], r['stem'], r['percent'])][r['system']] = r
    summaries = {}
    for task in ('tsm', 'pitch'):
        baseline = 'elastique_tsm' if task == 'tsm' else 'derived_elastique'
        for subset in ('all', 'target'):
            pairs = [v for k,v in grouped.items() if k[0] == task and
                     (subset == 'all' or abs(v[baseline]['semitones']) <= 12.0001)]
            if not pairs:
                continue
            systems = sorted(set.intersection(*(set(p) for p in pairs))-{baseline})
            summaries[task+'_'+subset] = {}
            for system in systems:
                de = [p[system]['env']-p[baseline]['env'] for p in pairs]
                do = [p[system]['onset']-p[baseline]['onset'] for p in pairs]
                summaries[task+'_'+subset][system] = dict(conditions=len(pairs),
                    env_delta=float(np.mean(de)), onset_delta=float(np.mean(do)),
                    env_wins=sum(d < 0 for d in de), onset_wins=sum(d > 0 for d in do),
                    max_peak=max(p[system]['peak'] for p in pairs),
                    max_duration_error_frames=max(abs(p[system]['duration_error_frames']) for p in pairs))
    return summaries


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('pv-cli','multires-cli','ref-dir','test-dir','output'):
        parser.add_argument('--'+name, type=Path, required=True)
    parser.add_argument('--workers', type=int, default=3)
    parser.add_argument('--source-commit', required=True)
    args = parser.parse_args()
    if args.workers < 1:
        parser.error('workers must be positive')
    args.pv_cli = args.pv_cli.resolve(strict=True)
    args.multires_cli = args.multires_cli.resolve(strict=True)
    tests = sorted(args.test_dir.glob('*_Elastique_*_per.wav'))
    if not tests:
        raise ValueError('no supplied Elastique TSM conditions')
    groups = defaultdict(list)
    for path in tests:
        match = PAT.fullmatch(path.name)
        if match is None:
            raise ValueError(f'invalid condition {path}')
        groups[match['stem']].append(path)
    # All source inputs are checked before creating results.
    for stem, paths in groups.items():
        x, rate = checked_audio(args.ref_dir/f'{stem}.wav')
        if rate != 44100:
            raise ValueError('this frozen corpus preset requires 44.1 kHz')
        for path in paths:
            y, sr = checked_audio(path)
            if sr != rate or y.shape[1] != x.shape[1]:
                raise ValueError(f'source/TSM mismatch {path}')
            output_frames(len(x), len(y)/len(x))
    if args.output.exists() and (not args.output.is_dir() or any(args.output.iterdir())):
        raise ValueError('output must be absent or empty')
    args.output.mkdir(parents=True, exist_ok=True)
    jobs = [(args, stem, paths) for stem, paths in sorted(groups.items())]
    rows = []
    with cf.ProcessPoolExecutor(max_workers=args.workers) as executor:
        for i, result in enumerate(executor.map(source_job, jobs), 1):
            rows.extend(result)
            print(f'source {i}/{len(jobs)}', flush=True)
    with (args.output/'metrics.csv').open('w', newline='', encoding='utf-8') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader(); writer.writerows(rows)
    summary = dict(source_commit=args.source_commit,
                   pv_cli_sha256=fingerprint(args.pv_cli),
                   multires_cli_sha256=fingerprint(args.multires_cli),
                   hpss=dict(fft=2048, hop=256, median_kernel=17, mask='complementary soft power'),
                   ola=dict(frame=512, hop=256),
                   wsola=dict(frame=2048, hop=1024, tolerance=512),
                   preset_status='frozen exploratory; not tuned on testing scores',
                   target_definition='TSM duration [0.5,2], pitch +/-12 st; tolerance 0.0001 st',
                   listening_status='not_listened', realtime_status='offline only',
                   results=summarize(rows))
    text = json.dumps(summary, indent=2, allow_nan=False)
    (args.output/'summary.json').write_text(text+'\n', encoding='utf-8')
    print(text)

if __name__ == '__main__':
    main()
