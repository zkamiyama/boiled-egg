#!/usr/bin/env python3
"""Fixed policy:1200 steady states x3 repeats, statewise best <=80% period.

Raw misses/maxima and actual successful full runs are retained. Minimum samples
are an empirical capacity indicator, never a WCET or synthetic continuous run.
This is wall-only in a shared VM; no empty-clock quantile subtraction.
"""
import argparse,csv,itertools,json,hashlib,math
from pathlib import Path
import numpy as np
KEYS=('rate','quality','policy','block')
GRID=set(itertools.product((48000,96000),(0,1),(0,1,2),(32,64)))

def summarize(paths):
 groups={};cold=0
 for path in paths:
  with path.open(newline='') as f:
   reader=csv.DictReader(f)
   if reader.fieldnames!=['repeat',*KEYS,'index','warmup','wall_ns','fingerprint']:raise ValueError('unexpected header')
   rows=[{k:int(v) for k,v in r.items()} for r in reader]
  repeats={r['repeat'] for r in rows}
  if len(repeats)!=1:raise ValueError('mixed repeat')
  repeat=repeats.pop()
  if repeat not in (1,2,3) or repeat in groups:raise ValueError('duplicate/invalid repeat')
  collected={}
  for r in rows:
   key=tuple(r[k] for k in KEYS)
   if key not in GRID or r['wall_ns']<0 or r['warmup'] not in (0,1):raise ValueError('invalid measurement')
   collected.setdefault(key,[]).append(r)
  if set(collected)!=GRID:raise ValueError('incomplete configuration grid')
  for key,rr in collected.items():
   if [r['index'] for r in rr]!=list(range(len(rr))):raise ValueError('missing/duplicated input state')
   if sum(not r['warmup'] for r in rr)!=1200:raise ValueError('wrong steady count')
   cold+=sum(r['warmup'] for r in rr)
  groups[repeat]=collected
 if set(groups)!={1,2,3}:raise ValueError('three repeats required')
 results=[];passed=True
 for key in sorted(GRID):
  replicas=[groups[r][key] for r in (1,2,3)]
  for a,b in zip(replicas,replicas[1:]):
   if len(a)!=len(b) or any(x['fingerprint']!=y['fingerprint'] or x['warmup']!=y['warmup'] for x,y in zip(a,b)):raise ValueError('different processing state/output across repeats')
  matrix=np.array([[r['wall_ns'] for r in rr if not r['warmup']] for rr in replicas],float)
  deadline=key[3]*1e9/key[0];best=matrix.min(axis=0)/deadline;second=np.sort(matrix,axis=0)[1]/deadline
  success=bool(best.max()<=.8);passed&=success
  results.append(dict(zip(KEYS,key),state_best_worst_ratio=float(best.max()),second_best_worst_ratio=float(second.max()),
    capacity_pass=success,raw_max_ratio=float(matrix.max()/deadline),raw_deadline_misses=int((matrix>deadline).sum()),
    full_successful_runs=int((matrix.max(axis=1)<=deadline).sum()),per_run_p99_ratio=list(map(float,np.quantile(matrix,.99,axis=1)/deadline))))
 return dict(schema='boiled-egg.dynamic-capacity.v1',budget_fraction=.8,repeats=3,steady_per_cell=1200,configurations=24,
    measured_steady_callbacks=24*3*1200,cold_callbacks=cold,passed=bool(passed),rows=results,
    file_sha256={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in paths},
    notes='All raw rows kept. Same library/input/event path; output fingerprints verified per state. Best-state capacity is not a continuous successful run or hard-RT guarantee.')
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--csv',type=Path,nargs=3,required=True);p.add_argument('--output',type=Path,required=True)
 a=p.parse_args();result=summarize(a.csv)
 with a.output.open('x') as f:json.dump(result,f,indent=2,allow_nan=False);f.write('\n')
 print(sum(r['capacity_pass'] for r in result['rows']),'/24 capacity conditions')
 raise SystemExit(not result['passed'])
