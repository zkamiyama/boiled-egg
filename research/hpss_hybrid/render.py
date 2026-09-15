"""Explicit offline linked-HPSS hybrid; no product/real-time/formant claim.

Concept: Driedger/Mueller/Ewert SPL2014 long harmonic PV / short percussive OLA.
Project adaptations and fixed ablations are in PROTOCOL.md. Own implementation;
only existing project phase kernels are reused, not external reference code.
"""
from __future__ import annotations
import ctypes as c
import importlib.util
from pathlib import Path
import numpy as np
from scipy import ndimage, signal

_path=Path(__file__).parents[1]/'phase_gradient/experiment.py'
_spec=importlib.util.spec_from_file_location('hpss_inherited_phase',_path)
phase=importlib.util.module_from_spec(_spec);_spec.loader.exec_module(phase)
MODES=('locked','heap','hps_locked_ola','hps_heap_ola','hps_locked_pv','hps_heap_pv')

class Kernels:
    def __init__(self,path):
        self.lib=c.CDLL(str(path));self.ptr=c.POINTER(c.c_double);self.iptr=c.POINTER(c.c_int64)
        self.lib.hpss_masks.argtypes=[self.ptr]*3+[c.c_size_t];self.lib.hpss_masks.restype=c.c_uint
        self.lib.hpss_overlap_add.argtypes=[self.ptr,c.c_size_t,c.c_uint,self.iptr,self.iptr,c.c_size_t,self.ptr,c.c_uint,self.ptr,c.c_size_t,self.ptr]
        self.lib.hpss_overlap_add.restype=c.c_uint
    def ptr_of(self,x):return x.ctypes.data_as(self.ptr)
    def mask(self,h,p):
        h=np.ascontiguousarray(h,dtype=np.float64);p=np.ascontiguousarray(p,dtype=np.float64)
        if h.shape!=p.shape:raise ValueError('mask shape')
        result=np.empty_like(h)
        if not self.lib.hpss_masks(self.ptr_of(h),self.ptr_of(p),self.ptr_of(result),h.size):raise ValueError('finite nonnegative medians required')
        return result
    def ola(self,x,source,target,window,output_frames):
        x=np.ascontiguousarray(x,dtype=np.float64);s=np.ascontiguousarray(source,dtype=np.int64);t=np.ascontiguousarray(target,dtype=np.int64)
        window=np.ascontiguousarray(window,dtype=np.float64)
        if (x.ndim!=2 or not 1<=x.shape[1]<=8 or not np.isfinite(x).all() or s.ndim!=1 or t.shape!=s.shape
            or window.ndim!=1 or output_frames<0):raise ValueError('OLA shape/control')
        output=np.zeros((output_frames,x.shape[1]));den=np.zeros(output_frames)
        good=self.lib.hpss_overlap_add(self.ptr_of(x),len(x),x.shape[1],s.ctypes.data_as(self.iptr),t.ctypes.data_as(self.iptr),len(s),
            self.ptr_of(window),len(window),self.ptr_of(output),output_frames,self.ptr_of(den))
        if not good:raise ValueError('OLA kernel controls')
        return output,den

def checked(x,rate):
    x=np.asarray(x,dtype=np.float64)
    if x.ndim==1:x=x[:,None]
    if x.ndim!=2 or not 1<=x.shape[1]<=8 or not np.isfinite(x).all() or rate not in (44100,48000,96000):raise ValueError('signal/rate')
    return x

