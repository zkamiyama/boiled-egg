#!/usr/bin/env python3
"""Decode submitted blind winner votes without inventing missing preferences.

One CSV per explicitly named listener. Counts are descriptive, not MOS, pairwise
rankings, independent-trial significance tests, or automatic promotion gates.
Legacy exports without a pack identity require explicit --allow-unbound.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import tempfile
from collections import Counter, defaultdict
from pathlib import Path

CRITERIA = ('overall', 'attack', 'tone')


def fingerprint(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_csv(path: Path, required: set[str]) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(newline='', encoding='utf-8-sig') as stream:
        reader = csv.DictReader(stream)
        fields = reader.fieldnames or []
        if len(fields) != len(set(fields)) or not required <= set(fields):
            raise ValueError(f'missing or duplicate CSV columns: {path}')
        rows = list(reader)
    if any(None in row or any(value is None for value in row.values()) for row in rows):
        raise ValueError(f'malformed CSV row: {path}')
    return fields, rows


def trial_id(text: str) -> int:
    if not re.fullmatch(r'[0-9]+', text) or int(text) < 1:
        raise ValueError(f'invalid trial ID: {text!r}')
    return int(text)


def read_key(path: Path) -> tuple[dict[int, dict], list[str], str | None]:
    fields, rows = read_csv(path, {'trial'})
    labels = sorted(field for field in fields if re.fullmatch(r'[A-Z]', field))
    if labels not in (['A', 'B', 'C'], ['A', 'B', 'C', 'D']) or not rows:
        raise ValueError('answer key must contain three or four labels and at least one trial')
    result, systems, identities = {}, None, set()
    for row in rows:
        trial = trial_id(row['trial'])
        if trial in result:
            raise ValueError(f'duplicate key trial: {trial}')
        current = [row[label] for label in labels]
        if any(not system.strip() for system in current) or len(set(current)) != len(labels):
            raise ValueError(f'empty or duplicate system in trial {trial}')
        if systems is not None and set(current) != systems:
            raise ValueError('system set changes between trials')
        systems = set(current)
        identity = row.get('pack_id', '')
        if 'pack_id' in fields and not re.fullmatch(r'[0-9a-f]{64}', identity):
            raise ValueError('pack_id must be a nonempty SHA-256 identity')
        identities.add(identity)
        result[trial] = row
    if len(identities) != 1:
        raise ValueError('answer key mixes pack identities')
    return result, labels, next(iter(identities)) or None


def decode(key_path: Path, ballots: list[tuple[str, Path]], *,
           allow_unbound: bool = False, require_complete: bool = False) -> tuple[list[dict], dict]:
    key, labels, pack_id = read_key(key_path)
    if not ballots:
        raise ValueError('at least one explicitly named listener ballot is required')
    decoded, provenance, seen_listeners, seen_paths = [], [], set(), set()
    for listener, path in ballots:
        if (not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,63}', listener) or
                listener in seen_listeners or path.resolve() in seen_paths):
            raise ValueError('invalid/duplicate listener ID or repeated ballot file')
        seen_listeners.add(listener)
        seen_paths.add(path.resolve())
        fields, choices = read_csv(path, {'trial', *CRITERIA})
        bound = pack_id is not None and 'pack_id' in fields
        if not bound and not allow_unbound:
            raise ValueError('unbound legacy ballot/key; regenerate a pack-bound export or explicitly allow unbound input')
        votes = {}
        for row in choices:
            trial = trial_id(row['trial'])
            if trial not in key or trial in votes:
                raise ValueError(f'unknown/duplicate ballot trial: {trial}')
            if bound and row['pack_id'] != pack_id:
                raise ValueError('ballot belongs to a different pack')
            if 'listener_id' in fields and row['listener_id'] != listener:
                raise ValueError('ballot listener_id conflicts with explicit listener ID')
            for criterion in CRITERIA:
                if row[criterion] not in ['', *labels]:
                    raise ValueError(f'invalid {criterion} label in trial {trial}: {row[criterion]!r}')
            votes[trial] = row
        if require_complete and (set(votes) != set(key) or
                any(not row[criterion] for row in votes.values() for criterion in CRITERIA)):
            raise ValueError(f'incomplete ballot: {listener}')
        for trial, answer in sorted(key.items()):
            for criterion in CRITERIA:
                label = votes.get(trial, {}).get(criterion, '')
                decoded.append(dict(listener=listener, trial=trial, criterion=criterion,
                                    label=label, system=answer[label] if label else '',
                                    status='selected' if label else 'missing',
                                    category=answer.get('category', ''), formant=answer.get('formant', ''),
                                    semitones=answer.get('semitones', answer.get('pitch_semitones', ''))))
        provenance.append(dict(listener=listener, file=path.name, sha256=fingerprint(path),
                               identity_verified=bound, supplied_trial_rows=len(votes)))
    systems = sorted({row[label] for row in key.values() for label in labels})
    groups = []
    for dimension in ('all', 'category', 'formant', 'semitones'):
        buckets: dict[tuple[str, str], list[dict]] = defaultdict(list)
        for row in decoded:
            value = 'all' if dimension == 'all' else row[dimension]
            buckets[(value, row['criterion'])].append(row)
        for (value, criterion), selected in sorted(buckets.items()):
            counts = Counter(row['system'] for row in selected if row['status'] == 'selected')
            submitted = sum(counts.values())
            groups.append(dict(dimension=dimension, value=value, criterion=criterion,
                               possible_votes=len(selected), submitted_votes=submitted,
                               missing_votes=len(selected)-submitted,
                               counts={system: counts[system] for system in systems},
                               selection_fractions={system: counts[system]/submitted if submitted else None
                                                    for system in systems}))
    submitted = sum(row['status'] == 'selected' for row in decoded)
    summary = dict(schema='boiled-egg.blind-winner-votes.v1', key_sha256=fingerprint(key_path),
                   pack_id=pack_id, trials=len(key), listeners=len(ballots), systems=systems,
                   criteria=list(CRITERIA), possible_votes=len(decoded), submitted_votes=submitted,
                   missing_votes=len(decoded)-submitted, ballots=provenance, groups=groups,
                   identity_verified=all(item['identity_verified'] for item in provenance),
                   status='submitted_preferences' if submitted else 'no_submitted_preferences',
                   interpretation='Winner-selection counts only. Missing answers are not losses or ties. '
                                  'Losing systems are not ranked. Repeated source/pitch trials are not '
                                  'independent listeners. No MOS transfer, significance, or promotion verdict.')
    return decoded, summary


def write_report(output: Path, decoded: list[dict], summary: dict) -> None:
    if output.exists() and (not output.is_dir() or any(output.iterdir())):
        raise ValueError('output must be absent or empty')
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.blind-votes-', dir=output.parent) as tmp:
        staging = Path(tmp)/'report'
        staging.mkdir()
        with (staging/'decoded_votes.csv').open('w', newline='', encoding='utf-8') as stream:
            writer = csv.DictWriter(stream, fieldnames=list(decoded[0]))
            writer.writeheader()
            writer.writerows(decoded)
        (staging/'summary.json').write_text(json.dumps(summary, indent=2, allow_nan=False)+'\n', encoding='utf-8')
        if output.exists():
            output.rmdir()
        staging.rename(output)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--answer-key', type=Path, required=True)
    parser.add_argument('--ballot', nargs=2, action='append', metavar=('LISTENER_ID', 'CSV'), required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--allow-unbound', action='store_true')
    parser.add_argument('--require-complete', action='store_true')
    args = parser.parse_args()
    rows, summary = decode(args.answer_key, [(name, Path(path)) for name, path in args.ballot],
                           allow_unbound=args.allow_unbound, require_complete=args.require_complete)
    write_report(args.output, rows, summary)
    print(f'{summary["submitted_votes"]}/{summary["possible_votes"]} submitted criterion votes; '
          f'identity_verified={summary["identity_verified"]}')


if __name__ == '__main__':
    main()
