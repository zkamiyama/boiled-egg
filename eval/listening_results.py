#!/usr/bin/env python3
"""Verify an anonymous pack and summarize only explicitly supplied observations.

Evaluation bookkeeping, not a perceptual model or an adoption gate. Incomplete
panels are counted but never completed with defaults. Organizer files are private.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
import itertools
import json
import math
from pathlib import Path
import re
import tempfile

import comparison_contract as c
import candidate_evidence as e

INDEX = 'organizer/integrity.json'
DIMENSIONS = ('naturalness', 'attack', 'sustain')


def pack_files(root: Path) -> dict[str, str]:
    result = {}
    for folder in ('listener', 'organizer'):
        for path in sorted((root / folder).rglob('*')):
            if not path.is_file():
                continue
            name = path.relative_to(root).as_posix()
            if name == INDEX:
                continue
            e.inside(root, name)  # Includes symlink/path-escape protection.
            result[name] = c.fingerprint(path)
    return result


def seal_pack(root: Path) -> str:
    """Called only after verified presentation generation; never repairs an index."""
    path = root / INDEX
    if path.exists():
        raise ValueError('pack already sealed; do not replace evidence')
    public = json.loads((root / 'listener/trials.json').read_text())
    c.json_write(path, dict(schema='boiled-egg.listening-integrity.v1',
                            pack_id=public['pack_id'], files=pack_files(root)))
    return c.fingerprint(path)


def verify_pack(root: Path, expected_index_sha256: str | None = None) -> tuple[dict, dict]:
    root = root.resolve(strict=True)
    path = e.inside(root, INDEX)
    if expected_index_sha256 is not None and c.fingerprint(path) != expected_index_sha256:
        raise ValueError('integrity index differs from separately recorded hash')
    index = json.loads(path.read_text())
    if index.get('schema') != 'boiled-egg.listening-integrity.v1' or pack_files(root) != index['files']:
        raise ValueError('changed, missing or unexpected pack file')
    public = json.loads((root / 'listener/trials.json').read_text())
    key = json.loads((root / 'organizer/key.json').read_text())
    evidence = json.loads((root / 'organizer/evidence.json').read_text())
    report = json.loads((root / 'organizer/summary.json').read_text())
    identity = e.digest(dict(plan=evidence['plan'],
                            receipts=[r['raw_output_sha256'] for r in evidence['receipts']],
                            seed=key['seed']))
    if any(x['pack_id'] != identity for x in (index, public, key, report)):
        raise ValueError('pack/organizer/evidence identity mismatch')
    expected = {}; trial_ids = set(); candidate_sets = []
    for trial in public['trials']:
        if trial['trial'] in trial_ids or not re.fullmatch(r'T[0-9]{3,}', trial['trial']):
            raise ValueError('duplicate or invalid trial')
        trial_ids.add(trial['trial'])
        labels = set()
        original = e.inside(root / 'listener', trial['original'])
        if c.fingerprint(original) != trial['original_sha256']:
            raise ValueError('orientation audio identity')
        for choice in trial['choices']:
            if choice['label'] in labels:
                raise ValueError('duplicate choice')
            labels.add(choice['label'])
            audio = e.inside(root / 'listener', choice['file'])
            if c.fingerprint(audio) != choice['sha256']:
                raise ValueError('presentation audio identity')
            expected[(trial['trial'], choice['label'])] = (trial, choice)
        if len(labels) < 2:
            raise ValueError('comparison needs at least two choices')
    authorized = set()
    for receipt in evidence['receipts']:
        source = receipt['source']; candidate = receipt['engine']
        if (receipt['status'] != 'passed' or receipt['errors']
                or source not in evidence['plan']['sources']
                or candidate not in evidence['plan']['probes']
                or receipt['source_metadata'] != evidence['plan']['sources'][source]
                or receipt['raw_output_sha256'] != receipt['output']['sha256']
                or receipt['candidate_identity'] != e.digest(evidence['plan']['probes'][candidate])
                or c.output_checks(receipt['source_metadata'], receipt['output'], c.Request(**receipt['request']))):
            raise ValueError('invalid embedded render evidence')
        signature = e.digest([source, candidate, receipt['request'], receipt['raw_output_sha256']])
        if signature in authorized:
            raise ValueError('duplicate embedded receipt')
        authorized.add(signature)
    observed = set()
    actual = {}; gains = defaultdict(set); by_trial = defaultdict(set)
    for row in key['choices']:
        ident = (row['trial'], row['choice'])
        if ident in actual or ident not in expected:
            raise ValueError('organizer is not a one-to-one choice map')
        trial, choice = expected[ident]
        if (row['request'] != trial['request'] or row['presentation_sha256'] != choice['sha256']
                or row['candidate'] in by_trial[row['trial']]):
            raise ValueError('organizer choice/request mismatch')
        if not math.isfinite(row['common_gain']) or not 0 < row['common_gain'] <= 1:
            raise ValueError('invalid presentation gain')
        signature = e.digest([row['source'], row['candidate'], row['request'], row['raw_sha256']])
        if signature not in authorized or signature in observed:
            raise ValueError('organizer disagrees with rendered candidate evidence')
        observed.add(signature)
        actual[ident] = row
        gains[row['trial']].add(row['common_gain'])
        by_trial[row['trial']].add(row['candidate'])
    candidate_sets = [frozenset(v) for v in by_trial.values()]
    if (not expected or set(actual) != set(expected) or observed != authorized
            or any(len(g) != 1 for g in gains.values())
            or len(set(candidate_sets)) != 1
            or report['trials'] != len(trial_ids) or report['choices'] != len(expected)):
        raise ValueError('incomplete or inconsistent listening panel')
    return public, actual


def summarize(pack: Path, submissions: list[dict], output: Path,
              expected_index_sha256: str | None = None) -> dict:
    from calibrated_listening import validate_answers
    if output.exists():
        raise ValueError('new report directory required')
    public, key = verify_pack(pack, expected_index_sha256)
    before = c.fingerprint(pack / INDEX)
    listener_ids = set(); paths = set(); records = []; receipts = []
    for item in submissions:
        if set(item) != {'listener_id', 'path'}:
            raise ValueError('submission requires only listener_id and path')
        listener = item['listener_id']
        if (not isinstance(listener, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,64}', listener)
                or listener in listener_ids):
            raise ValueError('unique anonymous listener IDs required')
        path = Path(item['path']).resolve(strict=True)
        if path in paths:
            raise ValueError('same submission file supplied more than once')
        listener_ids.add(listener); paths.add(path)
        digest = c.fingerprint(path)
        answers = json.loads(path.read_text())
        ratings = validate_answers(pack, answers)
        receipts.append(dict(listener_id=listener, path=str(path), sha256=digest,
                             explicit_ratings=len(ratings)))
        for row in ratings:
            origin = key[(row['trial'], row['choice'])]
            records.append(dict(listener_id=listener, **row,
                                candidate=origin['candidate'], source=origin['source'],
                                request=origin['request']))
    # Comparison uses complete panels per listener/trial/dimension, not unrelated
    # ratings from different sources/listeners. Partial observations remain raw.
    panels = defaultdict(list)
    for row in records:
        panels[(row['listener_id'], row['trial'], row['dimension'])].append(row)
    expected_candidates = {row['candidate'] for row in key.values()}
    complete = {}; incomplete = []
    for ident, rows in panels.items():
        if {r['candidate'] for r in rows} == expected_candidates:
            complete[ident] = rows
        else:
            incomplete.append(dict(listener_id=ident[0], trial=ident[1], dimension=ident[2],
                                   received=len(rows), expected=len(expected_candidates)))
    means = []; paired = []
    for dimension in DIMENSIONS:
        selected = [(ident, rows) for ident, rows in complete.items() if ident[2] == dimension]
        for candidate in sorted(expected_candidates):
            grouped = defaultdict(list)
            for ident, rows in selected:
                grouped[ident[0]].append(next(r['rating'] for r in rows if r['candidate'] == candidate))
            listener_means = [sum(v) / len(v) for v in grouped.values()]
            means.append(dict(dimension=dimension, candidate=candidate,
                              listeners=len(grouped), complete_panels=len(selected),
                              listener_balanced_mean=(sum(listener_means) / len(listener_means)
                                                      if listener_means else None)))
        for a, b in itertools.combinations(sorted(expected_candidates), 2):
            grouped = defaultdict(list); differences = []
            for ident, rows in selected:
                scores = {r['candidate']: r['rating'] for r in rows}
                delta = scores[a] - scores[b]
                differences.append(delta); grouped[ident[0]].append(delta)
            listener_deltas = [sum(v) / len(v) for v in grouped.values()]
            paired.append(dict(dimension=dimension, candidate=a, control=b,
                               listeners=len(grouped), matched_complete_panels=len(selected),
                               listener_balanced_delta=(sum(listener_deltas) / len(listener_deltas)
                                                        if listener_deltas else None),
                               higher=sum(v > 0 for v in differences),
                               lower=sum(v < 0 for v in differences),
                               ties=sum(v == 0 for v in differences)))
    report = dict(schema='boiled-egg.exploratory-observations.v1', pack_id=public['pack_id'],
                  integrity_index_sha256=before, submissions=receipts,
                  submitted_listener_ids=len(listener_ids), explicit_ratings=len(records),
                  complete_panels=len(complete), incomplete_panels=incomplete,
                  candidate_means=means, paired=paired,
                  listening_status='no_responses' if not records else 'exploratory_observations',
                  quality_selection=None,
                  method='Complete panels only; equal weighting of contributing listener means. '
                         'Unequal coverage and partial ratings retained; no default scores, '
                         'significance claim, certified MOS or automatic promotion.')
    verify_pack(pack, before)
    for receipt in receipts:
        if c.fingerprint(Path(receipt['path'])) != receipt['sha256']:
            raise ValueError('submission changed while reading')
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.observations-', dir=output.parent) as temporary:
        stage = Path(temporary) / 'report'; stage.mkdir()
        c.json_write(stage / 'summary.json', report)
        c.json_write(stage / 'explicit_observations.json', records)
        stage.rename(output)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pack', type=Path, required=True)
    parser.add_argument('--submissions', type=Path, required=True,
                        help='JSON list of {listener_id,path}; [] means no observations')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--expected-index-sha256')
    args = parser.parse_args()
    manifest = json.loads(args.submissions.read_text())
    if not isinstance(manifest, list):
        raise ValueError('submission manifest must be a list')
    result = summarize(args.pack, manifest, args.output, args.expected_index_sha256)
    print(json.dumps({k: result[k] for k in ('pack_id', 'listening_status', 'explicit_ratings',
                                           'complete_panels', 'quality_selection')}, indent=2))


if __name__ == '__main__':
    main()
