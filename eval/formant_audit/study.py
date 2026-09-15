#!/usr/bin/env python3
"""Roadmap B: fixed analytical formant comparison; never authorizes a blind panel.

Failed outputs/receipts remain in the journal. No trim, padding, fitted alignment,
limiting or output normalization. The Rubber Band binary is evaluation-only.
"""
from __future__ import annotations
import argparse
from dataclasses import asdict
import json
from pathlib import Path
import sys
import tempfile
import csv
import numpy as np
import soundfile as sf

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import comparison_contract as c
import candidate_evidence as e
from reference_rubberband import Reference
import metrics as m


def configurations(spectral: Path | None, reference: Path | None) -> list[dict]:
    configs = []
    if spectral is not None:
        configs += [dict(name=f'pv_{q}_{f}', kind='spectral', path=str(spectral.resolve(strict=True)),
                         quality=q, formant=f, block=32)
                    for q in ('general', 'transient') for f in ('off', 'harmonic', 'monophonic')]
    if reference is not None:
        configs += [dict(name=f'r3_{f}', kind='rubberband_direct', path=str(reference.resolve(strict=True)),
                         quality='general', formant=f, block=4096, generation=3)
                    for f in ('off', 'preserved')]
    if not configs:
        raise ValueError('at least one explicitly supplied engine required')
    return configs


def probes(configs: list[dict]) -> dict:
    result = {}
    for cfg in configs:
        if cfg['kind'] == 'spectral':
            engine = c.Engine(cfg['name'], 'spectral', cfg['path'], cfg['quality'], cfg['formant'], cfg['block'])
            backend = engine.probe()
            files = {backend['executable']: backend['sha256'], **backend['dependencies']}
        else:
            # Reuse the dependency probe only, not the Off-only eligibility API.
            dependency = e.Candidate('r3_probe', 'rubberband_direct', cfg['path'], block=cfg['block']).probe()
            backend = dict(library=cfg['path'], mode='offline-study-and-process', generation=3,
                           formant=cfg['formant'], note='dependency probe only; no inherited eligibility')
            files = dependency['files']
        result[cfg['name']] = dict(config=cfg, backend=backend, files=files)
    return result


def render(cfg: dict, probe: dict, source: Path, request: c.Request, case: Path) -> dict:
    if cfg['kind'] == 'spectral':
        engine = c.Engine(cfg['name'], 'spectral', cfg['path'], cfg['quality'], cfg['formant'], cfg['block'])
        return c.render_case(engine, probe['backend'], source, request, case)
    case.mkdir(parents=True, exist_ok=False)
    receipt = dict(engine=cfg['name'], request=asdict(request), config=cfg,
                   status='failed', errors=[], output=None)
    c.json_write(case / 'started.json', receipt)
    try:
        before = c.inspect_audio(source)
        receipt['source_metadata'] = before
        x, rate = sf.read(source, dtype='float32', always_2d=True)
        y, details = Reference(Path(cfg['path'])).render(x, rate, request, 3, cfg['formant'], cfg['block'])
        sf.write(case / 'output.wav', y, rate, subtype='FLOAT')
        actual = c.inspect_audio(case / 'output.wav')
        receipt.update(output=actual, details=details, raw_output_sha256=actual['sha256'])
        receipt['errors'] += c.output_checks(before, actual, request)
        if c.fingerprint(source) != before['sha256']:
            receipt['errors'].append('source changed')
    except (RuntimeError, ValueError, OSError) as exc:
        receipt['errors'].append(f'{type(exc).__name__}: {exc}')
    receipt['status'] = 'failed' if receipt['errors'] else 'passed'
    c.json_write(case / 'receipt.json', receipt)
    return receipt


def validate_grid(rows: list[dict], expected: set[tuple]) -> None:
    keys = [(r['rate'], r['f0'], r['contour'], r['shift'], r['engine']) for r in rows]
    if len(keys) != len(set(keys)) or set(keys) != expected:
        raise ValueError('incomplete or duplicated formant grid')
    for row in rows:
        if any(not np.isfinite(v) for v in row.values() if isinstance(v, float)):
            raise ValueError('nonfinite measurement')


