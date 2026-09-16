#!/usr/bin/env python3
"""Matched raw-output stereo regression. No MOS, listening or gain/lag fitting.

Outputs are measured then discarded. Inputs, configurations, exact metadata and
whole-WAV fingerprints are retained. A process or metadata failure aborts rather
than silently reducing the declared grid.
"""
from __future__ import annotations
import argparse,concurrent.futures as cf,csv,hashlib,itertools,json,subprocess,tempfile
from pathlib import Path
import numpy as np
import soundfile as sf
import metrics as m
OPS=((1.,0.),(.9,0.),(1.1,0.),(1.,-7.),(1.,7.))


def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def fixture(rate,seed,gain,seconds):
    n=round(rate*seconds);t=np.arange(n)/rate
    rng=np.random.default_rng(seed)
    freqs=(173.,1613.) if seed==260916 else tuple(rng.uniform(65,9000,5))
    x=sum(.08/(i+1)*np.sin(2*np.pi*f*t+i*.51) for i,f in enumerate(freqs))+.008*rng.standard_normal(n)
    return np.asarray(np.c_[x,gain*x],dtype='float32')


def render(exe,src,dst,rate,frames,channels,time,pitch,quality,formant,block):
    cmd=[str(exe),str(src),str(dst),'--backend','pv','--allow-experimental','--quality',quality,
         '--formant',formant,'--time',str(time),'--pitch-semitones',str(pitch),'--block',str(block)]
    proc=subprocess.run(cmd,capture_output=True,text=True,timeout=120)
    if proc.returncode:raise RuntimeError(f'CLI returned{proc.returncode}: {proc.stderr}')
    y,sr=sf.read(dst,dtype='float64',always_2d=True);info=sf.info(dst)
    expected=int(np.floor(frames*float(np.float32(time))+.5))
    if sr!=rate or info.subtype!='FLOAT' or y.shape!=(expected,channels) or not np.isfinite(y).all():
        raise ValueError('invalid raw output metadata')
    return y,sha(dst)


