#!/usr/bin/env python3
"""Same-input product CLI replay for behavior-preserving optimizations.

Requires development NumPy/SoundFile. Audio remains local; reports contain only
metadata and hashes. This is output equivalence, not a native-vendor comparison.
"""
from __future__ import annotations
import argparse
import concurrent.futures as cf
import csv
import hashlib
import json
import math
import subprocess
import tempfile
from pathlib import Path
import numpy as np
import soundfile as sf

SHIFTS=(-12,-7,-3,0,3,7,12)
TIMES=(.5,1.,2.)


def digest(path): return hashlib.sha256(path.read_bytes()).hexdigest()


def source_job(job):
    source, record, baseline, candidate = job
    if digest(source)!=record['sha256']: raise ValueError('source changed after plan')
    rows=[]
    with tempfile.TemporaryDirectory(prefix='product-cache-replay-') as tmp:
        for time in TIMES:
            for shift in SHIFTS:
                files=[]
                for label,cli,block in (('before',baseline,256),('candidate',candidate,32)):
                    output=Path(tmp)/(label+'.wav')
                    command=[str(cli),str(source),str(output),'--time',str(time),'--pitch',str(shift),'--block',str(block)]
                    run=subprocess.run(command,capture_output=True,text=True,timeout=120)
                    if run.returncode: raise RuntimeError(f'{source.name}/{time}/{shift}: {run.stderr}')
                    x,rate=sf.read(output,always_2d=True,dtype='float32')
                    expected=math.floor(record['frames']*time+.5)
                    if rate!=record['rate'] or x.shape!=(expected,record['channels']) or not np.isfinite(x).all():
                        raise ValueError('render rate/frame/channel/finite mismatch')
                    files.append(digest(output))
                rows.append(dict(source=source.name,source_sha256=record['sha256'],rate=record['rate'],
                    channels=record['channels'],time_ratio=time,shift=shift,frames=expected,
                    baseline_sha256=files[0],candidate_sha256=files[1],byte_identical=files[0]==files[1]))
    if digest(source)!=record['sha256']: raise ValueError('source changed during replay')
    return rows


def run(args):
    if args.output.exists() or args.workers<1: raise ValueError('new output and positive workers required')
    baseline,candidate=[p.resolve(strict=True) for p in (args.baseline,args.candidate)]
    dependencies={str(p.resolve(strict=True)):digest(p) for p in [baseline,candidate,*args.dependency]}
    sources=[]
    for p in sorted(args.references.glob('*.wav')):
        x,rate=sf.read(p,always_2d=True,dtype='float32')
        if not len(x) or not np.isfinite(x).all(): raise ValueError('invalid reference audio')
        sources.append((p.resolve(),dict(name=p.name,sha256=digest(p),rate=rate,frames=len(x),channels=x.shape[1])))
    if not sources: raise ValueError('no reference WAV files')
    args.output.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.product-replay-',dir=args.output.parent) as tmp:
        staging=Path(tmp)/'result';staging.mkdir();rows=[]
        with cf.ProcessPoolExecutor(max_workers=args.workers) as pool:
            for i,part in enumerate(pool.map(source_job,[(p,r,baseline,candidate) for p,r in sources]),1):
                rows.extend(part);print(f'{i}/{len(sources)} references',flush=True)
        expected={(r['name'],t,s) for p,r in sources for t in TIMES for s in SHIFTS}
        actual={(r['source'],r['time_ratio'],r['shift']) for r in rows}
        if len(rows)!=len(actual) or actual!=expected: raise ValueError('incomplete replay grid')
        if any(digest(Path(p))!=h for p,h in dependencies.items()): raise ValueError('binary/dependency changed')
        with (staging/'comparisons.csv').open('w',newline='',encoding='utf-8') as f:
            writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
        result=dict(schema='boiled-egg.product-cache-replay.v1',pairs=len(rows),renders=2*len(rows),
            identical=sum(r['byte_identical'] for r in rows),passed=all(r['byte_identical'] for r in rows),
            sources=[r for p,r in sources],dependencies=dependencies,script_sha256=digest(Path(__file__)),
            comparisons_sha256=digest(staging/'comparisons.csv'),baseline_block=256,candidate_block=32,
            interpretation='Complete-WAV same-toolchain equality; not a new perceptual/native quality ranking.')
        (staging/'summary.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n');staging.rename(args.output)
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for key in ('references','baseline','candidate','output'): p.add_argument('--'+key,type=Path,required=True)
    p.add_argument('--dependency',type=Path,action='append',default=[])
    p.add_argument('--workers',type=int,default=2)
    result=run(p.parse_args());print(result['identical'],'/',result['pairs'],'identical WAV pairs')
    raise SystemExit(0 if result['passed'] else 2)
