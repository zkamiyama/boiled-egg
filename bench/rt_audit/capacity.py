#!/usr/bin/env python3
"""Practical capacity evidence, not a worst-case-time or whole-DAW guarantee.

For each replayed input/history position, use the minimum of exactly three
predeclared repetitions; then take the maximum over positions/configurations.
Do not concatenate those minima into a fictitious successful continuous run.
All observed misses, maxima, actual successful runs and cold data are retained.
"""
from __future__ import annotations
import argparse
import csv
import json
import math
from collections import Counter, defaultdict
from pathlib import Path
from analyze import analyze
from run_matrix import digest

DEFAULT_POLICY = {
    'schema': 'boiled-egg.capacity-policy.v1',
    'repeats': 3,
    'minimum_steady_calls': 1200,
    'budget_fraction': 0.8,
    'maximum_relative_regression': 1.25,
}


def validate_policy(policy: dict) -> dict:
    if set(policy) != set(DEFAULT_POLICY) or policy['schema'] != DEFAULT_POLICY['schema']:
        raise ValueError('unknown or incomplete capacity policy')
    if type(policy['repeats']) is not int or policy['repeats'] != 3:
        raise ValueError('exactly three predeclared repetitions required')
    n = policy['minimum_steady_calls']
    if type(n) is not int or not 1 <= n <= 100000:
        raise ValueError('invalid minimum steady calls')
    for key, lo, hi in (('budget_fraction', 0., 1.), ('maximum_relative_regression', 1., 10.)):
        v = policy[key]
        if type(v) not in (int, float) or not math.isfinite(v) or not lo < v <= hi:
            raise ValueError('invalid ' + key)
    return dict(policy)


def replay_envelope(trials: list[list[dict]], fraction: float) -> tuple[dict, list[dict]]:
    """Pure three-way reducer. Input rows are validated before this call."""
    if len(trials) != 3 or not trials[0] or len({len(t) for t in trials}) != 1:
        raise ValueError('three equally sized nonempty replays required')
    if not math.isfinite(fraction) or not 0 < fraction <= 1:
        raise ValueError('invalid budget fraction')
    envelope = []
    histogram = Counter()
    successful = [True, True, True]
    under_period = [True, True, True]
    period_misses = budget_misses = 0
    raw_max = 0.
    for aligned in zip(*trials):
        if len({(r['index'], r['period_ns'], r['output_hash']) for r in aligned}) != 1:
            raise ValueError('different replay position, period or output history')
        period = aligned[0]['period_ns']
        times = [r['wall_ns'] for r in aligned]
        if period <= 0 or any(type(v) is not int or v <= 0 for v in times):
            raise ValueError('nonpositive or invalid clock measurement')
        ordered = sorted(times)
        successes = sum(v <= fraction * period for v in times)
        histogram[successes] += 1
        for i, v in enumerate(times):
            successful[i] &= v <= fraction * period
            under_period[i] &= v <= period
            budget_misses += v > fraction * period
            period_misses += v > period
            raw_max = max(raw_max, v / period)
        envelope.append(dict(index=aligned[0]['index'], period_ns=period,
            best_ns=ordered[0], second_best_ns=ordered[1], worst_ns=ordered[2],
            best_ratio=ordered[0]/period, second_best_ratio=ordered[1]/period,
            successes=successes, output_hash=aligned[0]['output_hash']))
    worst = max(envelope, key=lambda r: r['best_ratio'])
    return dict(states=len(envelope), calls=3*len(envelope),
        every_state_observed_within_budget=not histogram[0],
        worst_state_best_ratio=worst['best_ratio'], worst_state=worst,
        worst_state_second_best_ratio=max(r['second_best_ratio'] for r in envelope),
        states_by_success_count={str(i): histogram[i] for i in range(4)},
        actual_all_budget_runs=[i+1 for i,v in enumerate(successful) if v],
        actual_all_period_runs=[i+1 for i,v in enumerate(under_period) if v],
        raw_budget_exceedances=budget_misses, raw_period_exceedances=period_misses,
        raw_max_ratio=raw_max), envelope


