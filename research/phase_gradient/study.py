#!/usr/bin/env python3
"""Matched-window static study of locked, trapezoidal and heap PV.

The natural-source metrics are diagnostics, NOT errors against an ideal stretch.
No zplane run, native baseline, copied GPL source, or live-backend promotion.
"""
import argparse, concurrent.futures as cf, csv, hashlib, json, math, sys
from pathlib import Path
import numpy as np
import soundfile as sf
from scipy import signal
import experiment as e
MODES=('locked','trapezoid','heap')

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def bank(rate,pitch=1.):
    f=np.array([110.,223.4,378.9,531.2,829.7,1193.2,2300.3,4113.1])*pitch
    a=1/np.sqrt(np.arange(1,len(f)+1));t=np.arange(2*rate)/rate
    x=sum(v*np.sin(2*np.pi*freq*t+i*.7) for i,(freq,v) in enumerate(zip(f,a)))
    return x*.1/np.sqrt(np.mean(x*x)),f

def attack(rate,pitch=1.):
    t=np.arange(2*rate)/rate;x=sum(.1*np.sin(2*np.pi*freq*pitch*t) for freq in (2113,3299,5113,7331))
    g=np.zeros_like(x)
    for start in (.3,.7,1.1,1.5):
        n=round(.002*rate);g[round(start*rate):round(start*rate)+n]=np.sin(np.pi*np.arange(n)/n)**2
    return x*g

