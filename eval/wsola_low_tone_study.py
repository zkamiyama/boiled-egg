#!/usr/bin/env python3
"""Preregistered config ablation: execution integrity != quality qualification."""
from __future__ import annotations
import argparse
import itertools
import hashlib
import json
from pathlib import Path
import resource
import statistics
import sys
import numpy as np
import scipy
import soundfile as sf
import comparison_contract as c
import offline_pv_benchmark as metrics
import wsola_offline as host

FAMILIES = tuple(f'tone{f}_phase{phase}' for f in (41, 61, 83) for phase in (0, 1)) + (
    'tone223_phase0', 'harmonic83', 'bursts', 'mixed')
SHIFTS = (-12, 0, 12)
BLOCKS = (32, 64)
REPEATS = 3
BASE = '939270b9b26fa04e481f3f6feaae0e90102599c9'


def fixture(name: str, rate: int) -> tuple[np.ndarray, dict]:
    if name not in FAMILIES or rate not in host.RATES: raise ValueError('unknown fixture')
    if name in ('bursts', 'mixed'): return metrics.fixture(name, rate)
    t = np.arange(round(.75*rate))/rate
    if name.startswith('tone'):
        label, phase = name.split('_phase'); frequencies = [float(label[4:])]
        amplitudes = [.2]; phase = int(phase)*np.pi/3; family = 'low'
    else:
        frequencies = [83.*n for n in (1, 2, 3, 5)]
        amplitudes = [.12, .06, .03, .015]; phase = 0; family = 'harmonic'
    y = sum(a*np.sin(2*np.pi*f*t+phase) for f, a in zip(frequencies, amplitudes))
    y *= np.minimum(1., np.minimum(t/.02, (.75-t)/.02))
    return y.astype(np.float32), dict(family=family, rate=rate, frames=len(y),
        frequencies=frequencies, amplitudes=amplitudes)


def prepare(library: Path, output: Path) -> dict:
    output = output.resolve(); output.mkdir(parents=True, exist_ok=False)
    source_root = Path(__file__).resolve().parents[1]
    files = metrics.file_map(source_root)
    files.update(metrics.binary_map(library))
    inputs = []
    for name, rate in itertools.product(FAMILIES, host.RATES):
        x, metadata = fixture(name, rate); path = output/f'{name}-{rate}.wav'
        sf.write(path, x, rate, subtype='FLOAT')
        inputs.append(dict(name=name, path=str(path), metadata=metadata, audio=c.inspect_audio(path)))
    plan = dict(schema='boiled-egg.wsola-low-tone.v1', base_main=BASE,
        library=str(library.resolve()), files=files, sources=inputs,
        profiles=list(host.PROFILES), shifts=list(SHIFTS), blocks=list(BLOCKS), repeats=REPEATS,
        expected_cells=480, expected_runs=1440,
        environment=dict(python=sys.version, numpy=np.__version__, scipy=scipy.__version__, soundfile=sf.__version__),
        purpose='exploratory configuration ablation, not an independent natural-audio qualification',
        quality_selection=None)
    c.json_write(output/'plan.json', plan); return plan


def identity(plan: dict) -> None:
    if plan['profiles'] != list(host.PROFILES) or plan['shifts'] != list(SHIFTS) or plan['blocks'] != list(BLOCKS) or plan['repeats'] != REPEATS:
        raise ValueError('not registered grid')
    expected = {(name, rate) for name in FAMILIES for rate in host.RATES}
    actual = [(s['name'], s['metadata']['rate']) for s in plan['sources']]
    if len(actual) != len(set(actual)) or set(actual) != expected: raise ValueError('input grid mismatch')
    for path, sha in plan['files'].items():
        if c.fingerprint(Path(path)) != sha: raise ValueError('changed source/binary/dependency')
    for s in plan['sources']:
        if c.inspect_audio(Path(s['path'])) != s['audio']: raise ValueError('changed input')


def pcm_hash(path: Path) -> str:
    # Hash decoded stored samples, not WAV's optional timestamp-bearing chunks.
    data, _ = sf.read(path, dtype='float32', always_2d=True)
    if not np.isfinite(data).all(): raise ValueError('nonfinite stored PCM')
    return hashlib.sha256(np.asarray(data, dtype='<f4').tobytes()).hexdigest()


def key(row: dict) -> tuple:
    return tuple(row[k] for k in ('name', 'rate', 'block', 'shift', 'profile', 'repeat'))


def validate_grid(rows: list[dict]) -> None:
    expected = set(itertools.product(FAMILIES, host.RATES, BLOCKS, SHIFTS, host.PROFILES, range(REPEATS)))
    keys = [key(r) for r in rows]
    if len(keys) != len(set(keys)) or set(keys) != expected:
        raise ValueError('missing/duplicate/extra rows; no surviving-subset result')


