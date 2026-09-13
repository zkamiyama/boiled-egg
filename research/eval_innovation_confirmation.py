#!/usr/bin/env python3
"""Frozen-design confirmation: new oscillator seeds or preselected training audio.

This is not a native-vendor benchmark or pristine population validation. Seeded
inputs are fixed before measurements. Original catalog categories are retained.
No threshold, mode, or source is selected based on measured output quality.
"""
from __future__ import annotations
import argparse
import concurrent.futures as cf
import json
import random
import tempfile
from collections import defaultdict
from pathlib import Path
import numpy as np
import soundfile as sf
import eval_phase_owner_study as e

SEEDS=tuple(range(120000,120008))
SHIFTS=(-12,-7,-3,3,7,12)
SELECTION_SEED=20260914
VARIANTS=('baseline','guard','refined')  # ordinary, bounded predecessor, innovation


def select_sources(sources):
    groups=defaultdict(list)
    for row in sources:groups[row['category']].append(row)
    if set(groups)!={'music','solo','voice'}:raise ValueError('expected original three training categories')
    rng=random.Random(SELECTION_SEED);selected=[]
    for category,rows in sorted(groups.items()):
        if len(rows)<4:raise ValueError('insufficient category coverage')
        selected.extend(rng.sample(sorted(rows,key=lambda r:r['stem']),4))
    return sorted(selected,key=lambda r:r['stem'])


def work(job):
    suite,item,rate,shift,refs,builds=job
    ratio=float(np.float32(2**(shift/12)))
    with tempfile.TemporaryDirectory(prefix='innovation-confirmation-') as tmp:
        destination=Path(tmp)/'render.wav'
        if suite=='banks':
            seed=item
            x,_=e.s.oscillator_bank(seed-93173,rate,1.)
            oracle,meta=e.s.oscillator_bank(seed-93173,rate,ratio)
            source=Path(tmp)/'input.wav';sf.write(source,x,rate,subtype='FLOAT')
            common=dict(source=f'seed{seed}',seed=seed,category='analytical',formant='off')
        else:
            source=e.e.inside(refs,item['reference_name']);x,actual_rate=e.e.checked_audio(source)
            if actual_rate!=rate or e.e.fingerprint(source)!=item['reference_sha256']:raise ValueError('source metadata/hash mismatch')
            common=dict(source=item['stem'],category=item['category'],formant='harmonic')
        digest=e.e.fingerprint(source);rows=[]
        for variant,build in zip(VARIANTS,builds):
            y,sha=e.render(build,source,destination,ratio,rate,common['formant'])
            if y.shape!=x.shape:raise ValueError('render shape mismatch')
            metrics=e.q.diagnose(y,oracle,meta,rate) if suite=='banks' else e.z.pitch_metrics(x,y,rate)
            rows.append(dict(**common,shift=shift,rate=rate,variant=variant,frames=len(y),channels=y.shape[1],
                input_sha256=digest,render_sha256=sha,peak=float(np.max(np.abs(y))),**metrics))
        if e.e.fingerprint(source)!=digest:raise ValueError('source changed during comparison')
    return rows


def run(args):
    if args.output.exists() or args.workers<1:raise ValueError('new output and positive workers required')
    builds=[getattr(args,k).resolve(strict=True) for k in ('baseline','bounded','innovation')]
    hashes={v:e.e.fingerprint(b/'boiled_egg_pv_rt_cli') for v,b in zip(VARIANTS,builds)}
    sources=[];inputs={}
    if args.suite=='banks':
        jobs=[('banks',s,r,t,None,builds) for s in SEEDS for r in (48000,96000) for t in SHIFTS]
        expected={(f'seed{s}',r,t,v) for s in SEEDS for r in (48000,96000) for t in SHIFTS for v in VARIANTS}
    else:
        if not args.refs or not args.catalog:raise ValueError('reference directory and catalog required')
        sources=select_sources(e.e.preflight(args.refs,args.catalog))
        inputs[str(args.catalog.resolve())]=e.e.fingerprint(args.catalog)
        inputs.update({str(e.e.inside(args.refs,r['reference_name'])):r['reference_sha256'] for r in sources})
        jobs=[('training',r,r['sample_rate'],t,args.refs,builds) for r in sources for t in SHIFTS]
        expected={(r['stem'],r['sample_rate'],t,v) for r in sources for t in SHIFTS for v in VARIANTS}
    dependencies={str(Path(m.__file__).resolve()):e.e.fingerprint(Path(m.__file__)) for m in (e,e.s,e.q,e.z,e.q.m)}
    dependencies[str(Path(__file__).resolve())]=e.e.fingerprint(Path(__file__))
    args.output.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.innovation-confirmation-',dir=args.output.parent) as tmp:
        result=Path(tmp)/'result';result.mkdir();rows=[]
        with cf.ProcessPoolExecutor(args.workers) as pool:
            for i,part in enumerate(pool.map(work,jobs),1):
                rows.extend(part)
                if i%12==0:print(f'{args.suite} {i}/{len(jobs)}',flush=True)
        e.validate_rows(rows,expected,('source','rate','shift','variant'))
        for v,b in zip(VARIANTS,builds):
            if e.e.fingerprint(b/'boiled_egg_pv_rt_cli')!=hashes[v]:raise ValueError('renderer changed')
        for path,digest in {**inputs,**dependencies}.items():
            if e.e.fingerprint(Path(path))!=digest:raise ValueError('input or analysis changed')
        e.write_csv(result/'measurements.csv',rows)
        report=dict(schema='boiled-egg.innovation-confirmation.v1',suite=args.suite,rows=len(rows),
            executables=hashes,inputs=inputs,analysis=dependencies,sources=sources,seeds=list(SEEDS) if args.suite=='banks' else [],
            selection_seed=SELECTION_SEED,variant_names=dict(baseline='ordinary Fuzzy',guard='bounded owner predecessor',refined='innovation-weighted guard'),
            measurements_sha256=e.e.fingerprint(result/'measurements.csv'),native_baseline=False,listening_status='not_listened',
            protocol='Design frozen before these outputs. No subsequent tuning. Training subset is separate from the20 test references; '
            'the archive has been studied historically, so it is not a pristine population holdout. Four sources per original catalog category.')
        (result/'summary.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n');result.rename(args.output)
    return report

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for k in ('baseline','bounded','innovation','output'):p.add_argument('--'+k,type=Path,required=True)
    p.add_argument('--suite',choices=('banks','training'),required=True)
    for k in ('refs','catalog'):p.add_argument('--'+k,type=Path)
    p.add_argument('--workers',type=int,default=3)
    print(run(p.parse_args())['rows'],'confirmed render rows')
