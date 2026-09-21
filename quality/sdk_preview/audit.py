#!/usr/bin/env python3
"""Fail-closed SDK extraction and old-binary compatibility, not a MOS test.

The clients are compiled once using the old headers/library. The exact same
executables then run with original/OFF/ON libraries. The donor is independent
from stable main; its preview histories are compared separately.
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import itertools
import json
import os
from pathlib import Path
import platform
import subprocess
import tempfile

C_KEYS = ('rate', 'channels', 'quality', 'io', 'scenario', 'block')
CPP_KEYS = ('rate', 'quality')
PREVIEW_KEYS = ('rate', 'quality', 'policy', 'realtime', 'pitch', 'family', 'dynamic')
RATES = (44100, 48000, 88200, 96000)
ADDITIONS = frozenset(('boiledegg_set_formant_ratio', 'boiledegg_set_formant_semitones',
    'boiledegg_get_formant_ratio', 'boiledegg_get_backend_parameter_state',
    'boiledegg_set_backend_parameter_state', 'boiledegg_process_realtime_ramps',
    'boiledegg_push_ramps', 'boiledegg_get_automation_info'))


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def directory(root: Path, prefix: str) -> dict[str, str]:
    return {str(p.relative_to(root)): sha(p) for p in sorted((root / prefix).rglob('*')) if p.is_file()}


def source_contract(main: Path, donor: Path, current: Path, host_reference: Path | None = None) -> dict:
    protected = {}
    for prefix in ('adapters', 'eval', 'research'):
        # C1 defaults to the original adapters. C2 supplies a separately pinned,
        # reviewed host snapshot; this is exact equality, not a wildcard waiver.
        expected = directory(host_reference if prefix == 'adapters' and host_reference is not None else main, prefix)
        if not expected or expected != directory(current, prefix):
            raise ValueError(f'protected {prefix} tree changed')
        protected.update(expected)
    for name in ('include/boiled_egg/boiled_egg.h', 'src/engine.cpp', 'src/engine.hpp', 'src/profile.cpp'):
        if sha(main / name) != sha(current / name):
            raise ValueError(f'legacy source changed: {name}')
        protected[name] = sha(main / name)
    runtime = {**directory(donor, 'src'), **directory(donor, 'include')}
    if not runtime or runtime != {**directory(current, 'src'), **directory(current, 'include')}:
        raise ValueError('SDK differs from validated donor; not an extraction-only change')
    return dict(protected_sha256=protected, donor_runtime_sha256=runtime,
                protected_files=len(protected), runtime_files=len(runtime))



def packaging_source_contract(main: Path, donor: Path, current: Path,
                              reference: Path, host_reference: Path | None = None) -> dict:
    """Exact, separately pinned post-C1 maintenance scope; no generic exclusions.

    The reference must still contain the validated donor runtime. Only the exact
    Windows static export-macro addition is allowed in the candidate's runtime.
    The original extraction-only source_contract is intentionally unchanged.
    """
    runtime = {**directory(donor, 'src'), **directory(donor, 'include')}
    if not runtime or runtime != {**directory(reference, 'src'), **directory(reference, 'include')}:
        raise ValueError('package reference differs from validated donor runtime')
    protected = {}
    for prefix in ('adapters', 'eval', 'research'):
        expected_files = directory(reference, prefix)
        if not expected_files or expected_files != directory(current, prefix):
            raise ValueError(f'protected package {prefix} tree changed')
        protected.update(expected_files)
    if host_reference is not None and directory(reference, 'adapters') != directory(host_reference, 'adapters'):
        raise ValueError('package reference differs from reviewed host snapshot')
    for name in ('include/boiled_egg/boiled_egg.h', 'src/engine.cpp', 'src/engine.hpp', 'src/profile.cpp'):
        if sha(main / name) != sha(reference / name):
            raise ValueError(f'legacy package reference changed: {name}')
    header = 'include/boiled_egg/boiled_egg.h'
    original = (reference / header).read_bytes()
    before = b'#if defined(_WIN32)\n  #if defined(BOILED_EGG_BUILDING_LIBRARY)'
    after = (b'#if defined(_WIN32)\n  #if defined(BOILED_EGG_STATIC)\n'
             b'    #define BOILEDEGG_API\n  #elif defined(BOILED_EGG_BUILDING_LIBRARY)')
    if original.count(before) != 1:
        raise ValueError('unknown reference export macro')
    expected_runtime = dict(runtime)
    expected_runtime[header] = hashlib.sha256(original.replace(before, after, 1)).hexdigest()
    if expected_runtime != {**directory(current, 'src'), **directory(current, 'include')}:
        raise ValueError('package runtime differs beyond exact static export macro')
    protected.update(expected_runtime)
    return dict(protected_sha256=protected, donor_runtime_sha256=runtime,
                protected_files=len(protected), runtime_files=len(runtime),
                source_profile='pinned-package-static-export-v1',
                allowed_runtime_change={header: dict(before=runtime[header], after=expected_runtime[header])})

def expected(kind: str) -> set[tuple]:
    if kind == 'c':
        return set(itertools.product(RATES, (1, 2), (0, 1, 2), (0, 1), (0, 1, 2), (32, 257)))
    if kind == 'cpp':
        return set(itertools.product(RATES, (0, 1, 2)))
    static = set(itertools.product((48000, 96000), (0, 1), (0, 1, 2), (0, 1), (.5, 1., 2.), (0, 1), (0,)))
    return static | {(r, q, p, 1, 1., 1, 1) for r, q, p in itertools.product((48000, 96000), (0, 1), (0, 1, 2))}


def read_grid(path: Path, kind: str) -> dict[tuple, tuple]:
    keys, values = {'c': (C_KEYS, ('frames', 'audio_hash', 'metadata_hash')),
                    'cpp': (CPP_KEYS, ('frames', 'audio_hash', 'latency', 'capabilities')),
                    'preview': (PREVIEW_KEYS, ('frames', 'hash'))}[kind]
    result = {}
    with path.open(newline='') as stream:
        reader = csv.DictReader(stream)
        if reader.fieldnames != [*keys, *values]:
            raise ValueError('unexpected CSV columns')
        for row in reader:
            if None in row or any(v is None for v in row.values()):
                raise ValueError('ragged CSV')
            key = tuple(float(row[k]) if k == 'pitch' else int(row[k]) for k in keys)
            val = tuple(int(row[k]) for k in values)
            if key in result or val[0] <= 0 or any(v < 0 or v >= 2**64 for v in val):
                raise ValueError('duplicate cell or invalid values')
            result[key] = val
    if set(result) != expected(kind):
        raise ValueError('incomplete or unexpected grid')
    return result


def compare(a: Path, b: Path, kind: str) -> int:
    before, after = read_grid(a, kind), read_grid(b, kind)
    if before != after:
        raise ValueError(f'{kind} output/contract changed')
    return len(before)


def exports(lib: Path) -> set[str]:
    text = subprocess.run(['nm', '-D', '--defined-only', str(lib)], check=True,
                          text=True, capture_output=True, timeout=30).stdout
    return {line.split()[-1] for line in text.splitlines() if line.split()}


def export_contract(original: set[str], candidate: set[str]) -> None:
    if not original or not original <= candidate:
        raise ValueError('legacy export removed')
    if candidate - original != ADDITIONS:
        raise ValueError('unexpected/missing public exports')
    if any(not name.startswith('boiledegg_') or name.startswith(('boiledegg_private_', 'boiledegg_research_')) for name in candidate):
        raise ValueError('private/C++ export leak')


def execute(client: Path, lib: Path, path: Path) -> None:
    env = dict(os.environ, LD_LIBRARY_PATH=str(lib.parent))
    # Verify which SDK the loader will resolve; a misleading rpath must not pass.
    linked = subprocess.run(['ldd', str(client)], check=True, text=True,
                            capture_output=True, env=env, timeout=30).stdout
    resolved = [line.split('=>', 1)[1].split()[0] for line in linked.splitlines()
                if line.strip().startswith('libboiled_egg.so ') and '=>' in line]
    if len(resolved) != 1 or Path(resolved[0]).resolve() != lib.resolve():
        raise ValueError('client did not resolve the declared SDK library')
    path.with_suffix('.ldd.txt').write_text(linked)
    with path.open('w') as stream, path.with_suffix('.stderr.txt').open('w') as errors:
        subprocess.run([str(client)], check=True, stdout=stream, stderr=errors, env=env, timeout=180)


def run(args) -> dict:
    if args.output.exists():
        raise ValueError('new output directory required')
    base, donor, current = (p.resolve(strict=True) for p in (args.baseline_source, args.donor_source, args.source))
    libraries = dict(original=args.original_library.resolve(strict=True),
                     off=args.off_library.resolve(strict=True), on=args.on_library.resolve(strict=True))
    clients = dict(c=args.c_client.resolve(strict=True), cpp=args.cpp_client.resolve(strict=True))
    files = {str(p): sha(p) for p in [*libraries.values(), *clients.values(), args.donor_replay, args.candidate_replay, Path(__file__)]}
    host_reference = getattr(args, 'host_reference_source', None)
    if host_reference is not None:
        host_reference = host_reference.resolve(strict=True)
    package_reference = getattr(args, 'package_reference_source', None)
    if package_reference is not None:
        package_reference = package_reference.resolve(strict=True)
    def checked_scope():
        if package_reference is not None:
            return packaging_source_contract(base, donor, current, package_reference, host_reference)
        return source_contract(base, donor, current, host_reference)
    scope = checked_scope()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    # An interrupted/failed run retains evidence, but cannot publish summary.json.
    args.output.mkdir()
    (args.output / 'plan.json').write_text(json.dumps(dict(files=files, sources=scope, python=platform.python_version()), indent=2)+'\n')
    before = exports(libraries['original'])
    export_sets = {}
    for role in ('off', 'on'):
        export_sets[role] = exports(libraries[role]); export_contract(before, export_sets[role])
    counts = {}
    for kind, client in clients.items():
        for role, lib in libraries.items():
            execute(client, lib, args.output / f'{kind}-{role}.csv')
        counts[kind] = {role: compare(args.output / f'{kind}-original.csv', args.output / f'{kind}-{role}.csv', kind)
                        for role in ('off', 'on')}
    records = read_grid(args.output / 'c-original.csv', 'c')
    for key, values in records.items():
        if key[-1] == 32 and values != records[(*key[:-1], 257)]:
            raise ValueError('legacy block partition changed')
    preview_count = compare(args.donor_replay, args.candidate_replay, 'preview')
    if scope != checked_scope():
        raise ValueError('sources changed during run')
    for name, digest in files.items():
        if sha(Path(name)) != digest:
            raise ValueError('input binary/evidence changed during run')
    report = dict(schema='boiled-egg.sdk-preview-compatibility.v1', **scope,
                  legacy_pairs=counts, legacy_partition_pairs=144, preview_pairs=preview_count,
                  previous_exports=sorted(before), added_exports=sorted(ADDITIONS), files=files,
                  evidence_sha256={p.name: sha(p) for p in args.output.iterdir() if p.is_file()},
                  model_predictions=0, listener_responses=0,
                  notes='Same old executables run unchanged against three libraries. '
                        'Exact functional/ABI compatibility under tested operations, not an acoustic promotion.')
    (args.output / 'summary.json').write_text(json.dumps(report, indent=2)+'\n')
    return report


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('baseline-source', 'donor-source', 'source', 'original-library', 'off-library',
                 'on-library', 'c-client', 'cpp-client', 'donor-replay', 'candidate-replay', 'output'):
        p.add_argument('--'+name, type=Path, required=True)
    p.add_argument('--host-reference-source', type=Path, help='Explicit reviewed C2 adapter snapshot; default retains C1 main-adapter equality')
    p.add_argument('--package-reference-source', type=Path, help='Explicit pinned post-C1 source; permits only the exact static export macro change')
    r = run(p.parse_args()); print(json.dumps({k:r[k] for k in ('legacy_pairs', 'preview_pairs', 'runtime_files', 'protected_files')}))