def assess(rows: list[dict]) -> dict:
    validate_grid(rows)
    if any(r['status'] != 'complete' for r in rows):
        return dict(execution_complete=False, quality_selection=None, profiles=None)
    cells = {}
    for r in rows: cells.setdefault(key(r)[:-1], []).append(r)
    repeats_equal = all(len({r['pcm_sha256'] for r in rr}) == 1 for rr in cells.values())
    wav_equal = all(len({r['audio']['sha256'] for r in rr}) == 1 for rr in cells.values())
    partitions = {}
    for r in rows:
        partitions.setdefault((r['name'], r['rate'], r['shift'], r['profile']), set()).add(r['pcm_sha256'])
    partition_equal = all(len(v) == 1 for v in partitions.values())
    reference = {key(r)[:4]: r for r in rows if r['profile'] == 'default' and r['repeat'] == 0}
    summary = {}; stops = []
    for profile in host.PROFILES:
        selected = [r for r in rows if r['profile'] == profile and r['repeat'] == 0]
        tones = [r for r in selected if r['name'].startswith('tone')]
        clean = lambda r: abs(r['metrics']['pitch_error_cents']) <= 5 and abs(r['metrics']['amplitude_error_db'][0]) <= 1 and r['metrics']['undesired_energy_fraction'] <= .01
        times = [statistics.median(r['native']['host_render_seconds'] for r in rr)
                 for k, rr in cells.items() if k[-1] == profile]
        bursts = [r for r in selected if r['name'] == 'bursts']
        summary[profile] = dict(tone_cells=len(tones), pitch_pass=sum(abs(r['metrics']['pitch_error_cents']) <= 5 for r in tones),
            clean_tone_pass=sum(clean(r) for r in tones), max_abs_pitch_cents=max(abs(r['metrics']['pitch_error_cents']) for r in tones),
            max_abs_amplitude_db=max(abs(r['metrics']['amplitude_error_db'][0]) for r in tones),
            max_undesired_energy=max(r['metrics']['undesired_energy_fraction'] for r in tones),
            max_abs_event_position_ms=max(abs(e['position_error_ms']) for r in bursts for e in r['metrics']['events']),
            max_event_width_ms=max(e['width_ms'] for r in bursts for e in r['metrics']['events']),
            median_of_cell_median_host_seconds=statistics.median(times),
            max_cell_median_host_seconds=max(times))
        if profile == 'long_wide':
            for r in bursts:
                base = reference[key(r)[:4]]
                for i, (a, b) in enumerate(zip(base['metrics']['events'], r['metrics']['events'])):
                    reasons = []
                    if abs(b['position_error_ms']) > abs(a['position_error_ms'])+1: reasons.append('position_increase_gt_1ms')
                    if b['width_ms'] > 1.2*a['width_ms']: reasons.append('width_ratio_gt_1.20')
                    if reasons: stops.append(dict(cell=list(key(r)[:-1]), event=i, reasons=reasons,
                        default_event=a, candidate_event=b))
    return dict(execution_complete=True, repeat_pcm_identical=repeats_equal,
        repeat_wav_identical=wav_equal, partition_pcm_identical=partition_equal,
        profiles=summary, long_wide_transient_stops=stops, quality_selection=None,
        decision='research_only_no_product_promotion',
        timing='fresh handle+Python/native stream+destroy, no WAV IO/measurement; NOT realtime callback timing')


def run(plan_path: Path, plan_sha: str, output: Path) -> dict:
    if c.fingerprint(plan_path) != plan_sha: raise ValueError('plan hash mismatch')
    plan = json.loads(plan_path.read_text()); identity(plan)
    output = output.resolve(); output.mkdir(parents=True, exist_ok=False)
    native = host.Native(Path(plan['library']), plan['files'][plan['library']])
    # First real constructor includes shared resampler initialization; retained separately.
    cold_x, _ = fixture('tone223_phase0', 48000)
    _, cold = native.render(cold_x, 48000, 0, 'default', 64)
    c.json_write(output/'cold.json', cold)
    rows = []
    for source, block, shift, profile in itertools.product(plan['sources'], BLOCKS, SHIFTS, host.PROFILES):
        name, rate = source['name'], source['metadata']['rate']; x, _ = host.read_input(Path(source['path']))
        for repeat in range(REPEATS):
            case = output/f'{name}-{rate}-{block}-{shift:+d}-{profile}-{repeat}'; case.mkdir()
            row = dict(name=name, rate=rate, block=block, shift=shift, profile=profile, repeat=repeat,
                case=str(case.relative_to(output)), status='failed', errors=[])
            c.json_write(case/'started.json', row)
            try:
                y, info = native.render(x, rate, shift, profile, block)
                out = case/'output.wav'; sf.write(out, y, rate, subtype='FLOAT')
                row.update(status='complete', native=info, audio=c.inspect_audio(out),
                           pcm_sha256=pcm_hash(out), metrics=metrics.measure(y, source['metadata'], shift))
            except (ValueError, RuntimeError, OSError) as exc:
                row['status'] = 'failed'; row['errors'].append(str(exc))
            c.json_write(case/'receipt.json', row); rows.append(row)
        if len(rows) % 144 == 0: print(f'{len(rows)}/1440 native renders', flush=True)
    identity(plan)
    result = assess(rows)
    result.update(plan_sha256=plan_sha, rows=rows, run_peak_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    c.json_write(output/'summary.json', result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__); sub = parser.add_subparsers(dest='action', required=True)
    p = sub.add_parser('prepare'); p.add_argument('--library', type=Path, required=True); p.add_argument('--output', type=Path, required=True)
    p = sub.add_parser('run'); p.add_argument('--plan', type=Path, required=True); p.add_argument('--plan-sha256', required=True); p.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.action == 'prepare':
        prepare(args.library, args.output); print(c.fingerprint(args.output/'plan.json')); return 0
    r = run(args.plan, args.plan_sha256, args.output)
    return 0 if r['execution_complete'] and r['repeat_pcm_identical'] and r['partition_pcm_identical'] else 2


if __name__ == '__main__': raise SystemExit(main())
