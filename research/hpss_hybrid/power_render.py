"""Post-primary address-coherent white-noise normalization ablation, offline.

Different source sample addresses are modeled as uncorrelated. This assumption
is NOT valid for general tonal or colored noise residuals. No fitted gains,
source/output loudness statistics, limiter or per-frame envelope target.
"""
import ctypes as c
import numpy as np
from scipy import signal
import render as r
MODES=('hps_heap_ola','hps_heap_sparse','hps_heap_power','hps_heap_sparse_power')

class PowerKernel:
    def __init__(self,path):
        self.lib=c.CDLL(str(path));self.dp=c.POINTER(c.c_double);self.ip=c.POINTER(c.c_int64)
        self.lib.hpss_grouped_power.argtypes=[c.c_size_t,self.ip,self.ip,c.c_size_t,self.dp,c.c_uint,c.c_size_t,self.dp,self.ip,self.dp]
        self.lib.hpss_grouped_power.restype=c.c_uint
    def weights(self,frames,source,target,window,length):
        s=np.ascontiguousarray(source,dtype=np.int64);t=np.ascontiguousarray(target,dtype=np.int64);w=np.ascontiguousarray(window,dtype=np.float64)
        if s.ndim!=1 or s.shape!=t.shape or w.ndim!=1 or length<0 or frames<0:raise ValueError('power dimensions')
        out=np.empty(length);scratch=np.empty(length);keys=np.empty(length,dtype=np.int64)
        good=self.lib.hpss_grouped_power(frames,s.ctypes.data_as(self.ip),t.ctypes.data_as(self.ip),len(s),w.ctypes.data_as(self.dp),len(w),length,
            out.ctypes.data_as(self.dp),keys.ctypes.data_as(self.ip),scratch.ctypes.data_as(self.dp))
        if not good:raise ValueError('power input/monotone address groups')
        return out

def short_render(x,rate,time,pitch,kernel,power,sparse=False,use_power=False):
    x=r.checked(x,rate);alpha=time*pitch;target=int(np.floor(len(x)*time+.5))
    if not len(x):return np.zeros((target,x.shape[1]))
    win=256*(2 if rate==96000 else 1)
    hop=max(1,int(min(win/4,win/(2*alpha)))) if sparse else max(1,int(win/(8*max(1,alpha))))
    source=np.arange(0,len(x)+win//2+hop,hop,dtype=np.int64);synth=np.floor(source*alpha+.5).astype(np.int64)
    middle=max(1,int(np.floor(len(x)*alpha+.5)));window=signal.windows.hann(win,sym=False)
    out,linear=kernel.ola(x,source,synth,window,middle)
    denominator=np.sqrt(power.weights(len(x),source,synth,window,middle)) if use_power else linear
    if np.min(denominator)<1e-9:raise ValueError('normalizer coverage')
    out/=denominator[:,None]
    if target!=middle:out=signal.resample(out,target,axis=0)
    return out

def render(x,rate,time=1.,pitch=1.,mode='hps_heap_power',phase_kernel=None,hps_kernel=None,power_kernel=None,components=None):
    x=r.checked(x,rate)
    if mode not in MODES or not .5<=time<=2 or not .5<=pitch<=2:raise ValueError('power mode/ratio')
    k=r.Kernels(hps_kernel);pk=PowerKernel(power_kernel)
    h,p,stats=r.separate(x,rate,k) if components is None else components
    yh,_=r.phase.render(h,rate,time,pitch,'heap',phase_kernel)
    yp=short_render(p,rate,time,pitch,k,pk,'sparse' in mode,'power' in mode)
    y=yh+yp
    if y.shape!=(int(np.floor(len(x)*time+.5)),x.shape[1]) or not np.isfinite(y).all():raise ValueError('power output')
    return y,dict(**stats,offline=True,normalizer='address-group-white-power' if 'power' in mode else 'amplitude',
        sparse='sparse' in mode,formant_preservation=False)
