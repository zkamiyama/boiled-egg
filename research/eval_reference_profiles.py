#!/usr/bin/env python3
"""Exact-grid, reference-only manual-profile diagnostics (not Elastique/MOS).

Reference categories are copied from the supplied MOS catalog's ref_loc. They
are not an audio classifier. No MOS values or processed test renders are used.
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import csv
import json
import math
import re
import subprocess
import tempfile
from collections import defaultdict
from pathlib import Path, PurePosixPath

import numpy as np
import soundfile as sf

from eval_elastique_pitch import metrics
from eval_multires_corpus import checked_audio, fingerprint

PITCHES = (-12, -7, -3, 3, 7, 12)
PROFILES = ('general', 'transient', 'multires')
FORMANTS = ('off', 'harmonic', 'monophonic')
SCHEMA = 'boiled-egg.reference-profiles.v1'


def catalog_categories(path: Path) -> dict[str, str]:
    result = {}
    with path.open(newline='', encoding='utf-8-sig') as stream:
        reader = csv.DictReader(stream)
        if not {'ref_name', 'ref_loc'} <= set(reader.fieldnames or ()):
            raise ValueError('catalog requires ref_name and ref_loc')
        for row in reader:
            name = row['ref_name']
            location = row['ref_loc'].replace('\\', '/').rstrip('/')
            category = PurePosixPath(location).name.lower()
            if not name or Path(name).name != name or '\\' in name or not category:
                raise ValueError('invalid reference catalog entry')
            if name in result and result[name] != category:
                raise ValueError(f'conflicting catalog categories: {name}')
            result[name] = category
    return result


def preflight(ref_dir: Path, catalog: Path) -> list[dict]:
    categories = catalog_categories(catalog)
    paths = sorted(p for p in ref_dir.iterdir() if p.suffix.lower() == '.wav')
    if not paths:
        raise ValueError('no reference WAV files')
    result = []
    for path in paths:
        if path.name not in categories:
            raise ValueError(f'reference absent from supplied catalog: {path.name}')
        x, rate = checked_audio(path)
        info = sf.info(path)
        if not 16000 <= rate <= 384000 or not 1 <= x.shape[1] <= 8:
            raise ValueError(f'unsupported rate/channels: {path}')
        if len(x) < math.ceil(rate * .1):
            raise ValueError(f'reference must be at least 100 ms: {path}')
        if info.format != 'WAV' or info.subtype not in ('PCM_16', 'PCM_24', 'PCM_32', 'FLOAT'):
            raise ValueError(f'unsupported CLI WAV encoding: {path}')
        result.append(dict(stem=path.stem, category=categories[path.name],
                           reference_name=path.name, reference_sha256=fingerprint(path),
                           sample_rate=rate, frames=len(x), channels=x.shape[1]))
    return result


def measure(reference: np.ndarray, audio: np.ndarray, rate: int) -> dict:
    # Evaluate each channel separately: arithmetic downmix hides antiphase audio.
    values = [metrics(reference[:, ch], audio[:, ch], rate)
              for ch in range(reference.shape[1])]
    result = dict(env=float(np.mean([v[0] for v in values])),
                  onset=float(np.mean([v[1] for v in values])),
                  rms=float(np.sqrt(np.mean(audio.astype(np.float64)**2))),
                  peak=float(np.max(np.abs(audio))))
    if not all(math.isfinite(v) for v in result.values()):
        raise ValueError('non-finite objective diagnostic')
    return result


def source_job(job: tuple) -> list[dict]:
    source, record, pv_cli, multires_cli, output, formants, block = job
    reference, rate = checked_audio(source)
    if fingerprint(source) != record['reference_sha256']:
        raise ValueError(f'reference changed after preflight: {source}')
    rows = []
    for pitch in PITCHES:
        ratio = float(np.float32(2.0 ** (pitch/12.0)))
        for formant in formants:
            for profile in PROFILES:
                relative = Path('renders')/source.stem/f'{pitch:+d}st'/formant/f'{profile}.wav'
                destination = output/relative
                destination.parent.mkdir(parents=True, exist_ok=True)
                command = [str(multires_cli if profile == 'multires' else pv_cli),
                           str(source), str(destination), '--time', '1',
                           '--pitch-ratio', format(ratio, '.9g'), '--formant', formant,
                           '--block', str(block)]
                if profile != 'multires':
                    command += ['--mode', 'locked', '--fft', '2048' if profile == 'general' else '1024',
                                '--hop', '256']
                run = subprocess.run(command, capture_output=True, text=True, timeout=120)
                if run.returncode:
                    raise RuntimeError(f'{profile}/{source.name}/{pitch}/{formant}: {run.stderr}')
                audio, out_rate = checked_audio(destination)
                if out_rate != rate or audio.shape != reference.shape:
                    raise ValueError(f'render rate/frame/channel mismatch: {destination}')
                rows.append(dict(**record, pitch_semitones=pitch, control_ratio=ratio,
                                 formant=formant, profile=profile, **measure(reference, audio, rate),
                                 duration_error_frames=0, render_path=relative.as_posix(),
                                 render_sha256=fingerprint(destination)))
    if fingerprint(source) != record['reference_sha256']:
        raise ValueError(f'reference changed during rendering: {source}')
    return rows


def summarize(rows: list[dict], sources: list[dict], formants: list[str]) -> dict:
    expected = {(s['stem'], pitch, mode, profile) for s in sources
                for pitch in PITCHES for mode in formants for profile in PROFILES}
    actual = {}
    for row in rows:
        key = (row['stem'], row['pitch_semitones'], row['formant'], row['profile'])
        if key in actual:
            raise ValueError(f'duplicate render: {key}')
        actual[key] = row
    if not expected or set(actual) != expected:
        raise ValueError('incomplete or unexpected reference-profile grid')
    results = {}
    for mode in formants:
        comparisons = {}
        for profile in ('general', 'multires'):
            pairs = [(actual[(s['stem'], pitch, mode, profile)],
                      actual[(s['stem'], pitch, mode, 'transient')])
                     for s in sources for pitch in PITCHES]
            de = [a['env']-b['env'] for a,b in pairs]
            do = [a['onset']-b['onset'] for a,b in pairs]
            comparisons[profile] = dict(conditions=len(pairs),
                mean_env_delta_vs_transient=float(np.mean(de)),
                mean_onset_delta_vs_transient=float(np.mean(do)),
                env_wins_vs_transient=sum(v < 0 for v in de),
                onset_wins_vs_transient=sum(v > 0 for v in do))
        results[mode] = comparisons
    return dict(renders=len(rows), conditions=len(sources)*len(PITCHES)*len(formants),
                exact_duration_renders=sum(r['duration_error_frames'] == 0 for r in rows),
                max_peak=max(r['peak'] for r in rows), comparisons=results)


def run(args: argparse.Namespace) -> dict:
    if not re.fullmatch(r'[0-9a-fA-F]{40}', args.source_commit):
        raise ValueError('source-commit must be a full 40-character Git commit SHA')
    if args.workers < 1 or not 1 <= args.block <= 16384:
        raise ValueError('workers/block outside supported range')
    if not args.corpus_label.strip() or not args.formants or len(set(args.formants)) != len(args.formants):
        raise ValueError('nonempty corpus label and unique formant modes required')
    if set(args.formants)-set(FORMANTS):
        raise ValueError('unknown formant mode')
    references = args.ref_dir.resolve(strict=True)
    pv = args.pv_cli.resolve(strict=True)
    multires = args.multires_cli.resolve(strict=True)
    sources = preflight(references, args.catalog)
    provenance = dict(schema=SCHEMA, corpus_label=args.corpus_label,
        source_commit=args.source_commit, pv_cli_sha256=fingerprint(pv),
        multires_cli_sha256=fingerprint(multires), catalog_sha256=fingerprint(args.catalog),
        category_policy='copied from catalog ref_loc, not inferred from audio',
        pitch_grid=list(PITCHES), profiles=list(PROFILES), formants=args.formants,
        block=args.block, sources=sources, listening_status='not_listened',
        external_baseline='none', mos_transfer=False,
        metric_policy='existing cepstral envelope/onset diagnostics, averaged per channel')
    output = args.output.resolve()
    if output.exists() and (not output.is_dir() or any(output.iterdir())):
        raise ValueError('output must be absent or empty')
    output.parent.mkdir(parents=True, exist_ok=True)
    # Publish only a complete grid; failures cannot masquerade as final results.
    with tempfile.TemporaryDirectory(prefix='.reference-profiles-', dir=output.parent) as tmp:
        staging = Path(tmp)/'result'
        staging.mkdir()
        jobs = [(references/s['reference_name'], s, pv, multires, staging, args.formants, args.block)
                for s in sources]
        rows = []
        with cf.ProcessPoolExecutor(max_workers=args.workers) as executor:
            for index, result in enumerate(executor.map(source_job, jobs), 1):
                rows.extend(result)
                print(f'source {index}/{len(sources)}', flush=True)
        summary = dict(**provenance, **summarize(rows, sources, args.formants))
        if fingerprint(pv) != provenance['pv_cli_sha256'] or fingerprint(multires) != provenance['multires_cli_sha256']:
            raise ValueError('renderer executable changed during evaluation')
        with (staging/'metrics.csv').open('w', newline='', encoding='utf-8') as stream:
            writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
            writer.writeheader(); writer.writerows(rows)
        summary['metrics_sha256'] = fingerprint(staging/'metrics.csv')
        (staging/'summary.json').write_text(json.dumps(summary, indent=2, allow_nan=False)+'\n')
        if output.exists():
            output.rmdir()  # Refuse replacement if another writer added files.
        staging.rename(output)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('pv-cli', 'multires-cli', 'ref-dir', 'catalog', 'output'):
        parser.add_argument('--'+name, type=Path, required=True)
    parser.add_argument('--source-commit', required=True)
    parser.add_argument('--corpus-label', required=True)
    parser.add_argument('--formants', nargs='+', choices=FORMANTS, default=['harmonic'])
    parser.add_argument('--workers', type=int, default=3)
    parser.add_argument('--block', type=int, default=256)
    summary = run(parser.parse_args())
    print(json.dumps({k:v for k,v in summary.items() if k != 'sources'}, indent=2, allow_nan=False))


if __name__ == '__main__':
    main()