def job(task):
    rate,quality,formant,time,pitch,seed,gain,seconds,executables,mono_source=task
    x=(sf.read(mono_source,dtype='float32',always_2d=True)[0] if mono_source else fixture(rate,seed,gain,seconds))
    if mono_source and x.shape[1]!=1:raise ValueError('mono compatibility source required')
    rows=[]
    with tempfile.TemporaryDirectory(prefix='objective-audio-') as tmp:
        src=Path(tmp)/'in.wav';sf.write(src,x,rate,subtype='FLOAT');digest=sha(src)
        for name,exe in executables:
            dst=Path(tmp)/(name+'.wav');y,h=render(exe,src,dst,rate,len(x),x.shape[1],time,pitch,quality,formant,32)
            row=dict(rate=rate,quality=quality,formant=formant,time=time,pitch=pitch,seed=seed,gain=gain,
                     seconds=seconds,source=Path(mono_source).name if mono_source else 'generated',variant=name,
                     input_sha256=digest,output_sha256=h,frames=len(y),channels=y.shape[1],peak=float(abs(y).max()))
            if not mono_source:
                row.update(m.relation(y,[1.,gain]));row.update(m.stereo_spectrum(y,rate,gain))
                row['passed']=row['relative_error']<=1e-5
                for a,b,label in [(0,min(len(y),rate//10),'startup'),(len(y)//4,3*len(y)//4,'middle'),(max(0,len(y)-rate//10),len(y),'tail')]:
                    row[label+'_relative_error']=m.relation(y[a:b],[1.,gain])['relative_error']
            rows.append(row)
        if sha(src)!=digest:raise ValueError('source mutation')
    return rows


def run(a):
    if a.output.exists() or not 1<=a.workers<=4:raise ValueError('new output and workers1..4')
    executables=[('baseline',a.baseline.resolve(strict=True)),('candidate',a.candidate.resolve(strict=True))]
    if a.wrapped:executables.insert(1,('wrap_only',a.wrapped.resolve(strict=True)))
    hashes={str(p):sha(p) for _,p in executables}
    # These CLIs use same-directory shared libraries in the documented builds.
    for _,p in executables:
        lib=p.parent/'libboiled_egg.so'
        if not lib.exists():raise ValueError('expected same-directory shared SDK')
        hashes[str(lib)]=sha(lib)
    for p in (Path(__file__),Path(m.__file__)):hashes[str(p.resolve())]=sha(p)
    tasks=[];sources={}
    rates=(48000,96000)
    if a.suite=='replication':
        seeds=[(260916,-.375,2.)]
    elif a.suite=='confirmation':
        seeds=[(26091601,-.375,.25),(26091602,.25,2.),(26091603,-2.,2.),(26091604,0.,.25)]
    else:
        files=sorted(a.refs.glob('*.wav')) if a.refs else []
        if len(files)!=20:raise ValueError('exactly20 supplied mono references required')
        for p in files:
            sources[str(p.resolve())]=sha(p);info=sf.info(p)
            if info.channels!=1:raise ValueError('mono corpus expected')
            for q,f in itertools.product(('general','transient'),('off','harmonic','monophonic')):
                tasks.append((info.samplerate,q,f,1.,7.,0,0.,info.frames/info.samplerate,executables,str(p)))
        seeds=[]
    for rate,q,f,op,seed in itertools.product(rates,('general','transient'),('off','harmonic','monophonic'),OPS,seeds):
        tasks.append((rate,q,f,*op,*seed,executables,None))
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.mkdir();plan=dict(suite=a.suite,binaries_analysis=hashes,sources=sources,expected_conditions=len(tasks),
                              variants=[n for n,p in executables],relative_threshold=1e-5,metrics_version=1,
                              no_gain_or_lag_fit=True,not_mos=True)
    (a.output/'plan.json').write_text(json.dumps(plan,indent=2)+'\n')
    rows=[]
    with cf.ProcessPoolExecutor(a.workers) as pool:
        for i,part in enumerate(pool.map(job,tasks),1):
            rows+=part
            if i%20==0:print(a.suite,i,'/',len(tasks),flush=True)
    keys=('rate','quality','formant','time','pitch','seed','gain','seconds','source','variant')
    actual=[tuple(r[k] for k in keys) for r in rows]
    if len(rows)!=len(tasks)*len(executables) or len(set(actual))!=len(rows):raise ValueError('incomplete/duplicate grid')
    for p,h in {**hashes,**sources}.items():
        if sha(p)!=h:raise ValueError('input/engine/analysis changed')
    with (a.output/'measurements.csv').open('w',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=sorted(set().union(*(r.keys() for r in rows))));writer.writeheader();writer.writerows(rows)
    result=dict(plan=plan,outputs=len(rows),summaries=[],measurements_sha256=sha(a.output/'measurements.csv'))
    for name,_ in executables:
        group=[r for r in rows if r['variant']==name]
        summary=dict(variant=name,count=len(group))
        if a.suite!='mono':summary.update(passed=sum(r['passed'] for r in group),worst_relative=max(r['relative_error'] for r in group),
                                         worst_spatial=max(r['spatial_error'] for r in group),median_relative=float(np.median([r['relative_error'] for r in group])))
        result['summaries'].append(summary)
    if a.suite=='mono':
        before={tuple(r[k] for k in keys[:-1]):r['output_sha256'] for r in rows if r['variant']=='baseline'}
        result['byte_identical']=sum(r['output_sha256']==before[tuple(r[k] for k in keys[:-1])] for r in rows if r['variant']=='candidate')
    (a.output/'summary.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n');print(json.dumps(result['summaries']),flush=True)
    return result
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('baseline','candidate','output'):p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--wrapped',type=Path);p.add_argument('--refs',type=Path)
    p.add_argument('--suite',choices=('replication','confirmation','mono'),required=True);p.add_argument('--workers',type=int,default=2)
    r=run(p.parse_args())
    if r['plan']['suite']=='mono':raise SystemExit(r['byte_identical']!=r['plan']['expected_conditions'])
    raise SystemExit(next(s for s in r['summaries'] if s['variant']=='candidate')['passed']!=r['plan']['expected_conditions'])
