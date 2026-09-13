#!/usr/bin/env python3
"""Summarize diagnostic callback CSVs without hiding cold starts or raw tails.

RUSAGE_THREAD cannot see host/hypervisor events. A lack of page faults/context
switches is not a proof that the DSP itself caused a timing spike. Fixed-work
and no-op controls are reported separately, never counted as audio callbacks.
"""
from __future__ import annotations
import argparse,csv,hashlib,json,math
from pathlib import Path
import numpy as np

FIELDS=('repeat','profile','rate','block','pitch','input','ftz','instrument','index',
        'cpu_ns','wall_ns','minor_faults','major_faults','voluntary','involuntary',
        'cpu_before','cpu_after','completed_frames','max_frame_steps','output_energy')
META=('repeat','profile','rate','block','pitch','input','ftz','instrument')


def read(path: Path) -> list[dict]:
    with path.open(newline='',encoding='utf-8') as stream:
        reader=csv.DictReader(stream)
        if reader.fieldnames!=list(FIELDS):raise ValueError('unexpected probe header')
        raw=list(reader)
    if not raw:raise ValueError('empty probe')
    rows=[]
    for i,r in enumerate(raw):
        if None in r or any(v is None for v in r.values()):raise ValueError('malformed probe row')
        row={k:(v if k=='input' else float(v) if k in ('pitch','output_energy') else int(v)) for k,v in r.items()}
        if any(not math.isfinite(v) for v in row.values() if isinstance(v,(int,float))):raise ValueError('nonfinite probe')
        if row['index']!=i or row['rate']<=0 or row['block']<=0 or row['cpu_ns']<0 or row['wall_ns']<0:
            raise ValueError('invalid index or timing')
        if row['ftz'] not in (0,1) or row['instrument'] not in (0,1):raise ValueError('invalid probe flags')
        if rows and any(row[k]!=rows[0][k] for k in META):raise ValueError('mixed probe condition')
        rows.append(row)
    return rows


def analyze(paths: list[Path],warmup_seconds: float=1.) -> dict:
    if not paths or not math.isfinite(warmup_seconds) or warmup_seconds<=0:raise ValueError('positive warmup and nonempty inputs required')
    summaries=[];extremes=[];identities=set();sets={}
    for path in paths:
        rows=read(path);first=rows[0];identity=tuple(first[k] for k in META)
        if identity in identities:raise ValueError('duplicate probe condition/repeat')
        identities.add(identity)
        warm=math.ceil(first['rate']*warmup_seconds/first['block']);deadline=1e9*first['block']/first['rate']
        if len(rows)<=warm:raise ValueError('no steady samples after declared warmup')
        for phase,part in [('cold',rows[:warm]),('steady',rows[warm:])]:
            misses=[r for r in part if r['cpu_ns']>deadline]
            cpu=np.array([r['cpu_ns'] for r in part])/1000
            summaries.append(dict(file=path.name,sha256=hashlib.sha256(path.read_bytes()).hexdigest(),phase=phase,rows=len(part),
                **{k:first[k] for k in META},cpu_median_us=float(np.median(cpu)),cpu_p99_us=float(np.quantile(cpu,.99)),
                cpu_max_us=float(cpu.max()),wall_max_us=max(r['wall_ns'] for r in part)/1000,
                cpu_misses=len(misses),wall_misses=sum(r['wall_ns']>deadline for r in part),
                minor_faults=sum(r['minor_faults'] for r in part),major_faults=sum(r['major_faults'] for r in part),
                involuntary_switches=sum(r['involuntary'] for r in part),
                misses_with_faults=sum(r['minor_faults']+r['major_faults']>0 for r in misses),
                misses_with_guest_switch=sum(r['voluntary']+r['involuntary']>0 for r in misses),
                migrations=sum(r['cpu_before']!=r['cpu_after'] for r in part)))
        for row in sorted(rows[warm:],key=lambda r:r['cpu_ns'],reverse=True)[:10]:extremes.append(dict(file=path.name,**row))
        if first['input']=='normal' and first['instrument']==1:
            key=tuple(first[k] for k in META if k!='repeat')
            sets.setdefault(key,{})[first['repeat']]={r['index'] for r in rows[warm:] if r['cpu_ns']>deadline}
    overlap=[]
    for key,repeats in sets.items():
        if set(repeats)!={1,2,3}:continue
        overlap.append(dict(condition=list(key),total_events=sum(len(s) for s in repeats.values()),
            shared_indices_any_pair=len((repeats[1]&repeats[2])|(repeats[1]&repeats[3])|(repeats[2]&repeats[3])),
            shared_all_three=len(repeats[1]&repeats[2]&repeats[3])))
    return dict(schema='boiled-egg.rt-tail-probe-summary.v1',warmup_input_seconds=warmup_seconds,
        summaries=summaries,extremes=extremes,repeat_overlap=overlap,
        interpretation='Cold and steady periods retained. CPU and wall deadlines distinct. '
            'Guest OS counters do not identify host/hypervisor scheduling. No causal or hard-RT verdict.')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--csv',type=Path,nargs='+',required=True)
    p.add_argument('--warmup-seconds',type=float,default=1.);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();report=analyze(a.csv,a.warmup_seconds)
    with a.output.open('x',encoding='utf-8') as stream:json.dump(report,stream,indent=2,allow_nan=False);stream.write('\n')
