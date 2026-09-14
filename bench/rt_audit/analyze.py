#!/usr/bin/env python3
"""Validate a complete experiment and report all tails without noise subtraction.

CPU-period exceedance is not a host xrun. Periodic release misses include wake,
harness, observer and callback time. A bad null control invalidates the platform
qualification, not the existence of a recorded DSP deadline miss.
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import itertools
import json
import math
import statistics
from collections import defaultdict
from pathlib import Path
from run_matrix import PROTOCOLS, digest

FIELDS=('index','cold','cpu_ns','wall_ns','outer_ns','period_ns','wake_late_ns',
        'response_ns','slack_ns','release_miss','status','output_hash')

def describe(values: list[int]) -> dict:
    if not values:return {'samples':0}
    ordered=sorted(values)
    return dict(samples=len(values),mean_ns=statistics.mean(values),
        p50_ns=ordered[math.ceil(.5*len(values))-1],p99_ns=ordered[math.ceil(.99*len(values))-1],
        p999_ns=ordered[math.ceil(.999*len(values))-1],max_ns=ordered[-1])

def miss_episodes(flags: list[bool]) -> dict:
    episodes=longest=current=0
    for flag in flags:
        if flag:
            if not current:episodes+=1
            current+=1;longest=max(longest,current)
        else:current=0
    return dict(count=sum(flags),episodes=episodes,longest_run=longest)

def validate_row(row: dict, index: int, meta: dict) -> None:
    if row['index']!=index or row['cold']!=int(index<meta['warmup']):raise ValueError('index/warmup mismatch')
    if row['status']!=0:raise ValueError('DSP returned an error')
    if row['outer_ns']<0:raise ValueError('negative outer duration')
    for key in ('cpu_ns','wall_ns'):
        measured=(meta['bracket']!='wall') if key=='cpu_ns' else (meta['bracket']!='cpu')
        if (measured and row[key]<0) or (not measured and row[key]!=-1):raise ValueError('clock availability mismatch')
    a=index*meta['block']*10**9//meta['rate'];b=(index+1)*meta['block']*10**9//meta['rate']
    if row['period_ns']!=b-a:raise ValueError('period rounding mismatch')
    if meta['schedule']=='periodic':
        if row['wake_late_ns']<0 or row['response_ns']!=row['wake_late_ns']+row['outer_ns']:
            raise ValueError('release response arithmetic mismatch')
        if row['slack_ns']!=row['period_ns']-row['response_ns'] or row['release_miss']!=int(row['slack_ns']<0):
            raise ValueError('deadline classification mismatch')
    elif (row['wake_late_ns'],row['response_ns'],row['slack_ns'],row['release_miss'])!=(-1,-1,0,0):
        raise ValueError('saturated run fabricated periodic data')

def load_run(root: Path, cell: dict, count: int) -> tuple[dict,str]:
    name=cell['name']
    if not name or Path(name).name!=name or '\\' in name:raise ValueError('unsafe artifact name')
    path=root/(name+'.csv');metadata=root/(name+'.json');receipt=json.loads((root/(name+'.receipt.json')).read_text())
    if receipt['returncode']!=0 or receipt['csv_sha256']!=digest(path) or receipt['metadata_sha256']!=digest(metadata):
        raise ValueError('failed or tampered trial')
    meta=json.loads(metadata.read_text())
    for key in ('repeat','rate','block','shift','workload','schedule','bracket'):
        if meta[key]!=cell[key]:raise ValueError('trial/config mismatch')
    if meta['count']!=count or meta['errors']!=0 or meta['schema']!='boiled-egg.rt-audit.v1':raise ValueError('metadata mismatch')
    required=(meta['latency_frames']+(meta['rate']+1)//2+meta['block']-1)//meta['block']
    if meta['warmup']!=max(meta['requested_warmup'],required):raise ValueError('insufficient/inconsistent warmup')
    rows=[];fingerprint=hashlib.sha256()
    with path.open(newline='') as f:
        reader=csv.DictReader(f)
        if reader.fieldnames!=list(FIELDS):raise ValueError('wrong CSV header')
        for i,raw in enumerate(reader):
            if None in raw or any(v is None for v in raw.values()):raise ValueError('ragged CSV')
            code=raw.pop('output_hash')
            if not code or any(c not in '0123456789abcdef' for c in code):raise ValueError('invalid output fingerprint')
            fingerprint.update((code+'\n').encode())
            row={k:int(v) for k,v in raw.items()};validate_row(row,i,meta);rows.append(row)
    if len(rows)!=count+meta['warmup'] or code!=meta['output_fingerprint']:raise ValueError('incomplete trial')
    result=dict(**cell,metadata=meta,receipt_sha256=digest(root/(name+'.receipt.json')),
                csv_sha256=digest(path),cold={},steady={})
    for stage,part in (('cold',rows[:meta['warmup']]),('steady',rows[meta['warmup']:])):
        result[stage]={key:describe([r[key] for r in part if r[key]>=0])
            for key in ('cpu_ns','wall_ns','outer_ns','wake_late_ns','response_ns')}
        result[stage]['cpu_period_exceedances']=sum(r['cpu_ns']>r['period_ns'] for r in part)
        result[stage]['wall_period_exceedances']=sum(r['wall_ns']>r['period_ns'] for r in part)
        result[stage]['release_misses']=miss_episodes([bool(r['release_miss']) for r in part])
        result[stage]['already_late_on_entry']=sum(r['wake_late_ns']>=r['period_ns'] for r in part)
    return result,fingerprint.hexdigest()

def analyze(root: Path) -> dict:
    plan=json.loads((root/'plan.json').read_text());complete=json.loads((root/'COMPLETE.json').read_text())
    if complete['plan_sha256']!=digest(root/'plan.json') or complete['runs']!=len(plan['runs']):raise ValueError('incomplete plan')
    if plan['matrix']=='observer':
        cells=itertools.product(plan['probes'],('dsp','control','noop'),PROTOCOLS,(96000,),(32,),(7,),(1,2,3))
    elif plan['matrix']=='periodic':
        cells=itertools.product(plan['probes'],('dsp',),(('periodic','wall'),),(48000,96000),(32,64),(-12,-7,-3,3,7,12),(1,2,3))
    elif plan['matrix']=='capacity':
        cells=itertools.product(plan['probes'],('dsp',),(('saturated','wall'),),(48000,96000),(32,64),(-12,-7,-3,0,3,7,12),(1,2,3))
    else:raise ValueError('unknown matrix')
    expected=set(cells);actual=set();names=set();results=[];hashes=defaultdict(set)
    for c in plan['runs']:
        key=(c['label'],c['workload'],(c['schedule'],c['bracket']),c['rate'],c['block'],c['shift'],c['repeat'])
        if key in actual or c['name'] in names:raise ValueError('duplicate run')
        actual.add(key);names.add(c['name'])
        r,h=load_run(root,c,plan['count']);results.append(r)
        # Same workload, inputs and number of calls; timing must not change output.
        hashes[(c['label'],c['workload'],c['rate'],c['block'],c['shift'],r['metadata']['warmup'])].add(h)
    if actual!=expected:raise ValueError('missing or extra matrix cell')
    if any(len(h)!=1 for h in hashes.values()):raise ValueError('output changed across measurement protocols/repeats')
    return dict(schema='boiled-egg.rt-audit-summary.v1',plan_sha256=digest(root/'plan.json'),runs=results,
        output_protocol_invariance=True,steady_callbacks=len(results)*plan['count'],
        quantile='nearest rank; raw and cold maxima retained; no outlier rejection or control subtraction',
        interpretation='Shared-machine timing is descriptive. Periodic misses include harness and wake lateness. '
        'Saturated CPU-period exceedances are NOT observed audio xruns. Passing functional checks does not establish hard RT.',
        hard_realtime_qualified=False)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('root',type=Path);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();result=analyze(a.root)
    with a.output.open('x') as f:json.dump(result,f,indent=2,allow_nan=False);f.write('\n')