def partials(x,oracle,f,rate):
    def spectrum(x):
        x=x[rate//4:-rate//4];N=1<<int(np.ceil(np.log2(len(x)*4)))
        return np.fft.rfftfreq(N,1/rate),np.abs(np.fft.rfft(x*signal.windows.hann(len(x),sym=False),N))**2
    freq,p=spectrum(x);_,q=spectrum(oracle);a=[];b=[];used=np.zeros(len(freq),bool)
    for target in f:
        mask=abs(freq-target)<4;used|=mask;a.append(p[mask].sum());b.append(q[mask].sum())
    a=np.array(a);b=np.array(b);a/=max(a.sum(),1e-30);b/=max(b.sum(),1e-30)
    return dict(partial_error_db=float(np.sqrt(np.mean((10*np.log10(np.maximum(a,1e-12)/np.maximum(b,1e-12)))**2))),
                off_partial_energy_db=float(10*np.log10(max(p[~used].sum()/max(p.sum(),1e-30),1e-12))))

def attack_metrics(x,rate):
    widths=[];centers=[]
    for start in (.3,.7,1.1,1.5):
        lo=round((start-.1)*rate);hi=round((start+.102)*rate);p=x[lo:hi]**2;t=np.arange(lo,hi)/rate
        total=p.sum()
        if total<1e-24:raise ValueError('silent attack')
        q=np.interp([.05,.95],np.cumsum(p)/total,t);widths.append(1000*(q[1]-q[0]));centers.append(1000*((p*t).sum()/total-start-.001))
    return dict(attack_width_ms=float(np.mean(widths)),centroid_ms=float(np.mean(centers)))

def natural_metrics(x,y,rate,time):
    def bins(x):
        step=round(.005*rate);p=np.mean(x*x,axis=1);p=np.pad(p,(0,(-len(p))%step));return p.reshape(-1,step).mean(axis=1)
    a=bins(x);b=bins(y);mapped=np.interp((np.arange(len(b))+.5)/time-.5,np.arange(len(a)),a)
    mask=mapped>mapped.max()*1e-4
    aa=mapped/max(mapped.sum(),1e-24);bb=b/max(b.sum(),1e-24)
    envelope=float(np.sqrt(np.mean((10*np.log10(np.maximum(aa[mask],1e-12))-10*np.log10(np.maximum(bb[mask],1e-12)))**2)))
    flux_a=np.maximum(np.diff(np.sqrt(aa)),0);flux_b=np.maximum(np.diff(np.sqrt(bb)),0)
    onset=float(np.corrcoef(flux_a,flux_b)[0,1]) if flux_a.std()>1e-15 and flux_b.std()>1e-15 else 0.
    def psd(x):
        _,p=signal.welch(x,fs=rate,nperseg=2048,noverlap=1024,axis=0);p=p.mean(axis=1);return p/max(p.sum(),1e-24)
    p,q=psd(x),psd(y);mask=p>p.max()*1e-4
    distance=float(np.sqrt(np.mean((10*np.log10(np.maximum(p[mask],1e-12))-10*np.log10(np.maximum(q[mask],1e-12)))**2)))
    return dict(rms_shape_db=envelope,onset_corr=onset,global_psd_shape_db=distance)

def work(job):
    name,rate,ratio,operation,path,kernel=job
    if operation=='pitch':
        if name=='partials':x,_=bank(rate);oracle,frequencies=bank(rate,ratio)
        else:x=attack(rate);oracle=attack(rate,ratio)
        x=x[:,None]
    else:x,sr=sf.read(path,dtype='float64',always_2d=True)
    source_hash=hashlib.sha256(x.astype('<f8').tobytes()).hexdigest();rows=[]
    for mode in MODES:
        y,stats=e.render(x,rate,time=ratio if operation=='time' else 1.,pitch=ratio if operation=='pitch' else 1.,mode=mode,kernel_path=kernel)
        if len(y)!=math.floor(len(x)*(ratio if operation=='time' else 1)+.5):raise ValueError('duration')
        metrics=natural_metrics(x,y,rate,ratio) if operation=='time' else partials(y[:,0],oracle,frequencies,rate) if name=='partials' else attack_metrics(y[:,0],rate)
        rows.append(dict(source=name,rate=rate,ratio=ratio,operation=operation,mode=mode,
            input_pcm_sha256=source_hash,output_pcm_sha256=hashlib.sha256(y.astype('<f8').tobytes()).hexdigest(),
            frames=len(y),peak=float(np.max(np.abs(y))),**stats,**metrics))
    return rows

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--kernel',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--refs',type=Path);p.add_argument('--workers',type=int,default=2);a=p.parse_args()
    if a.output.exists() or not 1<=a.workers<=4:raise ValueError('new output / workers1..4 required')
    kernel=a.kernel.resolve(strict=True);digest=sha(kernel);sources={}
    jobs=[(name,r,2**(st/12),'pitch',None,kernel) for name in ('partials','attacks') for r in (48000,96000) for st in (-12,-7,-3,3,7,12)]
    if a.refs:
        files=sorted(a.refs.glob('*.wav'))
        if not files:raise ValueError('empty reference folder')
        for f in files:
            sources[str(f)]=sha(f)
            for ratio in (.5,1.5,2.):jobs.append((f.stem,sf.info(f).samplerate,ratio,'time',f,kernel))
    rows=[]
    with cf.ProcessPoolExecutor(a.workers) as pool:
        for i,part in enumerate(pool.map(work,jobs),1):
            rows+=part
            if i%12==0:print(i,'/',len(jobs),flush=True)
    if len(rows)!=len(jobs)*len(MODES) or sha(kernel)!=digest:raise ValueError('incomplete/modified study')
    if any(sha(p)!=d for p,d in sources.items()):raise ValueError('sources changed')
    a.output.mkdir(parents=True);fields=sorted(set().union(*(r.keys() for r in rows)))
    with (a.output/'results.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)
    groups={}
    for r in rows:
        group=f"{r['operation']}/{r['source'] if r['operation']=='pitch' else 'corpus'}/{r['rate']}/{r['mode']}"
        groups.setdefault(group,[]).append(r)
    means={g:{k:float(np.mean([r[k] for r in rs])) for k in ('partial_error_db','attack_width_ms','rms_shape_db','onset_corr','global_psd_shape_db') if k in rs[0]} for g,rs in groups.items()}
    result=dict(renders=len(rows),kernel_sha256=digest,source_files=sources,implementation_sha256=sha(e.__file__),script_sha256=sha(__file__),
                results_sha256=sha(a.output/'results.csv'),means=means,
                claim='Offline matched-window phase experiment. No native zplane/MOS or production qualification. Centered gradients need one future frame.')
    (a.output/'summary.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n');print(len(rows),'renders completed')
if __name__=='__main__':main()