def run(args) -> dict:
    if args.output.exists():
        raise ValueError('new output required')
    cfgs = configurations(args.spectral, args.reference)
    identity = probes(cfgs)
    files = {path: digest for probe in identity.values() for path, digest in probe['files'].items()}
    for module in (c, e, m, sys.modules['reference_rubberband']):
        p = Path(module.__file__).resolve(); files[str(p)] = c.fingerprint(p)
    files[str(Path(__file__).resolve())] = c.fingerprint(Path(__file__))
    args.output.mkdir(parents=True)
    sources = args.output / 'sources'; sources.mkdir()
    manifest = dict(schema='boiled-egg.formant-audit.v1', candidates=identity, files=files,
                    rates=args.rates, shifts=m.SHIFTS, contours=m.CONTOURS, fundamentals=m.FUNDAMENTALS,
                    mode='offline-mono-constant-pitch', seconds=2, steady_interval=[.25, 1.75],
                    hypothesis='preserve fixed filter while changing harmonic excitation pitch',
                    quality_gate=None, grants_listening_eligibility=False, native_zplane=False)
    c.json_write(args.output / 'plan.json', manifest)
    rows = []; source_hashes = {}
    expected = {(rate, f0, contour, shift, cfg['name']) for rate in args.rates
                for f0 in m.FUNDAMENTALS for contour in m.CONTOURS for shift in m.SHIFTS for cfg in cfgs}
    for rate in args.rates:
        for f0 in m.FUNDAMENTALS:
            for contour in m.CONTOURS:
                source = sources / f'{rate}-{int(f0)}-{contour}.wav'
                sf.write(source, m.fixture(rate, f0, contour), rate, subtype='FLOAT')
                source_hashes[str(source)] = c.fingerprint(source)
                for shift in m.SHIFTS:
                    request = c.Request.from_semitones(1, shift)
                    for cfg in cfgs:
                        key = e.digest([rate, f0, contour, shift, cfg])
                        case = args.output / 'cases' / key
                        receipt = render(cfg, identity[cfg['name']], source, request, case)
                        row = dict(rate=rate, f0=f0, contour=contour, shift=shift, engine=cfg['name'],
                                   policy=cfg['formant'], case=str(case.relative_to(args.output)),
                                   receipt_sha256=c.fingerprint(case / 'receipt.json'),
                                   status=receipt['status'], errors=list(receipt['errors']))
                        if receipt['status'] == 'passed':
                            audio, sr = sf.read(case / 'output.wav', dtype='float64', always_2d=True)
                            try:
                                row.update(m.measure(audio, sr, f0, contour, request.pitch_ratio,
                                                     cfg['formant'] != 'off'))
                            except ValueError as exc:
                                row['status'] = 'failed'; row['errors'].append(str(exc))
                        c.json_write(case / 'measurement.json', row); rows.append(row)
                print('formant group', rate, f0, contour, 'rows', len(rows), flush=True)
    validate_grid(rows, expected)
    for p, digest in {**files, **source_hashes}.items():
        if c.fingerprint(Path(p)) != digest:
            raise ValueError('input/engine/analysis changed; no completed report')
    c.json_write(args.output / 'rows.json', rows)
    with (args.output / 'measurements.csv').open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=sorted(set().union(*(r.keys() for r in rows))))
        writer.writeheader(); writer.writerows(rows)
    means = []
    for cfg in cfgs:
        for rate in args.rates:
            group = [r for r in rows if r['engine'] == cfg['name'] and r['rate'] == rate]
            good = [r for r in group if r['status'] == 'passed']
            means.append(dict(engine=cfg['name'], policy=cfg['formant'], rate=rate, conditions=len(group),
                              valid=len(good), **{key:float(np.mean([r[key] for r in good])) if good else None
                                                for key in ('target_contour_rmse_db', 'retained_contour_rmse_db',
                                                            'mean_partial_gain_db', 'out_of_harmonic_power_fraction')},
                              max_peak=max((r['peak'] for r in good), default=None)))
    result = dict(schema='boiled-egg.formant-audit-results.v1', outputs=len(rows),
                  metadata_and_measurements_passed=all(r['status'] == 'passed' for r in rows),
                  plan_sha256=c.fingerprint(args.output/'plan.json'),
                  rows_sha256=c.fingerprint(args.output/'rows.json'),
                  measurements_sha256=c.fingerprint(args.output/'measurements.csv'), sources=source_hashes,
                  means=means, quality_selection=None, listening_responses=0,
                  notes='Fixed analytical mono steady-state grid, not natural voice/polyphony, '
                        'stereo or alignment qualification. Ideal target differs for Off and preserved; '
                        'retained_contour is the shared preservation diagnostic. No native zplane or promotion.')
    c.json_write(args.output / 'summary.json', result)
    return result


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--spectral', type=Path)
    p.add_argument('--reference', type=Path)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--rates', type=int, nargs='+', choices=(48000,96000), default=[48000,96000])
    args = p.parse_args()
    if len(args.rates) != len(set(args.rates)):
        p.error('duplicate rates')
    report = run(args)
    print(report['outputs'], 'outputs; metadata/measurement pass:', report['metadata_and_measurements_passed'])
    raise SystemExit(not report['metadata_and_measurements_passed'])
