#!/usr/bin/env python3
"""Deterministic pitch/formant regression for the streaming PV research backend."""
from __future__ import annotations
import argparse, json, math, subprocess, tempfile
from pathlib import Path
import numpy as np
import soundfile as sf
from scipy import signal

SR=48000; NFFT=2048; HOP=256

def resonator(f,bw):
    r=np.exp(-np.pi*bw/SR); th=2*np.pi*f/SR
    return np.array([1-r]),np.array([1,-2*r*np.cos(th),r*r])

def make_vowel(seconds=2.0):
    n=int(SR*seconds); x=np.zeros(n,np.float64); x[::round(SR/120)]=1
    for f,bw in ((700,90),(1220,110),(2600,150)): x=signal.lfilter(*resonator(f,bw),x)
    x=np.r_[x[0],np.diff(x)]; return (0.5*x/(np.max(np.abs(x))+1e-12)).astype(np.float32)

def make_harmonic(seconds=2.0):
    n=int(SR*seconds); t=np.arange(n)/SR
    x=sum(signal.sawtooth(2*np.pi*f*t) for f in (110,138.59,164.81,220))/4
    for f,bw in ((900,120),(1800,180),(3200,250)): x=signal.lfilter(*resonator(f,bw),x)
    return (0.4*x/(np.max(np.abs(x))+1e-12)).astype(np.float32)

def cep_env(x,q=40):
    f,_,z=signal.stft(x,fs=SR,window='hann',nperseg=NFFT,noverlap=NFFT-HOP,nfft=NFFT,boundary='zeros',padded=True)
    logm=np.log(np.maximum(np.abs(z),1e-7)); full=np.concatenate([logm,logm[-2:0:-1]],axis=0)
    c=np.fft.ifft(full,axis=0).real; keep=np.zeros_like(c); keep[:q+1]=c[:q+1]; keep[-q:]=c[-q:]
    env=np.fft.fft(keep,axis=0).real[:len(f)]; return f,env

def env_error(ref,test):
    f,a=cep_env(ref); _,b=cep_env(test); n=max(a.shape[1],b.shape[1]); u=np.linspace(0,1,n)
    def rt(x):
        old=np.linspace(0,1,x.shape[1]); return np.vstack([np.interp(u,old,row) for row in x])
    a=rt(a); b=rt(b); mask=(f>=150)&(f<=6000); a=a[mask]*20/np.log(10); b=b[mask]*20/np.log(10)
    b += np.median(a-b,axis=0,keepdims=True); return float(np.sqrt(np.mean((a-b)**2)))

def pitch_cents(x,expected):
    x=x[len(x)//4:3*len(x)//4]; w=np.hanning(len(x)); n=1<<int(np.ceil(np.log2(len(x)*8)))
    s=np.abs(np.fft.rfft(x*w,n)); f=np.fft.rfftfreq(n,1/SR); valid=np.flatnonzero((f>100)&(f<2000)); k=valid[np.argmax(s[valid])]
    a,b,c=s[k-1:k+2]; d=0.5*(a-c)/(a-2*b+c+1e-30); hz=(k+d)*SR/n
    return float(1200*np.log2(hz/expected)),float(hz)

def render(cli,src,dst,st,formant):
    cmd=[str(cli),str(src),str(dst),'--time','1','--pitch-semitones',str(st),'--mode','locked','--formant',formant]
    p=subprocess.run(cmd,capture_output=True,text=True)
    if p.returncode: raise RuntimeError(p.stderr or p.stdout)

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--cli',type=Path,required=True); ap.add_argument('--output',type=Path); args=ap.parse_args()
    out=args.output or Path(tempfile.mkdtemp(prefix='boiled-egg-formant-')); out.mkdir(parents=True,exist_ok=True)
    fixtures={'vowel':make_vowel(),'harmonic':make_harmonic()}; report={'pitch':{},'formant':{}}
    for name,x in fixtures.items(): sf.write(out/f'{name}.wav',x,SR,subtype='FLOAT')
    sine=(.3*np.sin(2*np.pi*440*np.arange(SR*2)/SR)).astype(np.float32); sf.write(out/'sine.wav',sine,SR,subtype='FLOAT')
    for st in (-12,-7,7,12):
        dst=out/f'sine_{st}.wav'; render(args.cli,out/'sine.wav',dst,st,'off'); y,_=sf.read(dst,dtype='float32')
        cents,hz=pitch_cents(y,440*2**(st/12)); report['pitch'][str(st)]={'hz':hz,'cents_error':cents,'frames':len(y)}
        if len(y)!=len(sine) or abs(cents)>0.1: raise SystemExit(f'pitch regression {st}: {cents:.3f} cents, {len(y)} frames')
    for name,ref in fixtures.items():
        rows={}
        modes=('off','harmonic','monophonic') if name=='vowel' else ('off','harmonic')
        for mode in modes:
            errors=[]
            for st in (-12,-7,7,12):
                dst=out/f'{name}_{st}_{mode}.wav'; render(args.cli,out/f'{name}.wav',dst,st,mode); y,_=sf.read(dst,dtype='float32')
                if len(y)!=len(ref): raise SystemExit(f'duration regression {name} {st} {mode}')
                errors.append(env_error(ref,y))
            rows[mode]={'errors_db':errors,'mean_db':float(np.mean(errors))}
        report['formant'][name]=rows
    v=report['formant']['vowel']; h=report['formant']['harmonic']
    if v['harmonic']['mean_db'] >= 0.90*v['off']['mean_db']: raise SystemExit('harmonic formant path did not improve vowel envelope enough')
    if v['monophonic']['mean_db'] >= 0.90*v['off']['mean_db']: raise SystemExit('monophonic formant path did not improve vowel envelope enough')
    if h['harmonic']['mean_db'] >= 0.96*h['off']['mean_db']: raise SystemExit('harmonic formant path did not improve polyphonic envelope enough')
    (out/'report.json').write_text(json.dumps(report,indent=2,sort_keys=True))
    print(json.dumps(report,indent=2,sort_keys=True))
if __name__=='__main__': main()
