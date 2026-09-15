"""Input-only stereo-linked transient candidates; offline envelope calculation.

Keep the previous detector's envelope/prominence tests, independently varying
refractory spacing and channel fusion. No generated-event truth enters detection.
"""
import ctypes as c
import numpy as np
from scipy import ndimage, signal

class Fusion:
    def __init__(self, library, capacity):
        self.lib=c.CDLL(str(library));self.ptr=c.POINTER(c.c_double)
        self.lib.linked_events_create.argtypes=[c.c_uint32];self.lib.linked_events_create.restype=c.c_void_p
        self.lib.linked_events_destroy.argtypes=[c.c_void_p];self.lib.linked_events_destroy.restype=None
        self.lib.linked_events_process.argtypes=[c.c_void_p,self.ptr,self.ptr,c.c_uint32,c.c_double,self.ptr,c.c_uint32]
        self.lib.linked_events_process.restype=c.c_int64
        self.handle=self.lib.linked_events_create(capacity);self.capacity=capacity
        if not self.handle:raise ValueError('fusion capacity')
    def close(self):
        if self.handle:self.lib.linked_events_destroy(self.handle);self.handle=None
    def process(self, times, scores, tolerance):
        t=np.ascontiguousarray(times,dtype=np.float64);s=np.ascontiguousarray(scores,dtype=np.float64)
        if t.ndim!=1 or s.shape!=t.shape or len(t)>self.capacity:raise ValueError('fusion shape/capacity')
        out=np.empty_like(t)
        n=self.lib.linked_events_process(self.handle,t.ctypes.data_as(self.ptr),s.ctypes.data_as(self.ptr),len(t),
            tolerance,out.ctypes.data_as(self.ptr),len(out))
        if n<0:raise ValueError('invalid fusion batch')
        return out[:n]

def fusion_reference(times, scores, tolerance):
    order=sorted(range(len(times)),key=lambda i:(times[i],-scores[i]))
    result=[]
    while order:
        first=times[order[0]]
        group=[i for i in order if times[i]-first<=tolerance]
        result.append(times[min(group,key=lambda i:(-scores[i],times[i]))])
        order=order[len(group):]
    return np.asarray(result,dtype=float)

def detect(x, rate, mode='linked6', library=None):
    x=np.asarray(x,dtype=float)
    if x.ndim==1:x=x[:,None]
    if x.ndim!=2 or not 1<=x.shape[1]<=8 or not np.isfinite(x).all() or rate not in (44100,48000,96000):
        raise ValueError('invalid detector audio/rate')
    if mode not in ('legacy40','global6','linked6'):raise ValueError('detector mode')
    if not len(x):return np.empty(0),dict(candidates=0,anchors=0)
    step=max(1,round(rate*.001))
    powers=x*x if mode=='linked6' else np.mean(x*x,axis=1,keepdims=True)
    times=[];scores=[]
    for ch in range(powers.shape[1]):
        env=ndimage.uniform_filter1d(powers[:,ch],size=step,mode='constant')[::step]
        maximum=float(env.max())
        if maximum<=1e-24:continue
        floor=ndimage.median_filter(env,size=51,mode='nearest')
        distance=max(1,round((.04 if mode=='legacy40' else .006)*rate/step))
        peaks,properties=signal.find_peaks(env,distance=distance,prominence=.05*maximum)
        keep=env[peaks]>4*floor[peaks]
        times.extend((peaks[keep]*step).tolist())
        scores.extend((properties['prominences'][keep]/maximum).tolist())
    if library:
        fusion=Fusion(library,len(times))
        try:events=fusion.process(times,scores,rate*.001 if mode=='linked6' else 0.)
        finally:fusion.close()
    else:events=fusion_reference(times,scores,rate*.001 if mode=='linked6' else 0.)
    # Boundary endpoints cannot be interpolation anchors.
    events=events[(events>0)&(events<len(x))]
    return events,dict(candidates=len(times),anchors=len(events))
