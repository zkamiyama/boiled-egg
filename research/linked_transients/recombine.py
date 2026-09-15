"""Shared full-band phase field and localized residual replacement, offline.

Given the input-derived phase field R, A_R is a linear analysis/rotation/synthesis
operator. A_R(x-q)+A_R(q)=A_R(x). Replacing only A_R(q) by local waveform transport
isolates independent component phase histories without fitting output gain.
No formant preservation, live automation or realtime pipeline claim.
"""
import importlib.util
from pathlib import Path
import numpy as np
from scipy import signal
from detection import detect

_path=Path(__file__).parents[1]/'transient_transport/transport.py'
_spec=importlib.util.spec_from_file_location('linked_prior_transport',_path)
prior=importlib.util.module_from_spec(_spec);_spec.loader.exec_module(prior)
base=prior.base
MODES=('locked','heap','independent_legacy','independent_linked','shared_long','shared_linked','localized_shared')

class PhaseField:
    def __init__(self,x,rate,ratio,kernel_path):
        self.x=prior.audio(x);self.ratio=ratio
        self.win=2048*(2 if rate==96000 else 1);self.n=2*self.win
        self.hop=max(1,int(self.win/(8*max(1,ratio))))
        self.w=np.zeros(self.n);self.w[(self.n-self.win)//2:(self.n+self.win)//2]=signal.windows.hann(self.win,sym=False)
        self.centers=np.arange(0,len(x)+self.win//2+self.hop,self.hop)
        self.synth=np.floor(self.centers*ratio+.5).astype(int)
        self.target=int(np.floor(len(x)*ratio+.5));self.length=max(1,self.target)+3*self.n
        self.coeff=self.analyze(x);ref=int(np.argmax(np.sum(x*x,axis=0)))
        phase=np.angle(self.coeff[:,:,ref]);mag=np.sqrt(np.mean(abs(self.coeff)**2,axis=2))
        dt,df,_=base.derivatives(phase,self.hop,self.n)
        self.rotation=np.empty_like(phase);prev=phase[0];kernel=base.Kernel(kernel_path,mag.shape[1])
        try:
            for i,t in enumerate(self.synth):
                hs=t-self.synth[i-1] if i else 0
                if i==0 or ratio==1:current=phase[i].copy()
                else:current,_=kernel.process(mag[i],mag[i-1],dt[i],dt[i-1],df[i],prev,phase[i],hs,ratio)
                self.rotation[i]=base.wrap(current-phase[i]);prev=current
        finally:kernel.close()
        self.rotor=np.exp(1j*self.rotation[:,:,None])
    def analyze(self,x):
        padded=np.pad(x,((self.n//2,self.n),(0,0)))
        return np.array([np.fft.rfft(np.fft.ifftshift(padded[t:t+self.n]*self.w[:,None],axes=0),axis=0) for t in self.centers])
    def apply(self,x=None):
        coeff=self.coeff if x is None else self.analyze(x)
        y=np.zeros((self.length,self.x.shape[1]));weight=np.zeros(self.length)
        for i,t in enumerate(self.synth):
            z=coeff[i]*self.rotor[i]
            frame=np.fft.fftshift(np.fft.irfft(z,n=self.n,axis=0),axes=0)*self.w[:,None]
            lo=t+self.n//2;y[lo:lo+self.n]+=frame;weight[lo:lo+self.n]+=self.w*self.w
        out=y[self.n:self.n+self.target];den=weight[self.n:self.n+self.target]
        if len(den) and den.min()<1e-9:raise ValueError('phase-field coverage hole')
        return out/den[:,None]

def local_gate(length,ratio,anchors,rate):
    gate=np.zeros(length);edges=np.r_[0.,anchors,float(length)]
    for i,u in enumerate(anchors):
        radius=min(.012*rate,.2*min(u-edges[i],edges[i+2]-u)*min(1.,ratio))
        if radius<=0:continue
        a=max(0,int(np.floor(u-radius)));b=min(length,int(np.ceil(u+radius))+1)
        distance=np.abs(np.arange(a,b)-u)/radius
        weight=np.where(distance<=.5,1.,np.where(distance<1.,.5*(1+np.cos(np.pi*(2*distance-1))),0.))
        gate[a:b]=np.maximum(gate[a:b],weight)
    return gate

def grains(x,rate,ratio,anchors):
    target=int(np.floor(len(x)*ratio+.5));win=256*(2 if rate==96000 else 1);hop=win//4
    w=signal.windows.hann(win,sym=False)**2;synth=np.arange(0,target+win//2+hop,hop)
    out,src=prior.anchor_knots(len(x),ratio,anchors,rate)
    centers=np.floor(prior.map_positions(synth,out,src)+.5).astype(np.int64)
    y=np.zeros((target+2*win,x.shape[1]));den=prior.overlap_weights(synth,centers,w,len(y),True)
    for s,c in zip(synth,centers):
        a,b=max(0,c-win//2),min(len(x),c+win//2);frame=np.zeros((win,x.shape[1]))
        if b>a:frame[a-c+win//2:b-c+win//2]=x[a:b]
        y[s:s+win]+=frame*w[:,None]
    weights=den[win//2:win//2+target]
    if len(weights) and weights.min()<1e-12:raise ValueError('grain coverage hole')
    return y[win//2:win//2+target]/weights[:,None]

def render_set(x,rate,ratio,heap_library,event_library,modes=MODES):
    x=prior.audio(x)
    if rate not in (44100,48000,96000) or not np.isfinite(ratio) or not .5<=ratio<=2 or not set(modes)<=set(MODES):
        raise ValueError('research controls')
    target=int(np.floor(len(x)*ratio+.5));outputs={};stats={}
    if not len(x):return {m:np.zeros((target,x.shape[1])) for m in modes},{m:dict(anchors=0) for m in modes}
    if 'locked' in modes:outputs['locked'],stats['locked']=base.render(x,rate,time=ratio,mode='locked',kernel_path=heap_library)
    field=PhaseField(x,rate,ratio,heap_library);full=field.apply()
    if 'heap' in modes:outputs['heap']=full;stats['heap']=dict(anchors=0)
    if set(modes)-{'locked','heap'}:
        h,p,sp=prior.separate(x,rate)
        legacy,_=detect(p,rate,'legacy40',event_library);linked,ds=detect(p,rate,'linked6',event_library)
        if 'independent_legacy' in modes or 'independent_linked' in modes:
            hp,_=base.render(h,rate,time=ratio,mode='heap',kernel_path=heap_library)
            for m,anchors in [('independent_legacy',legacy),('independent_linked',linked)]:
                if m in modes:outputs[m]=hp+grains(p,rate,ratio,anchors);stats[m]=dict(sp,anchors=len(anchors))
        if 'shared_long' in modes or 'shared_linked' in modes:
            ps=field.apply(p);hs=field.apply(h)
            if 'shared_long' in modes:outputs['shared_long']=hs+ps;stats['shared_long']=dict(sp,anchors=0,recombine_error=float(abs(hs+ps-full).max()))
            if 'shared_linked' in modes:outputs['shared_linked']=hs+grains(p,rate,ratio,linked);stats['shared_linked']=dict(sp,**ds)
        if 'localized_shared' in modes:
            gate=local_gate(len(x),ratio,linked,rate);q=p*gate[:,None]
            outputs['localized_shared']=full-field.apply(q)+grains(q,rate,ratio,linked)
            stats['localized_shared']=dict(sp,**ds,gate_fraction=float(gate.mean()),replacement_energy_fraction=float(np.sum(q*q)/max(np.sum(x*x),1e-30)))
    for m,y in outputs.items():
        if y.shape!=(target,x.shape[1]) or not np.isfinite(y).all():raise ValueError('invalid render output')
    return outputs,stats
