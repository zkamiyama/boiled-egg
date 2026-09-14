#!/usr/bin/env python3
"""Compare continuous pitch/formant automation at block32 and257 on supplied WAVs.

Integration evidence only: both paths use the same loaded SDK, not an independent
quality reference or native vendor. Delay compensation is the API value, not a
fitted shift. Original/processed audio is not published by this runner.
"""
from __future__ import annotations
import argparse
import concurrent.futures as cf
import ctypes as c
import csv
import hashlib
import json
import tempfile
from pathlib import Path
import numpy as np
import soundfile as sf
import evaluate as core

SHIFTS=(-12,-7,-3,3,7,12,0)
FORMANTS=(1.,.8,1.2,.9,1.1,1.,1.)


def schedule(frames:int,rate:int,policy:int):
    if frames<rate:raise ValueError('at least one second of source audio required')
    # Fixed fractions use the same source-clock positions for every variant.
    events=[]
    for i,(shift,formant) in enumerate(zip(SHIFTS,FORMANTS),1):
        at=(i*frames)//8
        events.append((at,2,float(np.float32(2**(shift/12)))))
        if policy:events.append((at,4,formant))
    return events


def render(lib,x,rate,quality,policy,block):
    channels=len(x);config=lib.boiledegg_default_config(rate,channels);config.block=257
    b=lib.boiledegg_default_backend_config();b.backend=1;b.quality=quality;b.policy=policy;b.io=2;b.flags=3
    b.time=b.pitch=b.formant=1.;status=c.c_int()
    h=lib.boiledegg_create_backend(c.byref(config),c.byref(b),c.byref(status))
    if not h or status.value:raise ValueError(f'create failed: {status.value}')
    try:
        rt=core.Runtime();rt.size=c.sizeof(rt)
        if lib.boiledegg_get_runtime_info(h,c.byref(rt)):raise ValueError('runtime metadata')
        delay=rt.latency;frames=x.shape[1];source=np.pad(x,((0,0),(0,delay)));out=np.zeros_like(source)
        events=schedule(frames,rate,policy)
        for pos in range(0,source.shape[1],block):
            count=min(block,source.shape[1]-pos)
            inp=(core.FloatPtr*channels)(*[source[ch,pos:].ctypes.data_as(core.FloatPtr) for ch in range(channels)])
            dst=(core.FloatPtr*channels)(*[out[ch,pos:].ctypes.data_as(core.FloatPtr) for ch in range(channels)])
            ev=[core.Event(c.sizeof(core.Event),at-pos,parameter,value) for at,parameter,value in events if pos<=at<pos+count]
            if lib.boiledegg_process_realtime(h,inp,dst,count,(core.Event*len(ev))(*ev),len(ev)):raise ValueError('SDK process failure')
        if lib.boiledegg_get_runtime_info(h,c.byref(rt)) or rt.latency!=delay:raise ValueError('automation changed fixed delay')
        if np.any(out[:,:delay]) or not np.isfinite(out).all():raise ValueError('prefix or finite-output failure')
        return out,delay
    finally:lib.boiledegg_destroy(h)


def compare(a,b,delay_a,delay_b):
    if delay_a!=delay_b or a.shape!=b.shape:raise ValueError('delay/shape mismatch')
    if not np.isfinite(a).all() or not np.isfinite(b).all() or not np.array_equal(a,b):raise ValueError('output differs across block partitions')
    return hashlib.sha256(a.tobytes()).hexdigest()


def work(job):
    path,digest,library,quality,policy=job
    if core.sha(path)!=digest:raise ValueError('reference fingerprint changed')
    frames,rate=sf.read(path,dtype='float32',always_2d=True)
    if rate not in (44100,48000,88200,96000) or frames.shape[1] not in (1,2) or not np.isfinite(frames).all():raise ValueError('unsupported reference metadata')
    x=np.ascontiguousarray(frames.T);lib=core.library(library)
    a,da=render(lib,x,rate,quality,policy,32);b,db=render(lib,x,rate,quality,policy,257)
    fingerprint=compare(a,b,da,db)
    if core.sha(path)!=digest:raise ValueError('source changed during rendering')
    return dict(source=path.name,reference_sha256=digest,rate=rate,channels=len(x),source_frames=x.shape[1],
        quality=quality,policy=policy,delay_frames=da,output_frames=a.shape[1],compensated_frames=a.shape[1]-da,
        output_pcm_sha256=fingerprint,bit_identical=True,max_sample_difference=0.,
        peak=float(np.max(np.abs(a))),rms=float(np.sqrt(np.mean(a.astype(float)**2))))


def run(args):
    if args.output.exists() or not 1<=args.workers<=4 or args.expected_sources<1:raise ValueError('new output, positive source count and1..4 workers required')
    sources=sorted(args.refs.resolve(strict=True).glob('*.wav'))
    if len(sources)!=args.expected_sources:raise ValueError('source count does not match declared corpus')
    inputs={p:core.sha(p) for p in sources};library=args.library.resolve(strict=True);library_hash=core.sha(library)
    analysis={Path(__file__).resolve():core.sha(Path(__file__)),Path(core.__file__).resolve():core.sha(Path(core.__file__))}
    jobs=[(p,h,library,q,f) for p,h in inputs.items() for q in (0,1) for f in (0,1,2)]
    rows=[]
    with cf.ProcessPoolExecutor(args.workers) as pool:
        for i,row in enumerate(pool.map(work,jobs),1):
            rows.append(row)
            if i%12==0:print(f'{i}/{len(jobs)} paired automated renders',flush=True)
    keys={(r['source'],r['quality'],r['policy']) for r in rows}
    if len(rows)!=len(jobs) or keys!={(p.name,q,f) for p in sources for q in (0,1) for f in (0,1,2)}:raise ValueError('incomplete/duplicate grid')
    if core.sha(library)!=library_hash or any(core.sha(p)!=h for p,h in {**inputs,**analysis}.items()):raise ValueError('measured sources/library/analysis changed')
    args.output.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.dynamic-corpus-',dir=args.output.parent) as tmp:
        out=Path(tmp)/'report';out.mkdir()
        with (out/'comparisons.csv').open('w',newline='') as stream:
            writer=csv.DictWriter(stream,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
        report=dict(schema='boiled-egg.dynamic-corpus.v1',sources=len(sources),pairs=len(rows),renders=2*len(rows),
            passed=True,library_sha256=library_hash,analysis_sha256={p.name:h for p,h in analysis.items()},
            source_sha256={p.name:h for p,h in inputs.items()},comparisons_sha256=core.sha(out/'comparisons.csv'),
            shifts=list(SHIFTS),formant_ratios=list(FORMANTS),blocks=[32,257],
            notes='Same-kernel integration evidence. Complete input-clock event schedule. Exact fixed delay/no fitted alignment. '
            'Finite output and declared shape are checked, not a perceptual/native quality threshold. No audio or MOS redistributed.')
        (out/'summary.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n');out.rename(args.output)
    return report

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for k in ('refs','library','output'):p.add_argument('--'+k,type=Path,required=True)
    p.add_argument('--workers',type=int,default=2);p.add_argument('--expected-sources',type=int,default=20)
    r=run(p.parse_args());print(r['pairs'],'paired streams:',r['passed'])
