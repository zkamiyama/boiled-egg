#!/usr/bin/env python3
"""Audit supplied Roberts/Paliwal archives without extraction or fuzzy joins.

Readiness is based on exact MOS test_name -> ref_name pairs, not ZIP names or
file counts. MOS labels are never transferred to derived pitch renders.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import stat
import zipfile
from collections import Counter, defaultdict
from pathlib import Path, PurePosixPath

import soundfile as sf


def fingerprint(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1048576), b''):
            digest.update(block)
    return digest.hexdigest()


def audio_inventory(path: Path) -> dict[str, dict]:
    """Inspect WAV headers in-place; ambiguous basenames are never guessed."""
    result: dict[str, dict] = {}
    seen: set[str] = set()
    with zipfile.ZipFile(path) as archive:
        for item in archive.infolist():
            member = PurePosixPath(item.filename)
            if (member.is_absolute() or '..' in member.parts or
                    '\\' in item.filename or ':' in item.filename or
                    stat.S_ISLNK(item.external_attr >> 16)):
                raise ValueError(f'unsafe ZIP member: {item.filename}')
            if item.is_dir() or member.suffix.lower() not in {'.wav', '.wave'}:
                continue
            name = member.name
            if name.casefold() in seen:
                raise ValueError(f'ambiguous audio basename: {name}')
            seen.add(name.casefold())
            with archive.open(item) as stream:
                info = sf.info(stream)
            if info.frames <= 0 or info.samplerate <= 0 or info.channels <= 0:
                raise ValueError(f'empty/invalid WAV: {name}')
            result[name] = dict(member=item.filename, frames=info.frames,
                                sample_rate=info.samplerate, channels=info.channels)
    if not result:
        raise ValueError(f'no WAV files: {path}')
    return result


def score_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline='', encoding='utf-8-sig') as stream:
        reader = csv.DictReader(stream)
        required = {'test_name', 'ref_name', 'ref_loc', 'method', 'TSM', 'MeanOS'}
        if not required <= set(reader.fieldnames or []):
            raise ValueError(f'missing MOS columns: {sorted(required-set(reader.fieldnames or []))}')
        rows = list(reader)
    if not rows:
        raise ValueError('empty MOS CSV')
    seen: set[str] = set()
    for row in rows:
        for field in ('test_name', 'ref_name'):
            name = row[field]
            if (not name or name in {'.', '..'} or '/' in name or
                    '\\' in name or ':' in name):
                raise ValueError(f'invalid {field}: {name!r}')
        if row['test_name'] in seen:
            raise ValueError(f'duplicate MOS test_name: {row["test_name"]}')
        seen.add(row['test_name'])
        if not row['method'] or not row['ref_loc']:
            raise ValueError('empty MOS method/reference location')
        for field in ('TSM', 'MeanOS'):
            value = float(row[field])
            if not math.isfinite(value) or (field == 'TSM' and value <= 0):
                raise ValueError(f'invalid MOS {field}: {row[field]}')
    return rows


def audit(ref_zip: Path, test_zip: Path, scores: Path) -> dict:
    references, processed = audio_inventory(ref_zip), audio_inventory(test_zip)
    rows = score_rows(scores)
    index = {row['test_name']: row for row in rows}
    matched = [index[name] for name in sorted(processed) if name in index]
    unknown = sorted(set(processed)-set(index))
    required = {row['ref_name'] for row in matched}
    missing = sorted(required-set(references))
    mismatches, ready, derived = [], 0, 0
    for row in matched:
        name = row['ref_name']
        if name not in references:
            continue
        ref, test = references[name], processed[row['test_name']]
        if (ref['sample_rate'], ref['channels']) != (test['sample_rate'], test['channels']):
            mismatches.append(row['test_name'])
        else:
            ready += 1
            derived += row['method'] == 'Elastique'
    locations: dict[str, set[str]] = defaultdict(set)
    for row in rows:
        locations[row['ref_name']].add(row['ref_loc'])
    return dict(
        schema_version=1,
        scope='exact supplied test_name to MOS ref_name mapping; WAV-header audit only',
        inputs={key: {'name': path.name, 'sha256': fingerprint(path)}
                for key, path in [('references', ref_zip), ('processed', test_zip), ('scores', scores)]},
        score_rows=len(rows), reference_files=len(references), processed_files=len(processed),
        matched_score_rows=len(matched), unknown_processed_files=unknown,
        processed_methods=dict(sorted(Counter(row['method'] for row in matched).items())),
        required_reference_files=len(required), matched_reference_files=len(required & set(references)),
        missing_reference_files=missing, rate_or_channel_mismatches=mismatches,
        ready_processed_pairs=ready, ready_derived_elastique_pairs=derived,
        four_way_inputs_ready=bool(derived) and not (unknown or missing or mismatches),
        reference_only_sources=[dict(name=name, locations=sorted(locations[name]), **references[name])
                                for name in sorted(references)],
        interpretation='Reference-only evaluation is distinct from the held-out test comparison. '
                       'Derived Elastique is TSM plus offline resampling, not native pitch output. '
                       'Header readiness does not validate finite samples or perceptual quality.')


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    for flag in ('ref-zip', 'test-zip', 'scores', 'output'):
        parser.add_argument('--'+flag, type=Path, required=True)
    parser.add_argument('--require-four-way', action='store_true')
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError('output already exists')
    result = audit(args.ref_zip, args.test_zip, args.scores)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, allow_nan=False)+'\n', encoding='utf-8')
    print(f'{result["ready_processed_pairs"]}/{result["processed_files"]} paired; '
          f'{len(result["missing_reference_files"])} references missing')
    if args.require_four_way and not result['four_way_inputs_ready']:
        raise SystemExit(2)


if __name__ == '__main__':
    main()
