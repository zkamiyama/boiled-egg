#!/usr/bin/env python3
"""Paired innovation study with explicit true pilot membership and raw losses.

The inherited owner-study CSV contains that earlier study's `split` annotation.
It is NOT this iteration's cohort. We retain raw files unedited and classify the
five actual pilot sources explicitly below. Confirmation is only within this
iteration; historical reuse means it is not a pristine statistical holdout.
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
import math
import tempfile
from collections import defaultdict
from pathlib import Path
import numpy as np

PILOT_SOURCES=frozenset(('Ardour_2','Female_4','Male_6','Rock_4','Triangle_02'))
LABELS={'baseline':'ordinary Fuzzy','guard':'bounded phase-owner predecessor','refined':'innovation-weighted correction',
        'provided_elastique':'provided Elastique TSM recording; version/mode unknown'}
TEXT={'source','fixture','family','category','condition','operation','variant','formant','split','window_policy'}
KEYS=('source','fixture','condition','operation','formant','rate','shift','seed')

def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def read_report(root):
    report=json.loads((root/'summary.json').read_text())
    if digest(root/'measurements.csv')!=report['measurements_sha256']:raise ValueError('measurement hash mismatch')
    with (root/'measurements.csv').open(newline='',encoding='utf-8') as stream:
        reader=csv.DictReader(stream);fields=reader.fieldnames or []
        if len(fields)!=len(set(fields)) or not {'variant','render_sha256'}<=set(fields):raise ValueError('invalid CSV header')
        raw=list(reader)
    if len(raw)!=report['rows']:raise ValueError('row count mismatch')
    rows=[];seen=set()
    for r in raw:
        if None in r or any(v is None for v in r.values()):raise ValueError('ragged CSV row')
        row={}
        for k,v in r.items():
            if k in TEXT or k.endswith('sha256'):row[k]=v
            elif v=='':row[k]=None
            else:
                row[k]=float(v)
                if not math.isfinite(row[k]):raise ValueError('nonfinite measurement')
        if row['variant'] not in LABELS:raise ValueError('unknown variant')
        key=(*[row.get(k) for k in KEYS],row['variant'])
        if key in seen:raise ValueError('duplicate measurement')
        seen.add(key);rows.append(row)
    return rows,report

def confirmation_rows(rows):
    return [r for r in rows if r.get('source') not in PILOT_SOURCES]

def paired(rows,control,metric,higher=False):
    def index(variant):
        result={}
        for r in rows:
            if r['variant']!=variant or r.get(metric) is None:continue
            key=tuple(r.get(k) for k in KEYS)
            if key in result:raise ValueError('duplicate paired cell')
            result[key]=r
        return result
    a,b=index('refined'),index(control)
    if not a or set(a)!=set(b):raise ValueError('incomplete paired grid')
    differences=[];clusters=defaultdict(list);details=[]
    for k in sorted(a,key=str):
        d=a[k][metric]-b[k][metric];differences.append(d)
        clusters[a[k].get('source',a[k].get('fixture','all'))].append(d)
        details.append(dict(source=a[k].get('source',a[k].get('fixture')),condition=a[k].get('condition'),shift=a[k].get('shift'),delta=d))
    x=np.array(differences);good=x if higher else -x
    means=np.array([np.mean(v) for k,v in sorted(clusters.items())]);rng=np.random.default_rng(20260914)
    boot=means[rng.integers(0,len(means),(4000,len(means)))].mean(axis=1)
    worst=min(details,key=lambda r:r['delta']) if higher else max(details,key=lambda r:r['delta'])
    return dict(control=control,metric=metric,higher_is_better=higher,conditions=len(x),clusters=len(clusters),
        baseline_mean=float(np.mean([r[metric] for r in b.values()])),candidate_mean=float(np.mean([r[metric] for r in a.values()])),
        mean_delta=float(x.mean()),source_balanced_delta=float(means.mean()),ci95=list(map(float,np.quantile(boot,[.025,.975]))),
        wins=int((good>1e-9).sum()),losses=int((good < -1e-9).sum()),ties=int((abs(good)<=1e-9).sum()),worst_case=worst)

def natural_summary(rows,cohort,operation,formant):
    rows=[r for r in rows if r.get('operation',operation)==operation and r['formant']==formant]
    if cohort=='within_iteration_confirmation':rows=confirmation_rows(rows)
    results=[]
    controls=['baseline','guard']+(['provided_elastique'] if operation=='time_stretch' else [])
    for metric in ('onset_corr','envelope_rmse_db','rms_shape_db','spectral_distance_db'):
        if not any(r.get(metric) is not None for r in rows):continue
        for control in controls:
            results.append(dict(cohort=cohort,operation=operation,formant=formant,**paired(rows,control,metric,metric=='onset_corr')))
    return results

def run(args):
    if args.output.exists():raise ValueError('output exists')
    corpus,cr=read_report(args.corpus);synthetic,sr=read_report(args.synthetic)
    banks,br=read_report(args.banks);training,tr=read_report(args.training)
    if len({r['source'] for r in corpus})!=20 or not PILOT_SOURCES<={r['source'] for r in corpus}:raise ValueError('unexpected20-source corpus')
    if any(r['executables']!=cr['executables'] for r in (sr,br,tr)):raise ValueError('different renderer identities across suites')
    comparisons=[]
    for cohort in ('all20','within_iteration_confirmation'):
        for formant in ('off','harmonic','monophonic'):comparisons+=natural_summary(corpus,cohort,'exact_pitch',formant)
        comparisons+=natural_summary(corpus,cohort,'time_stretch','off')
    comparisons+=natural_summary(training,'separate_training12','exact_pitch','harmonic')
    partials=[]
    for label,rows in [('original_banks',[r for r in synthetic if r['fixture'] in ('harmonics','inharmonic')]),
                       ('previous_four',[r for r in synthetic if r['fixture'].startswith('unseen')]),('new_eight',banks)]:
        for rate in (48000,96000):
            selected=[r for r in rows if r['rate']==rate and r['shift']!=0]
            for control in ('baseline','guard'):
                partials.append(dict(fixture_set=label,rate=rate,**paired(selected,control,'partial_envelope_error_db')))
    peaks=[]
    for label,rows in [('corpus',corpus),('training',training),('synthetic',synthetic),('new_banks',banks)]:
        for variant in LABELS:
            group=[r for r in rows if r['variant']==variant]
            if group:peaks.append(dict(suite=label,variant=variant,max_sample_peak=max(r['peak'] for r in group),above_unity=sum(r['peak']>1 for r in group)))
    result=dict(schema='boiled-egg.phase-innovation-summary.v1',variant_names=LABELS,actual_pilot_sources=sorted(PILOT_SOURCES),
        ignored_legacy_column='split from earlier owner study; original raw CSV retained without alteration',
        natural=comparisons,partials=partials,peaks=peaks,
        inputs={str(p):digest(p/'summary.json') for p in (args.corpus,args.synthetic,args.banks,args.training)},
        limitations='Descriptive source-cluster4000-draw intervals, seed20260914, no multiplicity correction. '
        'Same corpus used historically. No native pitch result, perceptual score, all-condition victory or automatic promotion.')
    args.output.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.innovation-summary-',dir=args.output.parent) as tmp:
        staging=Path(tmp)/'report';staging.mkdir()
        (staging/'summary.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
        compact=[{k:(json.dumps(v) if isinstance(v,(dict,list)) else v) for k,v in r.items()} for r in comparisons+partials]
        with (staging/'paired_results.csv').open('w',newline='',encoding='utf-8') as stream:
            writer=csv.DictWriter(stream,fieldnames=sorted(set().union(*(r.keys() for r in compact))))
            writer.writeheader();writer.writerows(compact)
        staging.rename(args.output)
    return result

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for k in ('corpus','synthetic','banks','training','output'):p.add_argument('--'+k,type=Path,required=True)
    print(len(run(p.parse_args())['natural']),'paired natural descriptor comparisons')
