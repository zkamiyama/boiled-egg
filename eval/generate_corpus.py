#!/usr/bin/env python3
from pathlib import Path
import numpy as np
import soundfile as sf
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'data'/'synthetic'; OUT.mkdir(parents=True,exist_ok=True)
sr=48000; dur=5.0; n=int(sr*dur); t=np.arange(n)/sr
def write(name,x): sf.write(OUT/name,np.asarray(x,dtype=np.float32),sr,subtype='FLOAT')
write('sine_440.wav',0.4*np.sin(2*np.pi*440*t)); write('sine_10000.wav',0.4*np.sin(2*np.pi*10000*t)); write('sine_14000.wav',0.4*np.sin(2*np.pi*14000*t))
write('harmonic_stack.wav',sum((0.22/k)*np.sin(2*np.pi*110*k*t) for k in range(1,13)))
phase=2*np.pi*(80*t+(8000-80)/(2*dur)*t*t); write('chirp_80_8000.wav',0.35*np.sin(phase))
click=np.zeros(n); click[::sr//4]=0.8; write('click_train.wav',click)
rng=np.random.default_rng(1234); noise=np.zeros(n)
for start in range(0,n,sr//2):
 m=min(sr//20,n-start); env=np.exp(-np.arange(m)/(sr*0.008)); noise[start:start+m]=0.3*rng.standard_normal(m)*env
write('noise_bursts.wav',noise); x=np.zeros(n)
for start in range(0,n,sr//2):
 m=min(sr//4,n-start); tt=np.arange(m)/sr; x[start:start+m]+=0.45*np.sin(2*np.pi*(70-30*tt)*tt)*np.exp(-tt*18)+0.12*rng.standard_normal(m)*np.exp(-tt*45)
write('synthetic_drums.wav',x); left=0.3*np.sin(2*np.pi*330*t); right=0.3*np.sin(2*np.pi*330*t+0.7); write('stereo_phase.wav',np.stack([left,right],axis=1))
print(f'generated {len(list(OUT.glob("*.wav")))} files in {OUT}')
