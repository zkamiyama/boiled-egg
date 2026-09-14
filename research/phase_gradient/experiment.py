"""Offline phase-gradient comparison; production DSP is untouched.

Algorithm 1 and centered gradients (13)-(18) from Prusa/Holighaus 2017,
arXiv:2202.07382. Kernel written independently from the paper. Centered time
estimation requires one future frame. This experiment adds shared channel phase
rotation, deterministic input phases for sub-threshold bins and an explicit
unity bypass. It uses different windows/hops from the paper's listening test.
Only the C++ integration kernel is allocation-free, not this Python renderer.
"""
import ctypes as c
import numpy as np
from scipy import signal

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
        self.ptr=ptr;self.h=self.lib.phase_heap_create(bins)
        if not self.h:raise ValueError('kernel construction')
    def close(self):
        if self.h:self.lib.phase_heap_destroy(self.h);self.h=None
    def process(self,mag,oldmag,dt,olddt,df,oldphase,phase,hs,alpha):
        arrays=[np.ascontiguousarray(a,dtype=np.float64) for a in (mag,oldmag,dt,olddt,df,oldphase,phase)]
        out=np.empty_like(arrays[0])
        n=self.lib.phase_heap_process(self.h,*[a.ctypes.data_as(self.ptr) for a in arrays],hs,alpha,1e-6,out.ctypes.data_as(self.ptr))
        return wrap(out),n

def render(x,rate,time=1.,pitch=1.,mode='heap',kernel_path=None,window=2048):
    x=np.asarray(x,dtype=float)
    if x.ndim==1:x=x[:,None]
    if (x.ndim!=2 or x.shape[1]<1 or not np.isfinite(x).all() or rate not in (44100,48000,96000)
        or not .5<=time<=2 or not .5<=pitch<=2 or mode not in ('locked','trapezoid','heap')
        or window<64 or window>4096 or window&(window-1)):
        raise ValueError('invalid phase study input')
    target=int(np.floor(len(x)*time+.5));alpha=time*pitch
    if not len(x):return np.zeros((target,x.shape[1])),dict(vertical=0,analysis_frames=0,identity=True)
    win=window*(2 if rate==96000 else 1);N=2*win;hop=max(1,int(win/(8*max(1,alpha))))
    w=np.zeros(N);w[(N-win)//2:(N+win)//2]=signal.windows.hann(win,sym=False)
    centers=np.arange(0,len(x)+win//2+hop,hop)
    padded=np.pad(x,((N//2,N), (0,0)))
    coeff=np.array([np.fft.rfft(np.fft.ifftshift(padded[t:t+N]*w[:,None],axes=0),axis=0) for t in centers])
    ref=int(np.argmax(np.sum(x*x,axis=0)));phase=np.angle(coeff[:,:,ref]);mag=np.sqrt(np.mean(np.abs(coeff)**2,axis=2))
    dt,df,back=derivatives(phase,hop,N);synth=np.floor(centers*alpha+.5).astype(int)
    middle=int(np.floor(len(x)*alpha+.5));y=np.zeros((middle+3*N,x.shape[1]));weight=np.zeros(len(y));prev=phase[0];vertical=0
    kernel=Kernel(kernel_path,mag.shape[1]) if mode=='heap' else None
    try:
        for i,t in enumerate(synth):
            hs=t-synth[i-1] if i else 0
            if i==0 or alpha==1:current=phase[i].copy()
            elif mode=='heap':current,n=kernel.process(mag[i],mag[i-1],dt[i],dt[i-1],df[i],prev,phase[i],hs,alpha);vertical+=n
            elif mode=='trapezoid':current=wrap(prev+.5*hs*(dt[i-1]+dt[i]))
            else:
                predicted=prev+hs*back[i-1]
                peaks,_=signal.find_peaks(mag[i]);peaks=np.r_[0,peaks,mag.shape[1]-1]
                owner=peaks[np.searchsorted((peaks[:-1]+peaks[1:])//2+1,np.arange(mag.shape[1]))]
                current=wrap(predicted[owner]+wrap(phase[i]-phase[i,owner]))
            rotation=wrap(current-phase[i]);z=coeff[i]*np.exp(1j*rotation[:,None])
            frame=np.fft.fftshift(np.fft.irfft(z,n=N,axis=0),axes=0)*w[:,None]
            lo=t+N//2;y[lo:lo+N]+=frame;weight[lo:lo+N]+=w*w;prev=current
        result=y[N:N+middle];den=weight[N:N+middle]
        if np.min(den)<1e-9:raise ValueError('overlap coverage hole')
        result/=den[:,None]
        if target!=middle:result=signal.resample(result,target,axis=0)
        if not np.isfinite(result).all():raise ValueError('nonfinite reconstruction')
        return result,dict(vertical=vertical,analysis_frames=len(centers),identity=alpha==1,window=win,fft=N,analysis_hop=hop)
    finally:
        if kernel:kernel.close()
