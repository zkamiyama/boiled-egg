"""Offline matched-window edge transport, adapted from the project's renderer.

Edge ablations change only integration increments. The separate project modes
refine the inherited heap spectra. No automatic profile switching or gain EQ.
Both-edge increments are causal, but this full-array Python renderer is NOT RT.
Temporal-only and frequency-only variants isolate which averaging matters.
"""
MODES=('locked','heap','edge_time','edge_frequency','edge_both','project2','project4','project8')
import ctypes as c
import numpy as np
from scipy import signal
from consistency import refine

def wrap(v):return (v+np.pi)%(2*np.pi)-np.pi

def derivatives(phase,hop,nfft):
    omega=2*np.pi*np.arange(phase.shape[1])/nfft
    back=wrap(phase[1:]-phase[:-1]-hop*omega)/hop+omega
    dt=np.empty_like(phase);dt[0]=back[0];dt[-1]=back[-1];dt[1:-1]=.5*(back[:-1]+back[1:])
    edge=wrap(np.diff(phase,axis=1));df=np.empty_like(phase)
    df[:,0]=edge[:,0];df[:,-1]=edge[:,-1];df[:,1:-1]=.5*(edge[:,:-1]+edge[:,1:])
    return dt,df,back

class Kernel:
    def __init__(self,path,bins):
        self.lib=c.CDLL(str(path));ptr=c.POINTER(c.c_double)
        self.lib.phase_heap_create.argtypes=[c.c_uint];self.lib.phase_heap_create.restype=c.c_void_p
        self.lib.phase_heap_destroy.argtypes=[c.c_void_p]
        self.lib.phase_heap_process.argtypes=[c.c_void_p]+[ptr]*7+[c.c_double]*3+[ptr]
        self.lib.phase_heap_process.restype=c.c_uint
        self.bins=bins;self.ptr=ptr;self.h=self.lib.phase_heap_create(bins)
        if not self.h:raise ValueError('kernel construction')
    def close(self):
        if self.h:self.lib.phase_heap_destroy(self.h);self.h=None
    def process(self,mag,oldmag,dt,olddt,df,oldphase,phase,hs,alpha):
        arrays=[np.ascontiguousarray(a,dtype=np.float64) for a in (mag,oldmag,dt,olddt,df,oldphase,phase)]
        if any(a.shape!=(self.bins,) or not np.isfinite(a).all() for a in arrays):raise ValueError("finite kernel arrays of declared bin count required")
        if np.any(arrays[0]<0) or np.any(arrays[1]<0) or not np.isfinite(hs) or hs<0 or not .25<=alpha<=4:raise ValueError("invalid kernel magnitude/hop/stretch")
        out=np.empty_like(arrays[0])
        n=self.lib.phase_heap_process(self.h,*[a.ctypes.data_as(self.ptr) for a in arrays],hs,alpha,1e-6,out.ctypes.data_as(self.ptr))
        return wrap(out),n


class EdgeKernel:
    def __init__(self,path,bins):
        self.lib=c.CDLL(str(path));self.ptr=c.POINTER(c.c_double);self.bins=bins
        self.lib.phase_edge_create.argtypes=[c.c_uint];self.lib.phase_edge_create.restype=c.c_void_p
        self.lib.phase_edge_destroy.argtypes=[c.c_void_p]
        self.lib.phase_edge_process.argtypes=[c.c_void_p]+[self.ptr]*6+[c.c_double,self.ptr,c.POINTER(c.c_uint)]
        self.lib.phase_edge_process.restype=c.c_int
        self.h=self.lib.phase_edge_create(bins)
        if not self.h:raise ValueError('edge kernel construction')
    def close(self):
        if self.h:self.lib.phase_edge_destroy(self.h);self.h=None
    def process(self,mag,oldmag,dt,df,oldphase,phase):
        arrays=[np.ascontiguousarray(a,dtype=np.float64) for a in (mag,oldmag,dt,df,oldphase,phase)]
        for i,a in enumerate(arrays):
            if a.shape!=((self.bins-1,) if i==3 else (self.bins,)) or not np.isfinite(a).all():
                raise ValueError('edge array dimensions/finite values')
        out=np.empty(self.bins);stats=(c.c_uint*3)()
        status=self.lib.phase_edge_process(self.h,*[a.ctypes.data_as(self.ptr) for a in arrays],1e-6,out.ctypes.data_as(self.ptr),stats)
        if status:raise ValueError('edge kernel invalid controls')
        return wrap(out),stats[1]

