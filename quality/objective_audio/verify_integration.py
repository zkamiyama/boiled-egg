#!/usr/bin/env python3
"""Exact integration audit, not a quality score or cross-compiler comparison."""
from __future__ import annotations
import argparse
import csv
import hashlib
import itertools
import json
from pathlib import Path

FIELDS = ('rate', 'quality', 'policy', 'realtime', 'pitch', 'family', 'dynamic')


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def source_check(reference, integrated):
    def index(root):
        return {str(p.relative_to(root)): digest(p) for prefix in ('src', 'include')
                for p in sorted((root/prefix).rglob('*')) if p.is_file()}
    before, after = index(reference), index(integrated)
    if not before or set(before) != set(after):
        raise ValueError('source/header coverage mismatch')
    changed = [p for p in before if before[p] != after[p]]
    if changed:
        raise ValueError('integrated source differs from canonical patch chain: '+', '.join(changed))
    return before


def expected_keys():
    static = set(itertools.product((48000, 96000), (0, 1), (0, 1, 2), (0, 1),
                                   (.5, 1., 2.), (0, 1), (0,)))
    dynamic = {(rate, q, p, 1, 1., 1, 1) for rate, q, p in
               itertools.product((48000, 96000), (0, 1), (0, 1, 2))}
    return static | dynamic


def read_replay(path):
    with Path(path).open(newline='') as stream:
        reader = csv.DictReader(stream)
        if reader.fieldnames != [*FIELDS, 'frames', 'hash']:
            raise ValueError('unexpected replay columns')
        result = {}
        for row in reader:
            key = tuple(float(row[k]) if k == 'pitch' else int(row[k]) for k in FIELDS)
            if key in result:
                raise ValueError('duplicate replay cell')
            frames, fingerprint = int(row['frames']), int(row['hash'])
            if frames <= 0 or not 0 <= fingerprint < 2**64:
                raise ValueError('invalid replay metadata')
            result[key] = (frames, fingerprint)
    if set(result) != expected_keys():
        raise ValueError('incomplete or unexpected replay grid')
    return result


def compare_replays(reference, integrated):
    a, b = read_replay(reference), read_replay(integrated)
    if a != b:
        raise ValueError('same-toolchain output history changed')
    return dict(static_pairs=144, dynamic_pairs=12, total_pairs=len(a))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('reference_source', 'integrated_source', 'reference_csv', 'integrated_csv', 'output'):
        p.add_argument('--'+name.replace('_', '-'), type=Path, required=True)
    a = p.parse_args()
    if a.output.exists():
        raise ValueError('new output required')
    sources = source_check(a.reference_source, a.integrated_source)
    result = dict(schema='boiled-egg.static-stereo-integration.v1',
                  **compare_replays(a.reference_csv, a.integrated_csv),
                  source_files=len(sources), source_sha256=sources,
                  reference_csv_sha256=digest(a.reference_csv),
                  integrated_csv_sha256=digest(a.integrated_csv),
                  verifier_sha256=digest(__file__),
                  notes='Same-toolchain exact hashes plus canonical source equality; '
                        'not perceptual equivalence or new quality evidence.')
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(json.dumps(result, indent=2)+'\n')
    print(result['total_pairs'], 'complete replay pairs;', len(sources), 'source/header files identical')


if __name__ == '__main__':
    main()
