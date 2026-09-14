#!/usr/bin/env python3
"""Public SDK/private PV API replay: same kernel, not independent sound quality.

No fitted alignment, normalization, MOS, native comparison or retained WAVs.
"""
from __future__ import annotations
import argparse, concurrent.futures as cf, csv, hashlib, itertools, json, subprocess, tempfile
from pathlib import Path
import numpy as np
import soundfile as sf

SHIFTS=(-12,-7,-3,3,7,12)
POLICIES=('off','harmonic','monophonic')
QUALITIES=('general','transient')

def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for data in iter(lambda:f.read(1<<20),b''):h.update(data)
    return h.hexdigest()

def work(job):
    entry,public,oracle=job;src=Path(entry['path']);rows=[]
    if sha(src)!=entry['sha256']:raise ValueError('reference changed')
    conditions=[('pitch',st,1.,float(np.float32(2**(st/12)))) for st in SHIFTS]
    conditions += [('stretch',0,t,1.) for t in (.5,2.)]
    with tempfile.TemporaryDirectory(prefix='backend-replay-') as tmp:
        a,b=Path(tmp)/'public.wav',Path(tmp)/'oracle.wav'
        for (operation,shift,time,pitch),quality,policy in itertools.product(conditions,QUALITIES,POLICIES):
            commands=([str(public),str(src),str(a),'--backend','pv','--allow-experimental','--quality',quality,
                       '--formant',policy,'--time',str(time),'--pitch-ratio',format(pitch,'.9g'),'--block','32'],
                      [str(oracle),str(src),str(b),str(QUALITIES.index(quality)),str(POLICIES.index(policy)),
                       str(time),format(pitch,'.9g'),'1','256'])
            for command in commands:
                p=subprocess.run(command,capture_output=True,text=True,timeout=120)
                if p.returncode:raise RuntimeError(f'{entry["name"]}: {p.stderr}')
            x,rate=sf.read(a,always_2d=True);y,sr=sf.read(b,always_2d=True)
            frames=int(np.floor(entry['frames']*time+.5))
            if rate!=sr or rate!=entry['rate'] or x.shape!=y.shape or x.shape!=(frames,entry['channels']):raise ValueError('metadata mismatch')
            if not np.isfinite(x).all() or not np.isfinite(y).all():raise ValueError('nonfinite render')
            ah,bh=sha(a),sha(b)
            rows.append(dict(source=entry['name'],operation=operation,shift=shift,time_ratio=time,pitch_ratio=pitch,
                quality=quality,policy=policy,rate=rate,frames=frames,channels=x.shape[1],source_sha256=entry['sha256'],
                public_sha256=ah,oracle_sha256=bh,byte_identical=ah==bh,max_sample_difference=float(np.max(abs(x-y),initial=0)),
                peak=float(np.max(abs(x),initial=0))))
            a.unlink();b.unlink()
    if sha(src)!=entry['sha256']:raise ValueError('source mutated')
    return rows

def run(args):
    if args.workers<1 or args.output.exists():raise ValueError('positive workers and new output required')
    root=args.refs.resolve(strict=True);sources=[];names=set()
    for path in sorted(root.rglob('*.wav')):
        if not path.resolve().is_relative_to(root) or path.name.casefold() in names:raise ValueError('ambiguous or escaping path')
        names.add(path.name.casefold());x,rate=sf.read(path,always_2d=True)
        if rate not in (44100,48000,88200,96000) or x.shape[1] not in (1,2) or not len(x) or not np.isfinite(x).all():raise ValueError('invalid reference')
        sources.append(dict(name=path.name,path=str(path),sha256=sha(path),rate=rate,frames=len(x),channels=x.shape[1]))
    if not sources:raise ValueError('no WAV sources')
    public=args.public.resolve(strict=True);oracle=args.oracle.resolve(strict=True)
    provenance=dict(public=sha(public),oracle=sha(oracle),script=sha(Path(__file__)))
    args.output.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.backend-replay-',dir=args.output.parent) as tmp:
        staging=Path(tmp)/'report';staging.mkdir();rows=[]
        with cf.ProcessPoolExecutor(args.workers) as pool:
            for i,r in enumerate(pool.map(work,[(s,public,oracle) for s in sources]),1):
                rows+=r;print('sources',i,'/',len(sources),'pairs',len(rows),flush=True)
        expected={(s['name'],op,st,t,q,p) for s in sources for op,st,t in
                  [('pitch',st,1.) for st in SHIFTS]+[('stretch',0,t) for t in (.5,2.)] for q in QUALITIES for p in POLICIES}
        actual={(r['source'],r['operation'],r['shift'],r['time_ratio'],r['quality'],r['policy']) for r in rows}
        if actual!=expected or len(rows)!=len(actual):raise ValueError('incomplete/duplicate grid')
        if provenance!=dict(public=sha(public),oracle=sha(oracle),script=sha(Path(__file__))):raise ValueError('executable/script changed')
        with (staging/'comparisons.csv').open('w',newline='',encoding='utf-8') as f:
            w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
        result=dict(schema='boiled-egg.public-spectral-replay.v1',sources=sources,pairs=len(rows),rendered_wavs=2*len(rows),
            byte_identical=sum(r['byte_identical'] for r in rows),max_sample_difference=max(r['max_sample_difference'] for r in rows),
            public_block=32,private_block=256,provenance=provenance,comparisons_sha256=sha(staging/'comparisons.csv'),
            passed=all(r['byte_identical'] for r in rows),
            scope='API-routing equivalence of the same private PV kernel. Not independent quality, listening or native-vendor validation.')
        (staging/'summary.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n');staging.rename(args.output)
    return result

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for key in ('refs','public','oracle','output'):p.add_argument('--'+key,type=Path,required=True)
    p.add_argument('--workers',type=int,default=2);r=run(p.parse_args())
    print(r['byte_identical'],'/',r['pairs'],'identical');raise SystemExit(not r['passed'])
