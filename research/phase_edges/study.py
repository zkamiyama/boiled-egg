#!/usr/bin/env python3
"""Matched-input edge transport and linked consistency-projection study.

A manifest-bound per-case journal is resumable. Missing/duplicate/mutated data
cannot publish final results. Descriptor values are not MOS or native scores.
"""
import argparse, concurrent.futures as cf, csv, hashlib, importlib.util, json, math, os, time, tempfile
from pathlib import Path
import numpy as np
import soundfile as sf
from scipy import signal
from scipy.interpolate import interp1d
import experiment as e
import consistency

_spec=importlib.util.spec_from_file_location('phase_legacy_metrics',Path(__file__).parents[1]/'phase_gradient/study.py')
old=importlib.util.module_from_spec(_spec);_spec.loader.exec_module(old)
PILOT=('Ardour_2','Female_4','Male_6','Rock_4','Triangle_02')
SHIFTS=(-12,-7,-3,0,3,7,12)
SEEDS=tuple(range(2609150,2609158))

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def pcm(x):return hashlib.sha256(np.ascontiguousarray(x,dtype='<f8').tobytes()).hexdigest()

def local_spectral(x,y,rate,ratio):
    result={}
    for n in (512,2048,8192):
        n*=2 if rate==96000 else 1
        def power(x):
            _,t,z=signal.stft(x,fs=rate,window='hann',nperseg=n,noverlap=3*n//4,boundary='zeros',padded=True,axis=0)
            return t,np.mean(abs(z)**2,axis=1)
        tx,a=power(x);ty,b=power(y)
        a=interp1d(tx,a,axis=1,bounds_error=False,fill_value=0)(ty/ratio)
        # A single global energy factor per representation, not per-frame EQ.
        a/=max(a.sum(),1e-30);b/=max(b.sum(),1e-30);mask=a>a.max()*1e-4
        result[f'local_spectral_{n}_db']=float(np.sqrt(np.mean((10*np.log10(np.maximum(a[mask],1e-12))-10*np.log10(np.maximum(b[mask],1e-12)))**2)))
    return result

def texture(x,rate,ratio):
    x=x[rate//4:-rate//4];n=round(.04*rate)
    f,p=signal.welch(x,rate,nperseg=n,noverlap=n//2,axis=0);p=p.mean(axis=1)
    selected=p[(f>=2200*ratio)&(f<=6200*ratio)];selected/=max(selected.mean(),1e-30)
    step=round(.01*rate);rms=np.sqrt(np.mean(x[:len(x)//step*step]**2,axis=1).reshape(-1,step).mean(axis=1))
    return dict(flatness=float(np.exp(np.log(np.maximum(selected,1e-12)).mean())),rms_cv=float(rms.std()/max(rms.mean(),1e-30)),
                lr_correlation=float(np.corrcoef(x.T)[0,1]) if x.shape[1]==2 else 1.)

def fixture(name,rate,pitch=1.,seed=0):
    if name=='bank':return (*old.bank(rate,pitch),)
    if name=='attack':return old.attack(rate,pitch),None
    if name=='newbank':
        rng=np.random.default_rng(seed);freq=(73+np.cumsum(rng.uniform(90,360,14)))*pitch
        amps=10**(rng.uniform(-24,0,14)/20);phases=rng.uniform(-np.pi,np.pi,14);t=np.arange(2*rate)/rate
        x=sum(a*np.sin(2*np.pi*f*t+p) for a,f,p in zip(amps,freq,phases));x*=.1/np.sqrt(np.mean(x*x))
        return x,freq
    def noise(seed):
        z=np.fft.rfft(np.random.default_rng(seed).standard_normal(2*rate));f=np.fft.rfftfreq(2*rate,1/rate)
        z[(f<1800*pitch)|(f>7000*pitch)]=0;y=np.fft.irfft(z,n=2*rate);return .1*y/np.sqrt(np.mean(y*y))
    x=noise(550);return (np.c_[x,.7*x+np.sqrt(1-.7**2)*noise(551)] if name=='stereo' else x),None

def worker(job):
    suite,name,rate,ratio,shift,seed,source,modes,heap,edge=job
    if suite=='corpus':
        x,sr=sf.read(source,dtype='float64',always_2d=True)
        if sr!=rate:raise ValueError('source rate changed')
        oracle=freq=None
    else:
        x,_=fixture(name,rate,seed=seed);oracle,freq=fixture(name,rate,ratio,seed)
        if x.ndim==1:x=x[:,None]
    if not np.isfinite(x).all() or np.sum(x*x)<=1e-24:raise ValueError('nonfinite/silent evaluation input')
    digest=pcm(x);rows=[]
    for mode in modes:
        start=time.perf_counter()
        y,stats=e.render(x,rate,time=ratio if suite=='corpus' else 1.,pitch=ratio if suite!='corpus' else 1.,mode=mode,kernel_path=heap,edge_path=edge)
        elapsed=time.perf_counter()-start
        expected=int(np.floor(len(x)*(ratio if suite=='corpus' else 1)+.5))
        if y.shape!=(expected,x.shape[1]) or not np.isfinite(y).all() or np.sum(y*y)<=1e-24:raise ValueError('invalid evaluation output')
        row=dict(suite=suite,source=Path(source).stem if source else name,seed=seed,rate=rate,ratio=ratio,shift=shift,mode=mode,
            cohort=('pilot' if name in PILOT else 'within_iteration_confirmation') if suite=='corpus' else 'analytic',
            frames=len(y),channels=y.shape[1],input_pcm_sha256=digest,output_pcm_sha256=pcm(y),peak=float(abs(y).max()),
            rms_gain_db=float(10*np.log10(np.mean(y*y)/np.mean(x*x))),elapsed_seconds=elapsed,**stats)
        if suite=='corpus':row.update(old.natural_metrics(x,y,rate,ratio),**local_spectral(x,y,rate,ratio))
        elif name in ('bank','newbank'):row.update(old.partials(y[:,0],oracle,freq,rate))
        elif name=='attack':row.update(old.attack_metrics(y[:,0],rate))
        else:
            control=oracle[:,None] if oracle.ndim==1 else oracle
            target=texture(control,rate,ratio);observed=texture(y,rate,ratio)
            row.update(observed,**{'oracle_'+k:v for k,v in target.items()})
        if suite!='corpus' and shift==0:row['unity_max_abs_error']=float(abs(y-x).max())
        if not all(np.isfinite(v) for v in row.values() if isinstance(v,(float,np.floating))):raise ValueError('nonfinite measurement')
        rows.append(row)
    if pcm(x)!=digest:raise ValueError('evaluator mutated input')
    return rows

def validate(rows,keys):
    ids=[(r['source'],r['rate'],r['ratio'],r['seed'],r['mode']) for r in rows]
    if len(ids)!=len(set(ids)) or set(ids)!=set(map(tuple,keys)):raise ValueError('duplicate/missing grid')

def run(a):
    if a.output.exists() or not 1<=a.workers<=4:raise ValueError('new output and workers1..4 required')
    heap=a.kernel.resolve(strict=True);edge=a.edge.resolve(strict=True)
    hashes={str(p):sha(p) for p in (heap,edge,Path(__file__),Path(e.__file__),Path(consistency.__file__),Path(old.__file__))}
    sources={};jobs=[]
    if a.suite=='corpus':
        if not a.refs:raise ValueError('reference folder required')
        files=sorted(a.refs.glob('*.wav'))
        if len(files)!=20:raise ValueError('the supplied20 references are required; no substitution')
        for p in files:
            sources[str(p.resolve())]=sha(p)
            for ratio in (.5,1.5,2.):jobs.append((a.suite,p.stem,sf.info(p).samplerate,ratio,0,0,str(p.resolve()),e.MODES,str(heap),str(edge)))
    else:
        names=('bank','attack','noise','stereo') if a.suite=='synthetic' else ('newbank',)
        for name in names:
            for seed in (SEEDS if a.suite=='banks' else (0,)):
                for rate in (48000,96000):
                    for shift in (SHIFTS if a.suite=='synthetic' else tuple(s for s in SHIFTS if s)):
                        modes=e.MODES if a.suite=='synthetic' else ('locked','heap','edge_both','project4')
                        jobs.append((a.suite,name,rate,2**(shift/12),shift,seed,None,modes,str(heap),str(edge)))
    keys=[(j[1],j[2],j[3],j[5],m) for j in jobs for m in j[7]]
    manifest=dict(schema=1,suite=a.suite,hashes=hashes,sources=sources,keys=keys)
    serialized=json.dumps(manifest,sort_keys=True,separators=(',',':'))
    identity=hashlib.sha256(serialized.encode()).hexdigest();cache=a.cache.resolve();cache.mkdir(parents=True,exist_ok=True)
    path=cache/'manifest.json'
    if path.exists():
        if path.read_text()!=serialized:raise ValueError('cache configuration changed')
    elif any(cache.iterdir()):raise ValueError('unbound nonempty cache')
    else:path.write_text(serialized)
    rows=[];pending=[]
    for i,j in enumerate(jobs):
        path=cache/f'{i:04d}.json'
        if path.exists():
            blob=json.loads(path.read_text());payload=json.dumps(blob['rows'],sort_keys=True,separators=(',',':'))
            if blob['identity']!=identity or blob['index']!=i or hashlib.sha256(payload.encode()).hexdigest()!=blob['sha256']:raise ValueError('cache corruption')
            rows+=blob['rows']
        else:pending.append((i,j))
    with cf.ProcessPoolExecutor(a.workers) as pool:
        for done,((i,j),result) in enumerate(zip(pending,pool.map(worker,[j for _,j in pending])),1):
            payload=json.dumps(result,sort_keys=True,separators=(',',':'))
            temp=cache/f'.{i}.tmp';temp.write_text(json.dumps(dict(identity=identity,index=i,rows=result,sha256=hashlib.sha256(payload.encode()).hexdigest()),allow_nan=False))
            temp.replace(cache/f'{i:04d}.json');rows+=result
            if done%6==0:print(a.suite,done,'/',len(pending),flush=True)
    validate(rows,keys)
    if any(sha(p)!=digest for p,digest in {**hashes,**sources}.items()):raise ValueError('code or inputs changed')
    rows.sort(key=lambda r:(r['source'],r['seed'],r['rate'],r['ratio'],r['mode']))
    a.output.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".phase-report-",dir=a.output.parent) as tmp:
        dest=Path(tmp)/"report";dest.mkdir()
        fields=sorted(set().union(*(r.keys() for r in rows)))
        with (dest/'results.csv').open('w',newline='') as s:
            writer=csv.DictWriter(s,fieldnames=fields);writer.writeheader();writer.writerows(rows)
        report=dict(renders=len(rows),manifest=manifest,results_sha256=sha(dest/'results.csv'),listening_status='not_listened',native_baseline=False,
            notes='All predetermined variants retained; no automatic winner. Project4 new-bank subset fixed before confirmation. '
            '5ms/global descriptors inherited unchanged; local STFT descriptors are additional and not interchangeable. '
            'Elapsed wall time includes Python allocation and concurrent jobs, not audio-callback qualification.')
        (dest/'summary.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n');dest.rename(a.output);return report

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for k in ('kernel','edge','output','cache'):parser.add_argument('--'+k,type=Path,required=True)
    parser.add_argument('--suite',choices=('synthetic','corpus','banks'),required=True)
    parser.add_argument('--refs',type=Path);parser.add_argument('--workers',type=int,default=2)
    print(run(parser.parse_args())['renders'],'outputs complete')
