"""Reuse unchanged project descriptors; add explicit analytical temporal errors.

The energy width itself is NOT a lower-is-better error. Compare to the declared
2-ms gated-carrier oracle, including centroid and outside-gate energy. No fitted
alignment or output gain is used. Natural descriptors remain source-relative.
"""
import importlib.util
from pathlib import Path
import sys
import numpy as np
from scipy import signal

_dir=Path(__file__).parents[1]/'phase_edges'
sys.path.insert(0,str(_dir))
try:
    _spec=importlib.util.spec_from_file_location('hpss_inherited_metrics',_dir/'study.py')
    inherited=importlib.util.module_from_spec(_spec);_spec.loader.exec_module(inherited)
finally:
    sys.path.pop(0)
natural_metrics=inherited.old.natural_metrics
local_spectral=inherited.local_spectral
partials=inherited.old.partials

STARTS=(.3,.7,1.1,1.5)

def temporal_errors(x,oracle,rate,starts=STARTS,duration=.002):
    x=np.asarray(x).reshape(-1);oracle=np.asarray(oracle).reshape(-1)
    if x.shape!=oracle.shape or not np.isfinite(x).all() or not np.isfinite(oracle).all():raise ValueError('analytical time shape')
    widths=[];ideal_widths=[];centers=[];outside=[];energy=[]
    for start in starts:
        lo=max(0,round((start-.1)*rate));hi=min(len(x),round((start+duration+.1)*rate))
        t=np.arange(lo,hi)/rate;a=x[lo:hi]**2;b=oracle[lo:hi]**2
        if a.sum()<1e-24 or b.sum()<1e-24:raise ValueError('silent event diagnostic')
        def shape(p):
            q=np.interp([.05,.95],np.cumsum(p)/p.sum(),t)
            return 1000*(q[1]-q[0]),1000*np.sum(p*t)/p.sum()
        wa,ca=shape(a);wb,cb=shape(b);widths.append(wa);ideal_widths.append(wb);centers.append(abs(ca-cb))
        outside.append(float(a[(t<start)|(t>=start+duration)].sum()/a.sum()))
        energy.append(float(10*np.log10(a.sum()/b.sum())))
    return dict(attack_width_ms=float(np.mean(widths)),oracle_width_ms=float(np.mean(ideal_widths)),
        width_absolute_error_ms=float(np.mean(np.abs(np.array(widths)-ideal_widths))),
        centroid_absolute_error_ms=float(np.mean(centers)),outside_gate_energy_fraction=float(np.mean(outside)),
        event_energy_gain_db=float(np.mean(energy)))

def fixture(name,rate,pitch=1.,seed=0):
    if name in ('bank','attack','noise','stereo','newbank'):return inherited.fixture(name,rate,pitch,seed)
    t=np.arange(2*rate)/rate
    if name=='low55':return .1*np.sin(2*np.pi*55*pitch*t),np.array([55*pitch])
    if name=='mixture':
        freqs=np.array([110.,223.4,378.9,829.7])*pitch
        h=sum(.04*np.sin(2*np.pi*f*t+i*.7) for i,f in enumerate(freqs))
        return h+inherited.old.attack(rate,pitch),freqs
    raise ValueError('fixture')

def synthetic_metrics(name,y,oracle,freq,rate,pitch):
    if name in ('bank','newbank'):return partials(y[:,0],oracle,freq,rate)
    if name=='attack':return temporal_errors(y[:,0],oracle,rate)
    if name=='mixture':
        filter_=signal.butter(6,1800*pitch,fs=rate,btype='highpass',output='sos')
        a=signal.sosfiltfilt(filter_,y[:,0]);b=signal.sosfiltfilt(filter_,oracle)
        result=temporal_errors(a,b,rate)
        result.update(local_spectral(oracle[:,None],y,rate,1.))
        return result
    if name=='low55':
        x=y[rate//3:-rate//3,0];n=1<<int(np.ceil(np.log2(len(x)*8)))
        spec=np.abs(np.fft.rfft(x*signal.windows.hann(len(x),sym=False),n));index=int(np.argmax(spec))
        s=np.log(np.maximum(spec[index-1:index+2],1e-300))
        offset=.5*(s[0]-s[2])/(s[0]-2*s[1]+s[2]);frequency=(index+offset)*rate/n
        amplitude=abs(signal.hilbert(x));amp=amplitude[len(amplitude)//8:-len(amplitude)//8]
        lo,hi=np.quantile(amp,[.025,.975])
        return dict(pitch_error_cents=float(1200*np.log2(frequency/(55*pitch))),ripple95_db=float(20*np.log10(max(hi,1e-30)/max(lo,1e-30))))
    actual=inherited.texture(y,rate,pitch);ideal=inherited.texture(oracle if oracle.ndim==2 else oracle[:,None],rate,pitch)
    return {**actual,**{f'{k}_absolute_error':abs(actual[k]-ideal[k]) for k in ('flatness','rms_cv','lr_correlation')}}