def separate(x,rate,kernel):
    x=checked(x,rate)
    if not len(x):return x.copy(),x.copy(),dict(separation_error=0.,percussive_energy_fraction=0.)
    win=2048*(2 if rate==96000 else 1);nfft=2*win;hop=win//8
    window=np.zeros(nfft);window[(nfft-win)//2:(nfft+win)//2]=signal.windows.hann(win,sym=False)
    centers=np.arange(0,len(x)+win//2+hop,hop)
    padded=np.pad(x,((nfft//2,nfft),(0,0)))
    spectra=np.array([np.fft.rfft(np.fft.ifftshift(padded[t:t+nfft]*window[:,None],axes=0),axis=0) for t in centers])
    linked=np.sqrt(np.mean(np.abs(spectra)**2,axis=2))
    h=ndimage.median_filter(linked,size=(17,1),mode='nearest')
    p=ndimage.median_filter(linked,size=(1,17),mode='nearest')
    mask=kernel.mask(h,p)
    output=np.zeros_like(padded);den=np.zeros(len(padded))
    for i,t in enumerate(centers):
        frame=np.fft.fftshift(np.fft.irfft(spectra[i]*mask[i,:,None],n=nfft,axis=0),axes=0)
        output[t:t+nfft]+=frame*window[:,None];den[t:t+nfft]+=window**2
    den=den[nfft//2:nfft//2+len(x)]
    if np.min(den)<1e-9:raise ValueError('separator coverage')
    harmonic=output[nfft//2:nfft//2+len(x)]/den[:,None]
    percussive=x-harmonic
    return harmonic,percussive,dict(separation_error=float(np.max(np.abs(harmonic+percussive-x))),
        percussive_energy_fraction=float(np.sum(percussive**2)/max(np.sum(x**2),1e-30)),separator_frames=len(centers),separator_window=win)

def ola_render(x,rate,time,pitch,kernel):
    x=checked(x,rate);alpha=time*pitch;target=int(np.floor(len(x)*time+.5))
    if not len(x):return np.zeros((target,x.shape[1])),dict(ola_grains=0,min_ola_weight=0.)
    win=256*(2 if rate==96000 else 1);hop=max(1,int(win/(8*max(1,alpha))))
    centers=np.arange(0,len(x)+win//2+hop,hop,dtype=np.int64)
    synth=np.floor(centers*alpha+.5).astype(np.int64);middle=max(1,int(np.floor(len(x)*alpha+.5)))
    result,den=kernel.ola(x,centers,synth,signal.windows.hann(win,sym=False),middle)
    if np.min(den)<1e-9:raise ValueError('short-grain coverage hole')
    result/=den[:,None]
    if target!=middle:result=signal.resample(result,target,axis=0)
    return result,dict(ola_grains=len(centers),min_ola_weight=float(den.min()),short_window=win,short_hop=hop)

def render(x,rate,time=1.,pitch=1.,mode='hps_heap_ola',phase_kernel=None,hps_kernel=None,components=None):
    x=checked(x,rate)
    if mode not in MODES or not .5<=time<=2 or not .5<=pitch<=2:raise ValueError('mode/ratio')
    if mode in ('locked','heap'):
        y,stats=phase.render(x,rate,time,pitch,mode,phase_kernel)
        return y,dict(**stats,hybrid=False,offline=True)
    kernel=Kernels(hps_kernel)
    h,p,stats=separate(x,rate,kernel) if components is None else components
    if h.shape!=x.shape or p.shape!=x.shape:raise ValueError('component shape')
    harmonic_mode='heap' if '_heap_' in mode else 'locked'
    yh,hs=phase.render(h,rate,time,pitch,harmonic_mode,phase_kernel)
    if mode.endswith('_ola'):yp,ps=ola_render(p,rate,time,pitch,kernel)
    else:yp,ps=phase.render(p,rate,time,pitch,'locked',phase_kernel,window=256)
    y=yh+yp
    if y.shape!=(int(np.floor(len(x)*time+.5)),x.shape[1]) or not np.isfinite(y).all():raise ValueError('hybrid output')
    return y,dict(**stats,harmonic_frames=hs.get('analysis_frames',0),percussive_frames=ps.get('ola_grains',ps.get('analysis_frames',0)),
        hybrid=True,offline=True,formant_preservation=False)
