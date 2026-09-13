"""Offline selective-window NSGT experiment inspired by SELEBI (2026).

NOT a reproduction: a calibrated thresholded MPD mask is used,
local hop is a coverage bound rather than the paper's interval-redistribution;
fixed 2048-at48k longest window, common 2x FFT, linked-channel rotation, optional
existing-style cepstral EQ, and Fourier output resampling. No RT/latency claim.
The `fixed` ablation uses the identical kernel, with window adaptation disabled.
Source: Akaishi/Holighaus/Yatabe, arXiv:2602.16421v1, Eqs.3-6 and Algorithm3.
"""
from __future__ import annotations
from dataclasses import dataclass
import argparse
import json
from pathlib import Path
import numpy as np
from scipy import signal, ndimage
import soundfile as sf

@dataclass(frozen=True)
class Config:
    long_window: int = 2048  # At 48 kHz; rate scaling preserves physical duration.
    hop: int = 256
    adapt: bool = True
    mpd_tolerance: float = .25
    magnitude_floor: float = 1e-3
    prominence: float = .1
    formant: str = 'off'
    formant_ratio: float = 1.


def audio(x):
    x=np.asarray(x,dtype=np.float64)
    if x.ndim==1:x=x[:,None]
    if x.ndim!=2 or not 1<=x.shape[1]<=8 or not np.isfinite(x).all():
        raise ValueError('finite 0..N by 1..8 audio required')
    return x


def wrap(x):
    return (x+np.pi)%(2*np.pi)-np.pi


def window(length: int, fft: int):
    # Zero-phase support [-L/2,L/2), shared frequency grid regardless of length.
    if length%2 or not 4<=length<=fft:raise ValueError('even window support required')
    w=np.zeros(fft);lo=(fft-length)//2
    w[lo:lo+length]=signal.windows.hann(length,sym=False)
    return w


def frame(x,center,fft,w):
    y=np.zeros((fft,x.shape[1]))
    lo=center-fft//2; a=max(0,lo);b=min(len(x),lo+fft)
    if b>a:y[a-lo:b-lo]=x[a:b]
    return np.fft.rfft(np.fft.ifftshift(y*w[:,None],axes=0),axis=0)


def percussion(x,rate,fft,length,hop,cfg):
    """Centered mixed phase derivative; impulse -> 1, sinusoid -> 0.

    Power-weighted across channels, so antiphase audio cannot cancel the detector.
    This is a declared derivative discretization, not the unpublished code.
    """
    centers=np.arange(0,len(x)+hop,hop,dtype=int)
    ratios=np.zeros(len(centers));prev=None; w=window(length,fft)
    for i,t in enumerate(centers):
        z=frame(x,int(t),fft,w);mag=np.abs(z)
        d=wrap(np.angle(z[1:]*z[:-1].conj()))
        if prev is not None:
            mixed=wrap(d-prev)*fft/(2*np.pi*hop)
            weight=mag[1:]**2
            mask=(np.abs(mixed-1)<cfg.mpd_tolerance)&(mag[1:]>mag.max()*cfg.magnitude_floor)
            total=weight.sum()
            if total>1e-24:ratios[i]=(weight*mask).sum()/total
        prev=d
    smooth=ndimage.median_filter(ratios,size=3,mode='nearest')
    peaks,_=signal.find_peaks(smooth,prominence=cfg.prominence,distance=max(1,round(.02*rate/hop)))
    return centers[peaks],smooth[peaks],centers,smooth


def owners(magnitude):
    peaks,_=signal.find_peaks(magnitude,height=magnitude.max()*10**(-55/20))
    if magnitude[0]>magnitude[1]:peaks=np.r_[0,peaks]
    if magnitude[-1]>=magnitude[-2]:peaks=np.r_[peaks,len(magnitude)-1]
    if not len(peaks):peaks=np.array([int(np.argmax(magnitude))])
    boundaries=(peaks[:-1]+peaks[1:])//2+1
    return peaks[np.searchsorted(boundaries,np.arange(len(magnitude)),side='right')]


