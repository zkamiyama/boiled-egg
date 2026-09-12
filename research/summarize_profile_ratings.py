#!/usr/bin/env python3
"""Validate blind ratings and report descriptive, listener-balanced differences.

Only complete A/B/C triplets enter profile comparisons. No MOS labels, inferred
ratings, significance claim or automatic promotion decision is produced.
"""
from __future__ import annotations

import argparse
import csv
import json
import statistics
from collections import defaultdict
from pathlib import Path

from eval_multires_corpus import fingerprint
from eval_reference_profiles import PROFILES
from make_reference_profile_pack import CRITERIA, PACK_SCHEMA, RATING_FIELDS


def collect(key_path: Path, rating_paths: list[Path]) -> dict:
    key = json.loads(key_path.read_text())
    if key.get('schema') != PACK_SCHEMA or key.get('external_baseline') != 'none':
        raise ValueError('unsupported answer-key schema/baseline')
    trials = {}
    for trial in key['trials']:
        tid = trial['trial_id']
        if tid in trials or set(trial['labels']) != set('ABC') or set(trial['labels'].values()) != set(PROFILES):
            raise ValueError('invalid or duplicate blind answer-key trial')
        trials[tid] = trial
    if not trials or not rating_paths:
        raise ValueError('nonempty key and rating files required')
    seen = set()
    rated = defaultdict(dict)
    submitted = set()
    blank_rows = 0
    for path in rating_paths:
        with path.open(newline='', encoding='utf-8-sig') as stream:
            reader = csv.DictReader(stream)
            if reader.fieldnames != list(RATING_FIELDS):
                raise ValueError('unexpected rating CSV header/order')
            for row in reader:
                if None in row or any(v is None for v in row.values()):
                    raise ValueError('malformed rating CSV row')
                if row['pack_id'] != key['pack_id']:
                    raise ValueError('ratings belong to a different pack')
                tid, label, listener = row['trial_id'], row['label'], row['listener_id'].strip()
                if tid not in trials or label not in trials[tid]['labels']:
                    raise ValueError('unknown trial/label')
                identity = (listener, tid, label)
                if identity in seen:
                    raise ValueError('duplicate listener/trial/label; merge explicitly before import')
                seen.add(identity)
                values = [row[c].strip() for c in CRITERIA]
                if listener:
                    submitted.add(listener)
                if not any(values):
                    blank_rows += 1
                    continue
                if not listener or any(v not in ('1','2','3','4','5') for v in values):
                    raise ValueError('listener ID and four integer scores in [1,5] required')
                rated[(listener,tid)][label] = dict(zip(CRITERIA, map(int,values)))
    complete = {k:v for k,v in rated.items() if set(v) == set('ABC')}
    incomplete = [dict(listener_id=listener, trial_id=tid, rated_labels=sorted(values))
                  for (listener,tid), values in sorted(rated.items()) if set(values) != set('ABC')]
    by_listener = defaultdict(lambda: defaultdict(list))
    for (listener, tid), labels in complete.items():
        mapped = {trials[tid]['labels'][label]:values for label,values in labels.items()}
        for profile in PROFILES:
            for criterion in CRITERIA:
                by_listener[listener][(profile,criterion)].append(mapped[profile][criterion])
    results = {}
    for criterion in CRITERIA:
        result = {}
        for profile in PROFILES:
            means = [statistics.mean(v[(profile,criterion)]) for v in by_listener.values()]
            deltas = [statistics.mean(v[(profile,criterion)])-statistics.mean(v[('transient',criterion)])
                      for v in by_listener.values()]
            result[profile] = dict(listeners=len(means), complete_triplets=len(complete),
                listener_balanced_mean=statistics.mean(means) if means else None,
                mean_delta_vs_transient=statistics.mean(deltas) if deltas else None)
        results[criterion] = result
    coverage = {listener:dict(complete_trials=sum(l == listener for l,t in complete),
                             expected_trials=len(trials)) for listener in sorted(submitted)}
    all_complete = bool(submitted) and all(v['complete_trials'] == len(trials) for v in coverage.values())
    return dict(schema='boiled-egg.profile-ratings-summary.v1', pack_id=key['pack_id'],
                answer_key_sha256=fingerprint(key_path),
                rating_files=[dict(name=p.name, sha256=fingerprint(p)) for p in rating_paths],
                status=('complete_for_submitted_listeners' if all_complete else 'partial') if rated else 'not_listened',
                submitted_listeners=len(submitted), analyzed_listeners=len(by_listener),
                rated_candidates=sum(len(v) for v in rated.values()), blank_rows=blank_rows,
                complete_triplets=len(complete), incomplete_trials=incomplete,
                coverage=coverage, scores=results, external_baseline='none',
                automatic_promotion=False, statistics='descriptive; equal listener weight; complete triplets only')


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--answer-key', type=Path, required=True)
    parser.add_argument('--ratings', type=Path, nargs='+', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = collect(args.answer_key, args.ratings)
    with args.output.open('x', encoding='utf-8') as stream:
        json.dump(result, stream, indent=2, allow_nan=False); stream.write('\n')
    print(json.dumps(result, indent=2, allow_nan=False))


if __name__ == '__main__':
    main()
