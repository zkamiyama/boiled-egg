#!/usr/bin/env python3
"""Post-design validation: eight new banks (seeds93273..93280), never a MOS test."""
import argparse, concurrent.futures as cf, json, tempfile
from pathlib import Path
import numpy as np
import soundfile as sf
import eval_phase_owner_study as e

def job(a):
    seed,rate,shift,builds=a
    ratio=float(np.float32(2**(shift/12)))
    x,_=e.s.oscillator_bank(seed,rate,1.);ideal,meta=e.s.oscillator_bank(seed,rate,ratio)
    rows=[]
    with tempfile.TemporaryDirectory(prefix='owner-new-bank-') as tmp:
        src,dst=Path(tmp)/'source.wav',Path(tmp)/'render.wav'
        sf.write(src,x,rate,subtype='FLOAT');digest=e.e.fingerprint(src)
        for label,build in zip(e.VARIANTS,builds):
            y,sha=e.render(build,src,dst,ratio,rate,'off')
            if y.shape!=x.shape:raise ValueError('shape mismatch')
            rows.append(dict(seed=93173+seed,rate=rate,shift=shift,variant=label,input_sha256=digest,
                render_sha256=sha,peak=float(np.max(np.abs(y))),**e.q.diagnose(y,ideal,meta,rate)))
    return rows

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for k in (*e.VARIANTS,'output'):p.add_argument('--'+k,type=Path,required=True)
    p.add_argument('--workers',type=int,default=2);a=p.parse_args()
    if a.output.exists() or a.workers<1:raise ValueError('absent output and positive workers required')
    builds=[getattr(a,k).resolve(strict=True) for k in e.VARIANTS]
    hashes={k:e.e.fingerprint(b/'boiled_egg_pv_rt_cli') for k,b in zip(e.VARIANTS,builds)}
    jobs=[(s,r,t,builds) for s in range(100,108) for r in (48000,96000) for t in (-12,-7,-3,3,7,12)]
    rows=[]
    with cf.ProcessPoolExecutor(a.workers) as pool:
        for part in pool.map(job,jobs):rows+=part
    e.validate_rows(rows,{(93173+s,r,t,k) for s,r,t,b in jobs for k in e.VARIANTS},('seed','rate','shift','variant'))
    for k,b in zip(e.VARIANTS,builds):
        if e.e.fingerprint(b/'boiled_egg_pv_rt_cli')!=hashes[k]:raise ValueError('renderer changed')
    a.output.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.new-banks-',dir=a.output.parent) as tmp:
        dest=Path(tmp)/'result';dest.mkdir();e.write_csv(dest/'measurements.csv',rows)
        report=dict(rows=len(rows),seeds=list(range(93273,93281)),executables=hashes,
            script_sha256=e.e.fingerprint(Path(__file__)),fixture_sha256=e.e.fingerprint(Path(e.s.__file__)),
            evaluator_sha256=e.e.fingerprint(Path(e.__file__)),measurements_sha256=e.e.fingerprint(dest/'measurements.csv'),
            hypothesis='Bounded neighbor reassignment retains or improves old-guard partial balance on new banks.',
            listening_status='not_listened',native_baseline=False)
        (dest/'summary.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n');dest.rename(a.output)
    print(len(rows),'new-bank renders complete')
