#!/usr/bin/env python3
"""Paired complete-grid callback summaries; p99 is not a hard-RT guarantee.

Keep maxima and deadline-miss counts; never silently drop incomplete repeats.
Each output cell is the median of its three repetitions. Worst-pitch summaries
are calculated after that median, not by selecting the fastest run.
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import itertools
import json
import math
import statistics
from pathlib import Path

KEYS=('rate','channels','block','shift','profile','variant')
PROFILES=('transient','fuzzy','multires')
PITCHES=(-12,-7,-3,3,7,12)
VARIANTS={'core':('scalar','simd','scheduled','scheduled-simd'),
          'host':('scalar','scheduled-simd')}


def expected(kind: str) -> set[tuple]:
    if kind not in VARIANTS:raise ValueError('unknown benchmark kind')
    return set(itertools.product((48000,96000),(1,2),(32,64),PITCHES,PROFILES,VARIANTS[kind]))


def summarize(paths: list[Path],kind: str) -> dict:
    grid=expected(kind);by_repeat={};all_rows=[]
    for path in paths:
        with path.open(newline='',encoding='utf-8') as stream:
            reader=csv.DictReader(stream);fields=reader.fieldnames or []
            required={*KEYS,'repeat','callbacks','cpu_mean_us','cpu_p99_us','cpu_max_us','wall_p99_us','cpu_p99_ratio','frame_overruns'}
            if kind=='host':required|={'cpu_misses','wall_misses','wall_max_us','underruns','latency_frames'}
            if len(fields)!=len(set(fields)) or not required<=set(fields):raise ValueError('missing/duplicate fields')
            rows=list(reader)
        if not rows:raise ValueError('empty benchmark')
        local={};repeats=set()
        for raw in rows:
            if None in raw or any(v is None for v in raw.values()):raise ValueError('ragged benchmark row')
            row={k:v if k in ('profile','variant') else float(v) for k,v in raw.items()}
            if any(not math.isfinite(v) for v in row.values() if isinstance(v,float)):raise ValueError('nonfinite measurement')
            for field in ('repeat','rate','channels','block','shift','callbacks'):
                if row[field]!=int(row[field]):raise ValueError('integer field required')
                row[field]=int(row[field])
            if row['callbacks']!=1200 or row['cpu_p99_us']<0 or row['cpu_mean_us']<0 or row['cpu_max_us']<row['cpu_p99_us']:
                raise ValueError('invalid callback count/timing')
            deadline=1e6*row['block']/row['rate']
            if not math.isclose(row['cpu_p99_ratio'],row['cpu_p99_us']/deadline,abs_tol=2e-6):raise ValueError('inconsistent deadline ratio')
            if row['frame_overruns'] or (kind=='host' and row['underruns']):raise ValueError('DSP scheduling/audio underrun')
            if kind=='host':
                for f in ('cpu_misses','wall_misses'):
                    if row[f]!=int(row[f]) or not 0<=row[f]<=row['callbacks']:raise ValueError('invalid miss count')
            key=tuple(row[k] for k in KEYS)
            if key in local:raise ValueError('duplicate benchmark cell')
            local[key]=row;repeats.add(row['repeat']);all_rows.append(row)
        if len(repeats)!=1 or set(local)!=grid:raise ValueError('incomplete/mixed repeat grid')
        repeat=next(iter(repeats))
        if repeat in by_repeat:raise ValueError('duplicate repeat')
        by_repeat[repeat]=local
    if set(by_repeat)!={1,2,3}:raise ValueError('exactly three repeats 1,2,3 required')
    medians={}
    for key in sorted(grid):
        rows=[by_repeat[r][key] for r in (1,2,3)]
        medians[key]=dict(zip(KEYS,key),**{field:statistics.median(r[field] for r in rows)
            for field in ('cpu_mean_us','cpu_p99_us','cpu_max_us','wall_p99_us','cpu_p99_ratio')})
    worst=[]
    for rate,ch,block,profile,variant in itertools.product((48000,96000),(1,2),(32,64),PROFILES,VARIANTS[kind]):
        selected=[medians[(rate,ch,block,st,profile,variant)] for st in PITCHES]
        worst.append(dict(rate=rate,channels=ch,block=block,profile=profile,variant=variant,
            worst_pitch_median_cpu_p99_ratio=max(r['cpu_p99_ratio'] for r in selected)))
    improvement=[]
    for profile in PROFILES:
        selected=[k for k in grid if k[-2:]==(profile,'scheduled-simd')]
        changes={f:[] for f in ('cpu_p99_us','cpu_mean_us')}
        for key in selected:
            base=medians[(*key[:-1],'scalar')];candidate=medians[key]
            for f in changes:
                if base[f]<=0:raise ValueError('zero baseline timing')
                changes[f].append(100*(1-candidate[f]/base[f]))
        improvement.append(dict(profile=profile,cells=len(selected),median_p99_reduction_pct=statistics.median(changes['cpu_p99_us']),
                                median_mean_reduction_pct=statistics.median(changes['cpu_mean_us'])))
    extremes=[]
    for variant in VARIANTS[kind]:
        rows=[r for r in all_rows if r['variant']==variant]
        item=dict(variant=variant,measured_callbacks=sum(r['callbacks'] for r in rows),
            largest_raw_cpu_max_ratio=max(r['cpu_max_us']/(1e6*r['block']/r['rate']) for r in rows),
            largest_raw_cpu_p99_ratio=max(r['cpu_p99_ratio'] for r in rows))
        if kind=='host':item.update(cpu_deadline_misses=int(sum(r['cpu_misses'] for r in rows)),
            wall_deadline_misses=int(sum(r['wall_misses'] for r in rows)),
            largest_raw_wall_max_ratio=max(r['wall_max_us']/(1e6*r['block']/r['rate']) for r in rows))
        extremes.append(item)
    return dict(schema='boiled-egg.execution-benchmark-summary.v1',kind=kind,repeats=3,cells_per_repeat=len(grid),
        inputs=[dict(name=p.name,sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in paths],
        cells=list(medians.values()),worst_pitch=worst,paired_improvements=improvement,raw_extremes=extremes,
        interpretation='Descriptive same-machine results. Medians do not remove raw misses/maxima. '
                       'Zero algorithmic underruns is not zero callback deadline misses. No portable hard-RT guarantee.')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--kind',choices=VARIANTS,required=True)
    p.add_argument('--csv',type=Path,nargs=3,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();result=summarize(a.csv,a.kind)
    with a.output.open('x',encoding='utf-8') as stream:json.dump(result,stream,indent=2,allow_nan=False);stream.write('\n')