def formant_gain(magnitude,rate,fft,pitch,cfg):
    warp=pitch/cfg.formant_ratio
    if cfg.formant=='off' or abs(warp-1)<1e-8:return np.ones(len(magnitude))
    cep=np.fft.irfft(np.log(np.maximum(magnitude,1e-7)),n=fft)
    order=min(round(40*rate/48000),fft//2-1)
    folded=np.minimum(np.arange(fft),fft-np.arange(fft))
    lift=(folded<=order).astype(float)
    taper=min(8,order-1);sel=(folded>order-taper)&(folded<=order)
    lift[sel]=.5*(1+np.cos(np.pi*(folded[sel]-(order-taper))/taper))
    env=np.fft.rfft(cep*lift).real
    target=np.interp(np.arange(len(env))*warp,np.arange(len(env)),env)
    gain_db=np.clip((target-env)*20/np.log(10),-15,15)
    if cfg.formant=='monophonic':
        qa=max(2,int(np.floor(rate/900)));qb=min(fft//2-1,int(np.ceil(rate/60)))
        positive=np.maximum(cep[qa:qb+1],0)
        confidence=0.;f0=0.
        if len(positive) and positive.max()>0:
            q=int(positive.argmax())+qa;f0=rate/q
            confidence=np.clip((positive.max()/max(np.sqrt(np.mean(positive**2)),1e-7)-1.4)/3,0,1)
        freq=np.arange(len(env))*rate/fft
        dist=np.abs(freq-np.maximum(1,np.round(freq/max(f0,1)))*f0)
        radius=max(2*rate/fft,.46*f0)
        weight=confidence*np.where(dist<radius,np.cos(.5*np.pi*dist/radius)**2,0)
        weight[0]=0
        gain_db=np.where(gain_db>0,gain_db*weight,gain_db)
    gain=np.exp(gain_db*np.log(10)/20)
    weights=magnitude**2;weights[1:-1]*=2
    energy=weights.sum()+1e-12
    gain*=np.exp(-np.sum(weights*np.log(np.maximum(gain,1e-12)))/energy)
    corrected=np.sum(weights*gain**2)+1e-12
    if corrected>energy:gain*=max(.25,np.sqrt(energy/corrected))
    return gain


def render(x,rate:int,time_ratio:float=1.,pitch_ratio:float=1.,cfg:Config=Config()):
    x=audio(x)
    if (rate not in (16000,22050,32000,44100,48000,88200,96000,192000) or
        not .5<=time_ratio<=2 or not .5<=pitch_ratio<=2 or
        cfg.formant not in ('off','harmonic','monophonic') or not .5<=cfg.formant_ratio<=2 or
        (cfg.formant=='off' and cfg.formant_ratio!=1) or
        not 64<=cfg.long_window<=8192 or cfg.long_window&(cfg.long_window-1) or
        not 1<=cfg.hop<=cfg.long_window//4 or not 0<cfg.mpd_tolerance<1 or
        not 0<cfg.magnitude_floor<1 or not 0<cfg.prominence<1):
        raise ValueError('invalid NSGT configuration')
    alpha=time_ratio*pitch_ratio
    target=int(np.floor(len(x)*time_ratio+.5));intermediate=int(np.floor(len(x)*alpha+.5))
    if not len(x):return np.zeros((0,x.shape[1])),dict(frames=0,detected_events=0)
    # A nonempty one-sample input can round to zero at time*pitch=.25.
    # Keep one intermediate sample; this is an explicit discrete-length edge rule.
    intermediate=max(1,intermediate)
    scale=1
    while rate>48000*scale:scale*=2
    longest=cfg.long_window*scale;fft=longest*2;hop0=cfg.hop*scale
    # Contraction is a fixed-window extension, not published SELEBI behavior.
    if cfg.adapt and alpha>1:
        onset,strength,_,_=percussion(x,rate,fft,longest,hop0,cfg)
    else:onset=np.array([],dtype=int);strength=np.array([])
    minima=np.floor(longest-strength**2*(1-1/alpha)*longest).astype(int) if len(onset) else np.array([],int)
    minima=np.maximum(64*scale,2*(minima//2))
    out=np.zeros((intermediate+fft*2,x.shape[1]));weight=np.zeros(len(out))
    omega=np.arange(fft//2+1)*2*np.pi/fft
    oldphase=None;rotation=np.zeros(len(omega));old_t=old_s=0
    chindex=np.arange(len(omega));frames=0;shortest=longest;lengths=[];t=0
    while t<=len(x)+longest//2:
        length=longest
        if len(onset):length=int(min(longest,np.min(np.maximum(minima,2*np.abs(onset-t)))))
        length=max(4,2*(length//2));shortest=min(shortest,length)
        w=window(length,fft);z=frame(x,t,fft,w)
        mag=np.abs(z);phase=np.angle(z)
        linked=np.sqrt(np.mean(mag**2,axis=1))
        refs=np.argmax(mag,axis=1);own=owners(linked)
        synth=int(np.floor(t*alpha+.5))
        if oldphase is not None:
            da=t-old_t;ds=synth-old_s
            residual=wrap(phase[chindex,refs]-oldphase[chindex,refs]-omega*da)
            instantaneous=omega+residual/da
            predicted=wrap(rotation+(ds-da)*instantaneous)
            rotation=predicted[own]
        gain=formant_gain(linked,rate,fft,pitch_ratio,cfg)
        zout=mag*gain[:,None]*np.exp(1j*(phase+rotation[:,None]))
        y=np.fft.fftshift(np.fft.irfft(zout,n=fft,axis=0),axes=0)*w[:,None]
        lo=synth+fft//2;hi=min(lo+fft,len(out))
        if hi>lo:
            out[lo:hi]+=y[:hi-lo];weight[lo:hi]+=(w*w)[:hi-lo]
        oldphase=phase;old_t=t;old_s=synth;frames+=1;lengths.append(length)
        t+=max(1,min(hop0,int(np.floor(length/(4*max(alpha,1))))))
    cropped=out[fft:fft+intermediate];den=weight[fft:fft+intermediate]
    if not len(den) or np.min(den)<1e-8:raise ValueError('NSGT synthesis coverage hole')
    cropped/=den[:,None]
    result=signal.resample(cropped,target,axis=0) if target!=intermediate else cropped
    if not np.isfinite(result).all():raise ValueError('nonfinite NSGT output')
    return result,dict(frames=frames,detected_events=len(onset),min_window=shortest,max_window=longest,
        fft=fft,min_weight=float(den.min()),event_samples=onset.tolist(),event_strength=strength.tolist(),
        adapted_frames=sum(n<longest for n in lengths),intermediate_frames=intermediate,
        output_frames=target,offline=True,algorithm='selective NSGT adaptation, not exact SELEBI')


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('input',type=Path);p.add_argument('output',type=Path)
    p.add_argument('--time',type=float,default=1);p.add_argument('--pitch',type=float,default=1)
    p.add_argument('--fixed',action='store_true');p.add_argument('--formant',choices=('off','harmonic','monophonic'),default='off')
    p.add_argument('--formant-ratio',type=float,default=1);p.add_argument('--receipt',type=Path)
    a=p.parse_args();x,sr=sf.read(a.input,always_2d=True)
    if a.output.exists():raise ValueError('refuse overwrite')
    y,meta=render(x,sr,a.time,a.pitch,Config(adapt=not a.fixed,formant=a.formant,formant_ratio=a.formant_ratio))
    sf.write(a.output,y,sr,subtype='FLOAT')
    if a.receipt:a.receipt.write_text(json.dumps(meta,indent=2,allow_nan=False)+'\n')
if __name__=='__main__':main()
