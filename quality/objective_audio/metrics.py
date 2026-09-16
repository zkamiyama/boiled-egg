"""Deterministic artifact diagnostics, NOT a trained MOS or audibility model.

The spatial projector is invariant to one common complex gain per TF cell;
relative phase/gain changes remain visible. It cannot see common-mode coloration,
so waveform, level, timing and spectral metrics must remain separate.
"""
from __future__ import annotations
import numpy as np
from scipy import signal


def audio(x):
    x = np.asarray(x, dtype=np.float64)
    if x.ndim == 1: x = x[:, None]
    if x.ndim != 2 or not len(x) or not 1 <= x.shape[1] <= 8 or not np.isfinite(x).all():
        raise ValueError('nonempty finite channel matrix required')
    return x


def relation(x, gains):
    """Physical fixed-channel-ratio invariant; no fitted level or alignment."""
    x = audio(x); g = np.asarray(gains, dtype=np.float64)
    if g.shape != (x.shape[1],) or not np.isfinite(g).all() or g[0] != 1.:
        raise ValueError('one declared gain per channel; first must be1')
    denominator = np.sum(x[:,0]**2)
    if denominator <= 1e-20: raise ValueError('zero output is not a perfect score')
    error = x - x[:, :1]*g[None, :]
    relative = float(np.sqrt(np.sum(error**2)/denominator))
    return dict(relative_error=relative, residual_db=float(20*np.log10(max(relative,1e-15))))


def stft(x, rate, window=2048):
    x=audio(x)
    if rate not in (44100,48000,88200,96000) or window<16 or window & (window-1):
        raise ValueError('rate/window')
    size=window*(2 if rate>48000 else 1)
    if len(x)<size: x=np.pad(x,((0,size-len(x)),(0,0)))
    _,_,z=signal.stft(x,fs=rate,window='hann',nperseg=size,noverlap=3*size//4,
                      boundary='zeros',padded=True,axis=0)
    return np.moveaxis(z,1,-1) # frequency,time,channel


def projector_distance(reference, candidate, floor_db=-60.):
    """Channel-vector angular error, weighted by reference energy.

Compute the orthogonal residual directly instead of subtracting nearly equal
squared norms. This remains accurate around float32 noise floors.
    """
    a=np.asarray(reference,dtype=np.complex128);b=np.asarray(candidate,dtype=np.complex128)
    if a.shape!=b.shape or a.ndim<2 or not np.isfinite(a).all() or not np.isfinite(b).all():
        raise ValueError('matched finite complex channel vectors required')
    aa=np.sum(abs(a)**2,axis=-1);bb=np.sum(abs(b)**2,axis=-1)
    if aa.max(initial=0)<=1e-24 or bb.max(initial=0)<=1e-24:
        raise ValueError('zero energy cannot qualify')
    active=aa>=aa.max()*10**(floor_db/10)
    dot=np.sum(a.conj()*b,axis=-1)
    scale=np.divide(dot,aa,out=np.zeros_like(dot),where=aa>0)
    residual=np.sum(abs(b-scale[...,None]*a)**2,axis=-1)
    err=np.divide(residual,bb,out=np.ones_like(bb),where=bb>aa.max()*1e-24)
    err=np.clip(err,0.,1.)
    return dict(spatial_error=float(np.sqrt(np.sum(aa[active]*err[active])/np.sum(aa[active]))),
                active_cells=int(active.sum()))


def stereo_spectrum(x,rate,gain,window=2048):
    z=stft(x,rate,window)
    if z.shape[-1]!=2 or not np.isfinite(gain): raise ValueError('stereo/gain')
    expected=np.stack([z[...,0],z[...,0]*gain],axis=-1)
    result=projector_distance(expected,z)
    # Independent relative-channel phase and level. Silent channels use relation().
    if gain:
        power=abs(z[...,0])**2;active=power>=power.max()*1e-6
        ratio=np.divide(z[...,1],z[...,0],out=np.zeros_like(z[...,0]),where=abs(z[...,0])>0)
        ild=20*np.log10(np.maximum(abs(ratio[active]/gain),1e-15))
        ipd=np.angle(ratio[active]/gain)
        w=power[active]/power[active].sum()
        result.update(ild_rms_db=float(np.sqrt(np.sum(w*ild*ild))),
                      ipd_rms_radians=float(np.sqrt(np.sum(w*ipd*ipd))))
    return result


def envelope_rmse(reference,candidate,rate,window_ms=5.):
    """Same-target temporal envelope error; no best-lag or gain fitting."""
    a,b=audio(reference),audio(candidate)
    if a.shape!=b.shape:raise ValueError('exact target duration required')
    n=max(1,round(rate*window_ms/1000));usable=len(a)//n*n
    if not usable:raise ValueError('too short')
    aa=np.mean(a[:usable].reshape(-1,n,a.shape[1])**2,axis=(1,2))
    bb=np.mean(b[:usable].reshape(-1,n,b.shape[1])**2,axis=(1,2))
    if max(aa.max(),bb.max())<1e-20:raise ValueError('zero reference/target')
    floor=aa.max()*1e-10;active=aa>aa.max()*1e-6
    return float(np.sqrt(np.mean((10*np.log10(np.maximum(bb[active],floor)/aa[active]))**2)))