def report(root: Path, reference_label: str | None = None) -> tuple[dict, list[dict]]:
    # Existing strict receipt/grid/output-invariance validation remains mandatory.
    checked = analyze(root)
    plan = json.loads((root/'plan.json').read_text())
    if plan['matrix'] != 'capacity':
        raise ValueError('requires a capacity plan with policy fixed before measurements')
    policy = validate_policy(plan['capacity_policy'])
    if plan['count'] < policy['minimum_steady_calls']:
        raise ValueError('measurement count below predeclared policy')
    if reference_label is not None and reference_label not in plan['probes']:
        raise ValueError('reference label absent from plan')
    groups = defaultdict(dict)
    for r in checked['runs']:
        if r['workload'] != 'dsp' or r['schedule'] != 'saturated' or r['bracket'] != 'wall':
            raise ValueError('capacity must use separated wall-only saturated replays')
        groups[(r['label'],r['rate'],r['block'],r['shift'])][r['repeat']] = r
    results = []; envelopes = []
    for (label,rate,block,shift), runs in sorted(groups.items()):
        if set(runs) != {1,2,3}:
            raise ValueError('incomplete replay set')
        trials = []
        identities = {(r['metadata']['warmup'],r['metadata']['latency_frames'],
                       r['metadata']['pinned_cpu'],r['metadata']['policy']) for r in runs.values()}
        if len(identities) != 1:
            raise ValueError('replays used different warmup, latency, CPU or scheduling policy')
        for i in (1,2,3):
            r = runs[i]; path = root/(r['name']+'.csv')
            if digest(path) != r['csv_sha256']:
                raise ValueError('CSV changed after validation')
            with path.open(newline='') as stream:
                trial = [{k: (v if k=='output_hash' else int(v)) for k,v in row.items()}
                         for row in csv.DictReader(stream) if row['cold']=='0']
            trials.append(trial)
        metrics, envelope = replay_envelope(trials,policy['budget_fraction'])
        common = dict(label=label,rate=rate,block=block,shift=shift)
        results.append(dict(**common,**metrics,latency_frames=runs[1]['metadata']['latency_frames'],
            warmup=runs[1]['metadata']['warmup'],
            raw_trials=[dict(repeat=i,cold=runs[i]['cold'],steady=runs[i]['steady']) for i in (1,2,3)]))
        envelopes.extend(dict(**common,**r) for r in envelope)
    labels = []
    for label in plan['probes']:
        cells = [r for r in results if r['label']==label]
        observed = all(r['every_state_observed_within_budget'] for r in cells)
        labels.append(dict(label=label,cells=len(cells),capacity_observed=observed,
            status='capacity_observed' if observed else 'capacity_not_demonstrated',
            worst_state_best_ratio=max(r['worst_state_best_ratio'] for r in cells),
            worst_state_second_best_ratio=max(r['worst_state_second_best_ratio'] for r in cells),
            states_with_only_one_success_of_three=sum(r['states_by_success_count']['1'] for r in cells),
            raw_period_exceedances=sum(r['raw_period_exceedances'] for r in cells),
            actual_all_period_runs=sum(len(r['actual_all_period_runs']) for r in cells),
            actual_runs=3*len(cells)))
    regressions = []
    if reference_label is not None:
        baseline = {(r['rate'],r['block'],r['shift']):r for r in results if r['label']==reference_label}
        for r in results:
            if r['label']==reference_label: continue
            b = baseline[(r['rate'],r['block'],r['shift'])]
            if (r['warmup'],r['latency_frames'],r['states']) != (b['warmup'],b['latency_frames'],b['states']):
                raise ValueError('relative regression requires matched replay windows and latency')
            relative = r['worst_state_best_ratio']/b['worst_state_best_ratio']
            regressions.append(dict(label=r['label'],reference=reference_label,rate=r['rate'],
                block=r['block'],shift=r['shift'],relative_capacity_cost=relative,
                within_limit=relative <= policy['maximum_relative_regression']))
    return dict(schema='boiled-egg.capacity-report.v1',policy=policy,
        plan_sha256=digest(root/'plan.json'),reporter_sha256=digest(Path(__file__)),
        dependencies=plan.get('dependencies',{}),probes=plan['probes'],
        output_replay_invariance=checked['output_protocol_invariance'],labels=labels,cells=results,
        relative_regressions=regressions,
        scope='Declared deterministic stereo input/history, static target pitches; not all possible DSP states.',
        interpretation='Each state uses its own best of exactly three trials. This demonstrates observed capacity, '
        'NOT a worst-case bound, interrupt attribution, a stitched continuous success or a whole-DAW guarantee. '
        'Raw cold/steady misses and actual successful replays remain visible. No time/control subtraction. '
        'Relative labels must be chosen only for functionally comparable builds; no DSP promotion is automatic.',
        hard_realtime_qualified=False,automatic_promotion=False), envelopes


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('root',type=Path);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--envelopes',type=Path);p.add_argument('--reference-label')
    p.add_argument('--require-capacity',action='store_true',help='exit 2 when declared capacity/regression evidence is not met')
    a=p.parse_args()
    result,rows=report(a.root,a.reference_label)
    with a.output.open('x',encoding='utf-8') as stream:
        json.dump(result,stream,indent=2,allow_nan=False);stream.write('\n')
    if a.envelopes:
        with a.envelopes.open('x',newline='',encoding='utf-8') as stream:
            w=csv.DictWriter(stream,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    print(json.dumps(result['labels'],indent=2))
    if a.require_capacity and (not all(r['capacity_observed'] for r in result['labels']) or
                               not all(r['within_limit'] for r in result['relative_regressions'])):
        raise SystemExit(2)
