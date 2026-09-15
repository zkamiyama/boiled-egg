#!/usr/bin/env python3
"""Byte-exact legacy 10-ms pitch-event regression across two shared libraries."""
import argparse, concurrent.futures as cf, hashlib, json, sys
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'dynamic_pitch'))
import evaluate as e

def one(job):
    old,new,rate,quality,policy,frequency=job
    a,da,ha=e.render(e.library(old),rate,quality,policy,frequency,32)
    b,db,hb=e.render(e.library(new),rate,quality,policy,frequency,32)
    return dict(rate=rate,quality=quality,policy=policy,frequency=frequency,old_sha256=ha,new_sha256=hb,
        identical=ha==hb and da==db and np.array_equal(a,b))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for k in ('baseline','candidate','output'):p.add_argument('--'+k,type=Path,required=True)
    a=p.parse_args()
    if a.output.exists():raise ValueError('new output required')
    hashes={k:e.sha(getattr(a,k)) for k in ('baseline','candidate')}
    jobs=[(a.baseline,a.candidate,r,q,f,hz) for r in (48000,96000) for q in (0,1) for f in (0,1,2) for hz in (55.,220.,6200.)]
    with cf.ProcessPoolExecutor(2) as pool:rows=list(pool.map(one,jobs))
    if any(e.sha(getattr(a,k))!=h for k,h in hashes.items()):raise ValueError('library changed')
    result=dict(pairs=len(rows),identical=sum(r['identical'] for r in rows),libraries=hashes,rows=rows,
                source_sha256=e.sha(Path(__file__)),dependency_sha256=e.sha(Path(e.__file__)))
    with a.output.open('x') as f:json.dump(result,f,indent=2,allow_nan=False);f.write('\n')
    print(result['identical'],'/',len(rows),'legacy trajectories identical')
    raise SystemExit(result['identical']!=len(rows))