def render(x,rate,time=1.,pitch=1.,mode='heap',kernel_path=None,window=2048,edge_path=None):
    iterations=int(mode[7:]) if mode.startswith('project') and mode in MODES else 0
    x=np.asarray(x,dtype=float)
    if x.ndim==1:x=x[:,None]
    if (x.ndim!=2 or x.shape[1]<1 or not np.isfinite(x).all() or rate not in (44100,48000,96000)
        or not .5<=time<=2 or not .5<=pitch<=2 or mode not in MODES
        or window<64 or window>4096 or window&(window-1)):
        raise ValueError('invalid phase study input')
    if iterations:mode='heap'
    target=int(np.floor(len(x)*time+.5));alpha=time*pitch
    if not len(x):return np.zeros((target,x.shape[1])),dict(vertical=0,analysis_frames=0,identity=True)
    win=window*(2 if rate==96000 else 1);N=2*win;hop=max(1,int(win/(8*max(1,alpha))))
    w=np.zeros(N);w[(N-win)//2:(N+win)//2]=signal.windows.hann(win,sym=False)
    centers=np.arange(0,len(x)+win//2+hop,hop)
    padded=np.pad(x,((N//2,N), (0,0)))
    coeff=np.array([np.fft.rfft(np.fft.ifftshift(padded[t:t+N]*w[:,None],axes=0),axis=0) for t in centers])
    ref=int(np.argmax(np.sum(x*x,axis=0)));phase=np.angle(coeff[:,:,ref]);mag=np.sqrt(np.mean(np.abs(coeff)**2,axis=2))
    dt,df,back=derivatives(phase,hop,N);synth=np.floor(centers*alpha+.5).astype(int)
    middle=max(1,int(np.floor(len(x)*alpha+.5)));y=np.zeros((middle+3*N,x.shape[1]));weight=np.zeros(len(y));prev=phase[0];vertical=0
    kernel=Kernel(kernel_path,mag.shape[1]) if mode=='heap' else EdgeKernel(edge_path,mag.shape[1]) if mode.startswith('edge_') else None
    constructed=[]
    try:
        for i,t in enumerate(synth):
            hs=t-synth[i-1] if i else 0
            if i==0 or alpha==1:current=phase[i].copy()
            elif mode=='heap':current,n=kernel.process(mag[i],mag[i-1],dt[i],dt[i-1],df[i],prev,phase[i],hs,alpha);vertical+=n
            elif mode.startswith('edge_'):
                temporal=hs*back[i-1] if mode in ('edge_time','edge_both') else .5*hs*(dt[i-1]+dt[i])
                frequency=alpha*wrap(np.diff(phase[i])) if mode in ('edge_frequency','edge_both') else .5*alpha*(df[i,:-1]+df[i,1:])
                current,n=kernel.process(mag[i],mag[i-1],temporal,frequency,prev,phase[i]);vertical+=n
            elif mode=='trapezoid':current=wrap(prev+.5*hs*(dt[i-1]+dt[i]))
            else:
                predicted=prev+hs*back[i-1]
                peaks,_=signal.find_peaks(mag[i]);peaks=np.r_[0,peaks,mag.shape[1]-1]
                owner=peaks[np.searchsorted((peaks[:-1]+peaks[1:])//2+1,np.arange(mag.shape[1]))]
                current=wrap(predicted[owner]+wrap(phase[i]-phase[i,owner]))
            rotation=wrap(current-phase[i]);z=coeff[i]*np.exp(1j*rotation[:,None])
            if iterations:constructed.append(z)
            frame=np.fft.fftshift(np.fft.irfft(z,n=N,axis=0),axes=0)*w[:,None]
            lo=t+N//2;y[lo:lo+N]+=frame;weight[lo:lo+N]+=w*w;prev=current
        errors=[]
        if iterations:
            audio,errors=refine(coeff,np.array(constructed),synth,w,len(y),iterations)
        result=y[N:N+middle];den=weight[N:N+middle]
        if np.min(den)<1e-9:raise ValueError('overlap coverage hole')
        result/=den[:,None]
        if iterations:result=audio[N:N+middle]
        if target!=middle:result=signal.resample(result,target,axis=0)
        if not np.isfinite(result).all():raise ValueError('nonfinite reconstruction')
        return result,dict(vertical=vertical,analysis_frames=len(centers),identity=alpha==1,window=win,fft=N,analysis_hop=hop,projection_iterations=iterations,consistency_initial=errors[0] if errors else None,consistency_final=errors[-1] if errors else None)
    finally:
        if kernel:kernel.close()
