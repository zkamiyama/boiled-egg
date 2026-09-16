#!/usr/bin/env python3
"""Fixed 72-cell cost audit. Keep complete raw histories and failures.

Capacity follows the existing state-best-of-three policy, not a WCET guarantee.
Cost compares the median of the three cell means, never the best ratio/run.
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import importlib.util
import json
from pathlib import Path
import numpy as np

ROLES = ('original', 'pooled', 'optimized')
PITCHES = ('0.5', '1', '2')
KEYS = ('rate', 'quality', 'policy', 'block')


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def median_cost(original, candidate):
    a, b = np.asarray(original, float), np.asarray(candidate, float)
    if a.shape != (3,) or b.shape != (3,) or not np.isfinite(a).all() or not np.isfinite(b).all() or np.any(a <= 0) or np.any(b <= 0):
        raise ValueError('three positive finite cell means required')
    return float(np.median(b) / np.median(a))


def exact_history(a, b):
    """Check every warm and steady state; do not ignore unequal output sizes."""
    if len(a) != len(b):
        raise ValueError('history lengths differ')
    fields = ('repeat', *KEYS, 'index', 'warmup', 'fingerprint')
    for x, y in zip(a, b):
        if any(x[k] != y[k] for k in fields):
            raise ValueError('corrected/optimized history is not identical')


def run(root, output, policy):
    if output.exists():
        raise ValueError('new result file required')
    spec = importlib.util.spec_from_file_location('declared_capacity', policy)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    capacities = {}; tables = {}; hashes = {}
    for role in ROLES:
        for pitch in PITCHES:
            paths = [root/f'{role}-p{pitch}-{r}.csv' for r in (1, 2, 3)]
            capacities[(role, pitch)] = module.summarize(paths)
            for repeat, path in enumerate(paths, 1):
                hashes[path.name] = digest(path)
                with path.open(newline='') as stream:
                    rows = [{k: int(v) for k, v in row.items()} for row in csv.DictReader(stream)]
                tables[(role, pitch, repeat)] = rows
    compared = 0
    for pitch in PITCHES:
        for repeat in (1, 2, 3):
            a, b = tables[('pooled', pitch, repeat)], tables[('optimized', pitch, repeat)]
            exact_history(a, b); compared += len(a)
    means = {}
    for (role, pitch, repeat), rows in tables.items():
        for key in module.GRID:
            values = [r['wall_ns'] for r in rows if not r['warmup'] and tuple(r[k] for k in KEYS) == key]
            if len(values) != 1200:
                raise ValueError('missing per-cell means')
            means[(role, pitch, repeat, key)] = float(np.mean(values))
    cells = []
    for pitch in PITCHES:
        capacity = {tuple(r[k] for k in KEYS): r for r in capacities[('optimized', pitch)]['rows']}
        for key in sorted(module.GRID):
            values = {role: [means[(role, pitch, repeat, key)] for repeat in (1, 2, 3)] for role in ROLES}
            old_ratio = median_cost(values['original'], values['optimized'])
            prior_ratio = median_cost(values['pooled'], values['optimized'])
            cells.append(dict(zip(KEYS, key), pitch=float(pitch), mean_ns=values,
                              ratio_to_original=old_ratio, ratio_to_pooled=prior_ratio,
                              cost_pass=old_ratio <= 1.25, **{k: v for k, v in capacity[key].items() if k not in KEYS}))
    result = dict(schema='boiled-egg.static-cost.v1', cells=cells, cells_expected=72,
                  capacity_passed=sum(r['capacity_pass'] for r in cells),
                  cost_passed=sum(r['cost_pass'] for r in cells),
                  fingerprint_pairs=compared,
                  worst_capacity=max(r['state_best_worst_ratio'] for r in cells),
                  median_cost_ratio_to_original=float(np.median([r['ratio_to_original'] for r in cells])),
                  worst_cost_ratio_to_original=max(r['ratio_to_original'] for r in cells),
                  median_cost_ratio_to_pooled=float(np.median([r['ratio_to_pooled'] for r in cells])),
                  raw_misses=sum(r['raw_deadline_misses'] for r in cells),
                  actual_complete_runs=sum(r['full_successful_runs'] for r in cells),
                  raw_worst_ratio=max(r['raw_max_ratio'] for r in cells),
                  files=hashes, policy_sha256=digest(policy), script_sha256=digest(__file__),
                  notes='All raw warmup/steady samples retained. Exact same-toolchain output histories required. '
                        'No noise subtraction, outlier deletion or repeated-run quality evidence. '
                        'Original is the pre-repair implementation; pooled is the verified stereo repair.')
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, allow_nan=False)+'\n')
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ('results', 'output', 'policy'):
        parser.add_argument('--'+key, type=Path, required=True)
    args = parser.parse_args(); result = run(args.results, args.output, args.policy)
    print(json.dumps({k: v for k, v in result.items() if k not in ('cells', 'files')}, indent=2))
    raise SystemExit(not (result['capacity_passed'] == result['cost_passed'] == 72))
