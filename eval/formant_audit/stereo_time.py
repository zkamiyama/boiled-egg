#!/usr/bin/env python3
"""Roadmap B: linked-stereo invariants and unfitted local-time diagnostics.

Reuse the named formant panel, not its analytical oracle or any eligibility flag.
Raw outputs and failed receipts remain. No alignment/gain correction is applied.
"""
from __future__ import annotations
import argparse
import csv
import json
from pathlib import Path
import sys
import numpy as np
import soundfile as sf

# Both CLI and local unittest discovery resolve the neighboring, trusted study.
import study as audit
c = audit.c
OPERATIONS = ((1., 0.), (.9, 0.), (1.1, 0.), (1., -7.), (1., 7.))
FIXTURES = ('proportional', 'silent_right', 'bursts', 'bursts_swapped')
EVENTS = ((.30, 0), (.75, 1), (1.20, 0), (1.65, 1))
THRESHOLD = 1e-5


def fixture(name: str, rate: int) -> np.ndarray:
    if name not in FIXTURES or rate not in (48000, 96000):
        raise ValueError('declared fixture/rate required')
    n = 2 * rate
    if name in ('proportional', 'silent_right'):
        t = np.arange(n) / rate
        rng = np.random.default_rng(260916)
        left = (.10 * np.sin(2*np.pi*173*t) + .04 * np.sin(2*np.pi*1613*t)
                + .008 * rng.standard_normal(n))
        right = -.375 * left if name == 'proportional' else np.zeros(n)
        return np.c_[left, right].astype('float32')
    result = np.zeros((n, 2))
    width = round(.004 * rate)
    t = (np.arange(width) - width // 2) / rate
    gate = np.sin(np.pi * np.arange(width) / width)**2
    pulse = gate * sum(.07*np.cos(2*np.pi*f*t) for f in (701., 2303., 5003.))
    for center, channel in EVENTS:
        start = round(center*rate) - width//2
        result[start:start+width, channel] = pulse
    if name == 'bursts_swapped':
        result = result[:, ::-1]
    return np.ascontiguousarray(result, dtype='float32')


def waveform(audio: np.ndarray) -> np.ndarray:
    x = np.asarray(audio, dtype=float)
    if x.ndim != 2 or x.shape[1] != 2 or len(x) < 1 or not np.isfinite(x).all():
        raise ValueError('nonempty finite stereo required')
    return x


def relation_error(audio: np.ndarray, gain: float) -> float:
    x = waveform(audio)
    energy = float(np.sum(x[:, 0]**2))
    if energy <= 1e-20:
        raise ValueError('zero reference-channel output is not stereo success')
    return float(np.sqrt(np.sum((x[:, 1] - gain*x[:, 0])**2) / energy))


def permutation_error(normal: np.ndarray, swapped: np.ndarray) -> float:
    x, y = waveform(normal), waveform(swapped)
    if x.shape != y.shape:
        raise ValueError('channel-exchange shapes differ')
    power = float(np.sum(x*x))
    if power <= 1e-20:
        raise ValueError('zero output is not channel-exchange success')
    return float(np.sqrt(np.sum((y[:, ::-1] - x)**2) / power))


def placements(audio: np.ndarray, rate: int, duration: float, swapped: bool = False) -> list[dict]:
    x = waveform(audio)
    if rate not in (48000, 96000) or not np.isfinite(duration) or not .5 <= duration <= 2:
        raise ValueError('rate/duration outside protocol')
    rows = []
    for center, original_channel in EVENTS:
        channel = 1-original_channel if swapped else original_channel
        target = center * duration * rate
        lo = max(0, int(np.floor(target - .08*rate)))
        hi = min(len(x), int(np.ceil(target + .08*rate)))
        power = x[lo:hi, channel]**2
        total = float(np.sum(power))
        if total <= 1e-20:
            raise ValueError('no measurable event inside prescribed window')
        samples = np.arange(lo, hi, dtype=float)
        centroid = float(np.dot(samples, power) / total)
        # Quantiles are measured locations, never offsets fitted back into audio.
        quantiles = np.interp([.05, .95], np.cumsum(power)/total, samples)
        rows.append(dict(input_center_seconds=center, output_channel=channel,
                         expected_center_sample=target, measured_center_sample=centroid,
                         signed_error_samples=centroid-target,
                         width_5_95_ms=float((quantiles[1]-quantiles[0])*1000/rate),
                         captured_energy=total,
                         opposite_channel_energy_ratio=float(np.sum(x[lo:hi, 1-channel]**2)/total)))
    return rows


def validate_grid(rows: list[dict], expected: set[tuple]) -> None:
    keys = [(r['rate'], r['operation'], r['fixture'], r['engine']) for r in rows]
    if len(keys) != len(set(keys)) or set(keys) != expected:
        raise ValueError('incomplete/duplicate/unexpected stereo-time grid')
    for row in rows:
        if any(isinstance(v, float) and not np.isfinite(v) for v in row.values()):
            raise ValueError('nonfinite scalar measurement')


def run(args) -> dict:
    if args.output.exists() or not args.rates or len(set(args.rates)) != len(args.rates):
        raise ValueError('new output and unique rates required')
    if not set(args.rates) <= {48000, 96000}:
        raise ValueError('undeclared rate')
    configs = audit.configurations(args.spectral, args.reference)
    probes = audit.probes(configs)
    files = {p:h for probe in probes.values() for p,h in probe['files'].items()}
    for module in (audit, audit.m, audit.c, audit.e, sys.modules['reference_rubberband'], sys.modules[__name__]):
        path = Path(module.__file__).resolve(); files[str(path)] = c.fingerprint(path)
    args.output.mkdir(parents=True); (args.output/'sources').mkdir()
    plan = dict(schema='boiled-egg.stereo-time-plan.v1', candidates=probes, files=files,
                rates=args.rates, operations=OPERATIONS, fixtures=FIXTURES,
                relation_threshold=THRESHOLD, seconds=2., timing_window_seconds=.08,
                timing_quality_threshold=None, grants_listening_eligibility=False,
                native_zplane=False, notes='Offline output time, no fitted latency or gain.')
    c.json_write(args.output/'plan.json', plan)
    expected = {(r, o, f, cfg['name']) for r in args.rates for o in range(len(OPERATIONS))
                for f in FIXTURES for cfg in configs}
    rows = []; exchanges = []; sources = {}
    for rate in args.rates:
        for name in FIXTURES:
            source = args.output/'sources'/f'{rate}-{name}.wav'
            sf.write(source, fixture(name, rate), rate, subtype='FLOAT')
            sources[str(source.resolve())] = c.fingerprint(source)
        for operation, (duration, pitch) in enumerate(OPERATIONS):
            request = c.Request.from_semitones(duration, pitch)
            for cfg in configs:
                pair = {}
                for name in FIXTURES:
                    key = audit.e.digest([rate, operation, name, cfg])
                    case = args.output/'cases'/key
                    receipt = audit.render(cfg, probes[cfg['name']],
                                           args.output/'sources'/f'{rate}-{name}.wav', request, case)
                    row = dict(rate=rate, operation=operation, duration_ratio=duration,
                               pitch_semitones=pitch, fixture=name, engine=cfg['name'],
                               policy=cfg['formant'], case=str(case.relative_to(args.output)),
                               receipt_sha256=c.fingerprint(case/'receipt.json'),
                               metadata_passed=receipt['status']=='passed',
                               errors=list(receipt['errors']))
                    if row['metadata_passed']:
                        y, sr = sf.read(case/'output.wav', dtype='float64', always_2d=True)
                        row['output_sha256'] = c.fingerprint(case/'output.wav')
                        try:
                            if name in ('proportional', 'silent_right'):
                                row['relation_error'] = relation_error(y, -.375 if name=='proportional' else 0.)
                                row['relation_passed'] = row['relation_error'] <= THRESHOLD
                            else:
                                detail = placements(y, sr, duration, name=='bursts_swapped')
                                c.json_write(case/'event_locations.json', detail)
                                row['events_sha256'] = c.fingerprint(case/'event_locations.json')
                                row['max_abs_event_error_ms'] = max(abs(d['signed_error_samples'])*1000/rate for d in detail)
                                row['mean_abs_event_error_ms'] = float(np.mean([abs(d['signed_error_samples'])*1000/rate for d in detail]))
                                row['max_width_ms'] = max(d['width_5_95_ms'] for d in detail)
                                pair[name] = y
                        except ValueError as exc:
                            row['errors'].append(str(exc))
                    c.json_write(case/'measurement.json', row); rows.append(row)
                item = dict(rate=rate, operation=operation, engine=cfg['name'], passed=False)
                if set(pair) == {'bursts', 'bursts_swapped'}:
                    item['relative_error'] = permutation_error(pair['bursts'], pair['bursts_swapped'])
                    item['passed'] = item['relative_error'] <= THRESHOLD
                exchanges.append(item)
            print('stereo/time', rate, operation, 'rows', len(rows), flush=True)
    validate_grid(rows, expected)
    for p,h in {**files, **sources}.items():
        if c.fingerprint(Path(p)) != h:
            raise ValueError('source/engine/analysis changed; report not completed')
    c.json_write(args.output/'rows.json', rows)
    c.json_write(args.output/'channel_exchange.json', exchanges)
    with (args.output/'measurements.csv').open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=sorted(set().union(*(r.keys() for r in rows))))
        writer.writeheader(); writer.writerows(rows)
    relation = [r for r in rows if r['fixture'] in ('proportional', 'silent_right')]
    result = dict(schema='boiled-egg.stereo-time-results.v1', outputs=len(rows),
                  metadata_passed=sum(r['metadata_passed'] for r in rows),
                  measurement_errors=sum(bool(r['errors']) for r in rows),
                  relation_cases=len(relation), relation_passed=sum(r.get('relation_passed', False) for r in relation),
                  channel_exchange_cases=len(exchanges), channel_exchange_passed=sum(r['passed'] for r in exchanges),
                  plan_sha256=c.fingerprint(args.output/'plan.json'),
                  rows_sha256=c.fingerprint(args.output/'rows.json'),
                  measurements_sha256=c.fingerprint(args.output/'measurements.csv'),
                  channel_exchange_sha256=c.fingerprint(args.output/'channel_exchange.json'),
                  sources=sources, timing_quality_threshold=None, quality_selection=None,
                  listening_responses=0, grants_listening_eligibility=False,
                  notes='Limited deterministic stereo/placement diagnostics, not full alignment, '
                        'perceptual stereo, natural formants or realtime/native-zplane qualification.')
    c.json_write(args.output/'summary.json', result)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--spectral', type=Path)
    parser.add_argument('--reference', type=Path)
    parser.add_argument('--rates', type=int, nargs='+', choices=(48000, 96000), default=[48000, 96000])
    parser.add_argument('--output', type=Path, required=True)
    result = run(parser.parse_args())
    print(json.dumps(result, indent=2))
    # Do not hide invariant failures; they are distinct from descriptive timings.
    raise SystemExit(not (result['metadata_passed']==result['outputs'] and not result['measurement_errors']
                          and result['relation_passed']==result['relation_cases']
                          and result['channel_exchange_passed']==result['channel_exchange_cases']))
