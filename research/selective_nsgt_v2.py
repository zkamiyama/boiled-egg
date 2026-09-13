"""Offline selective-window experiment, inspired by SELEBI arXiv:2602.16421.

Not a paper reproduction: power-weighted discretized MPD, coverage-bound hops,
identity phase locking instead of full phase-gradient integration, and Fourier
output resampling. Optional phase-frequency compatibility is our ablation, not
SELEBI. No streaming/RT/host-latency claim; no trained neural model.
"""
from __future__ import annotations
from dataclasses import dataclass
import numpy as np
from scipy import ndimage, signal

@dataclass(frozen=True)
class Config:
    adaptive: bool = True
    coherence: bool = False
    long_window: int = 2048
    hop: int = 256
    mpd_tolerance: float = .25
    prominence: float = .1


def wrap(x):return (x+np.pi)%(2*np.pi)-np.pi


def win(length, nfft):
    w=np.zeros(nfft);start=(nfft-length)//2
    w[start:start+length]=signal.windows.hann(length,sym=False)
    return w


def frame(x,center,w):
    n=len(w);y=np.zeros((n,x.shape[1]));lo=center-n//2
    a,b=max(0,lo),min(len(x),lo+n)
    if b>a:y[a-lo:b-lo]=x[a:b]
    return np.fft.rfft(np.fft.ifftshift(y*w[:,None],axes=0),axis=0)


def percussion(x,nfft,length,hop,tolerance,prominence):
    centers=np.arange(0,len(x)+hop,hop);w=win(length,nfft);scores=np.zeros(len(centers));previous=None
    for i,t in enumerate(centers):
        z=frame(x,int(t),w);mag=np.abs(z)
        df=wrap(np.angle(z[1:]*z[:-1].conj()))
        if previous is not None:
            mixed=wrap(df-previous)*nfft/(2*np.pi*hop)
            energy=mag[1:]**2;mask=(np.abs(mixed-1)<tolerance)&(mag[1:]>mag.max()*1e-3)
            if energy.sum()>1e-24:scores[i]=float((energy*mask).sum()/energy.sum())
        previous=df
    scores=ndimage.median_filter(scores,size=3,mode='nearest')
    peaks,_=signal.find_peaks(scores,prominence=prominence,distance=3)
    return centers[peaks],scores[peaks]


def owners(mag):
    peaks,_=signal.find_peaks(mag,height=mag.max()*10**(-55/20))
    if mag[0]>mag[1]:peaks=np.r_[0,peaks]
    if mag[-1]>=mag[-2]:peaks=np.r_[peaks,len(mag)-1]
    if not len(peaks):peaks=np.array([int(mag.argmax())])
    return peaks[np.searchsorted((peaks[:-1]+peaks[1:])//2+1,np.arange(len(mag)),side='right')]


def render(x, rate:int, time_ratio:float=1., pitch_ratio:float=1., cfg:Config=Config()):
    x=np.asarray(x,dtype=np.float64)
    if x.ndim==1:x=x[:,None]
    if (x.ndim!=2 or not 1<=x.shape[1]<=8 or not np.isfinite(x).all() or
        rate not in (44100,48000,96000) or not .5<=time_ratio<=2 or not .5<=pitch_ratio<=2 or
        not 64<=cfg.long_window<=8192 or cfg.long_window&(cfg.long_window-1) or
        not 1<=cfg.hop<=cfg.long_window//4 or not 0<cfg.mpd_tolerance<1 or not 0<cfg.prominence<1):
        raise ValueError('invalid signal/control/window configuration')
    target=int(np.floor(len(x)*time_ratio+.5));alpha=time_ratio*pitch_ratio
    if not len(x):return np.zeros((0,x.shape[1])),dict(frames=0,adapted_frames=0,events=0)
    scale=2 if rate==96000 else 1;longest=cfg.long_window*scale;nfft=2*longest;hop0=cfg.hop*scale
    events,strength=(percussion(x,nfft,longest,hop0,cfg.mpd_tolerance,cfg.prominence)
        if cfg.adaptive and alpha>1 else (np.array([],int),np.array([])))
    # SELEBI Algorithm 3-inspired window-support minima. Actual hop redistribution
    # in this adaptation is a conservative OLA-coverage rule, not Algorithm 4.
    minimum=np.maximum(64*scale,2*(np.floor(longest-strength**2*(1-1/alpha)*longest).astype(int)//2))
    intermediate=max(1,int(np.floor(len(x)*alpha+.5)))
    y=np.zeros((intermediate+2*nfft,x.shape[1]));den=np.zeros(len(y))
    omega=np.arange(nfft//2+1)*2*np.pi/nfft;rotation=np.zeros(len(omega));index=np.arange(len(omega))
    prev_phase=None;prev_mag=None;prev_t=prev_s=0;prev_length=longest;holdoff=0;steps=adapted=unlocked=0;t=0
    while t<=len(x)+longest//2:
        length=int(min(longest,np.min(np.maximum(minimum,2*np.abs(events-t))))) if len(events) else longest
        length=max(4,2*(length//2));w=win(length,nfft);z=frame(x,t,w);mag=np.abs(z);phase=np.angle(z)
        linked=np.sqrt(np.mean(mag**2,axis=1));owner=owners(linked);refs=np.argmax(mag,axis=1);synth=int(np.floor(t*alpha+.5))
        if prev_phase is not None:
            da=t-prev_t;ds=synth-prev_s
            residual=wrap(phase[index,refs]-prev_phase[index,refs]-omega*da)
            freq=omega+residual/da;predicted=wrap(rotation+(ds-da)*freq)
            rotation=predicted[owner]
            if cfg.coherence:
                flux=float(np.maximum(linked-prev_mag,0).sum()/(prev_mag.sum()+1e-12))
                if flux>.12 or length!=prev_length:holdoff=(longest+hop0-1)//hop0+2
                elif holdoff:holdoff-=1
                if not holdoff:
                    different=np.abs(wrap((freq-freq[owner])*da))/da>np.pi/nfft
                    rotation=np.where(different,predicted,rotation);unlocked+=int(different.sum())
        output=mag*np.exp(1j*(phase+rotation[:,None]))
        synthesis=np.fft.fftshift(np.fft.irfft(output,n=nfft,axis=0),axes=0)*w[:,None]
        lo=synth+nfft//2;hi=min(lo+nfft,len(y))
        if hi>lo:y[lo:hi]+=synthesis[:hi-lo];den[lo:hi]+=(w*w)[:hi-lo]
        prev_phase=phase;prev_mag=linked;prev_t=t;prev_s=synth;prev_length=length
        steps+=1;adapted+=int(length<longest)
        t+=max(1,min(hop0,int(np.floor(length/(4*max(alpha,1))))))
    out=y[nfft:nfft+intermediate];weight=den[nfft:nfft+intermediate]
    if np.min(weight)<1e-8:raise ValueError('coverage hole')
    out/=weight[:,None]
    if target!=intermediate:out=signal.resample(out,target,axis=0)
    if not np.isfinite(out).all():raise ValueError('nonfinite synthesis')
    return out,dict(frames=steps,adapted_frames=adapted,events=len(events),unlocked_bins=unlocked,
        min_weight=float(weight.min()),offline=True,formant_preservation=False)
