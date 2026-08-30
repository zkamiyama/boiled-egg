#!/usr/bin/env python3
"""Independent offline phase-vocoder research prototype for boiled egg.

This Python/Numpy implementation validates algorithm choices before a realtime
C++ port. It is not linked into the product library.
"""
from __future__ import annotations

import argparse
import dataclasses
import math
from pathlib import Path

import numpy as np
import soundfile as sf
from scipy import signal

EPS = 1.0e-12


@dataclasses.dataclass(frozen=True)
class PVConfig:
    fft_size: int = 2048
    analysis_hop: int = 256
    phase_locking: bool = True
    transient_reset: bool = True
    peak_floor_db: float = -55.0
    transient_floor: float = 0.12
    transient_sigma: float = 2.5


def wrap_phase(x: np.ndarray) -> np.ndarray:
    return (x + np.pi) % (2.0 * np.pi) - np.pi


def peak_owners(magnitude: np.ndarray, floor_db: float) -> tuple[np.ndarray, np.ndarray]:
    bins = len(magnitude)
    if bins < 3:
        peaks = np.array([int(np.argmax(magnitude))], dtype=np.int64)
    else:
        threshold = float(np.max(magnitude)) * (10.0 ** (floor_db / 20.0))
        local = (magnitude[1:-1] >= magnitude[:-2]) & (magnitude[1:-1] > magnitude[2:]) & (magnitude[1:-1] >= threshold)
        peaks = np.flatnonzero(local) + 1
        if magnitude[0] > magnitude[1] and magnitude[0] >= threshold: peaks = np.r_[0, peaks]
        if magnitude[-1] >= magnitude[-2] and magnitude[-1] >= threshold: peaks = np.r_[peaks, bins - 1]
        if len(peaks) == 0: peaks = np.array([int(np.argmax(magnitude))], dtype=np.int64)
    owners = np.empty(bins, dtype=np.int64)
    boundaries = ((peaks[:-1] + peaks[1:]) // 2) if len(peaks) > 1 else np.array([], dtype=np.int64)
    start = 0
    for idx, peak in enumerate(peaks):
        stop = int(boundaries[idx] + 1) if idx < len(boundaries) else bins
        owners[start:stop] = peak; start = stop
    return peaks, owners


def _transient_mask(audio: np.ndarray, ratio: float, sr: int) -> np.ndarray:
    mono = np.mean(audio, axis=1); n_fft = 1024; hop = 128
    _, _, z = signal.stft(mono, fs=sr, window="hann", nperseg=n_fft, noverlap=n_fft-hop, boundary="zeros", padded=True)
    mag = np.abs(z); flux = np.mean(np.maximum(0.0, np.diff(np.log1p(20.0*mag), axis=1)), axis=0)
    kernel_size = min(9, len(flux) if len(flux) % 2 else max(1, len(flux)-1)); kernel_size = max(1, kernel_size)
    med = signal.medfilt(flux, kernel_size=kernel_size); score = np.maximum(0.0, flux-med)
    score = np.clip(score/(np.quantile(score,0.85)+EPS),0.0,1.0)
    kernel = np.r_[np.linspace(0.1,1.0,4,endpoint=False), np.exp(-np.arange(22)/7.0)]
    expanded = np.clip(np.convolve(score,kernel,mode="same"),0.0,1.0)
    output_len = max(1,round(len(audio)*ratio)); normalized_input = np.arange(output_len)/max(ratio,EPS)
    return np.interp(normalized_input,np.arange(len(expanded))*hop,expanded,left=0.0,right=0.0)


def phase_vocoder(audio: np.ndarray, ratio: float, config: PVConfig) -> np.ndarray:
    if ratio <= 0.0 or not math.isfinite(ratio): raise ValueError("ratio must be positive and finite")
    if audio.ndim == 1: audio = audio[:,None]
    x = np.asarray(audio,dtype=np.float64); frames_in,channels = x.shape
    n_fft = int(config.fft_size); ha = int(config.analysis_hop)
    if n_fft < 64 or n_fft & (n_fft-1): raise ValueError("fft_size must be a power of two")
    if ha <= 0 or ha > n_fft//2: raise ValueError("analysis_hop must be in (0, fft_size/2]")
    window = np.sqrt(signal.windows.hann(n_fft,sym=False)); pad=n_fft//2
    padded=np.pad(x,((pad,pad+n_fft),(0,0)))
    analysis_starts=np.arange(0,max(1,len(padded)-n_fft+1),ha,dtype=np.int64)
    synthesis_starts=np.rint(np.arange(len(analysis_starts))*(ratio*ha)).astype(np.int64)
    wanted=max(1,int(round(frames_in*ratio)))
    output=np.zeros((int(synthesis_starts[-1])+n_fft+pad+4,channels),dtype=np.float64); weight=np.zeros(len(output),dtype=np.float64)
    omega=2.0*np.pi*np.arange(n_fft//2+1)/n_fft
    previous_analysis=np.zeros((channels,n_fft//2+1)); previous_output=np.zeros_like(previous_analysis)
    previous_magnitude=np.zeros(n_fft//2+1); flux_mean=0.0; flux_var=0.0; initialized=False; previous_out_start=0
    for a_start,s_start in zip(analysis_starts,synthesis_starts):
        frame=padded[a_start:a_start+n_fft]*window[:,None]; spectrum=np.fft.rfft(frame,axis=0).T
        magnitude=np.abs(spectrum); phase=np.angle(spectrum); linked_magnitude=np.sqrt(np.mean(np.square(magnitude),axis=0)+EPS)
        peaks,owners=peak_owners(linked_magnitude,config.peak_floor_db)
        if initialized:
            flux=float(np.sum(np.maximum(0.0,linked_magnitude-previous_magnitude))/(np.sum(previous_magnitude)+EPS))
            sigma=math.sqrt(max(flux_var,0.0)); is_transient=config.transient_reset and flux>config.transient_floor and flux>flux_mean+config.transient_sigma*sigma
            delta=wrap_phase(phase-previous_analysis-omega[None,:]*ha); inst=omega[None,:]+delta/ha
            propagated=previous_output+inst*int(s_start-previous_out_start)
        else:
            flux=0.0; is_transient=True; propagated=phase.copy()
        if is_transient:
            output_phase=phase+omega[None,:]*float(s_start-a_start)
        elif config.phase_locking:
            owner_index=np.searchsorted(peaks,owners); output_phase=np.empty_like(phase)
            for channel in range(channels):
                output_phase[channel]=propagated[channel,peaks][owner_index]+wrap_phase(phase[channel]-phase[channel,owners])
        else:
            output_phase=propagated
        out_spectrum=magnitude*np.exp(1j*output_phase); out_frame=np.fft.irfft(out_spectrum.T,n=n_fft,axis=0).real*window[:,None]
        output[s_start:s_start+n_fft]+=out_frame; weight[s_start:s_start+n_fft]+=window*window
        if initialized:
            alpha=0.04; diff=flux-flux_mean; flux_mean+=alpha*diff; flux_var=(1.0-alpha)*(flux_var+alpha*diff*diff)
        else:
            flux_mean=flux; flux_var=0.0; initialized=True
        previous_analysis=phase; previous_output=output_phase; previous_magnitude=linked_magnitude; previous_out_start=int(s_start)
    output/=np.maximum(weight[:,None],1.0e-8); start=int(round(pad*ratio)); y=output[start:start+wanted]
    if len(y)<wanted: y=np.pad(y,((0,wanted-len(y)),(0,0)))
    y[~np.isfinite(y)]=0.0; return y.astype(np.float32)


def adaptive_multiresolution(audio: np.ndarray, ratio: float, sr: int) -> np.ndarray:
    long=phase_vocoder(audio,ratio,PVConfig(fft_size=4096,analysis_hop=256,phase_locking=True,transient_reset=True))
    short=phase_vocoder(audio,ratio,PVConfig(fft_size=1024,analysis_hop=128,phase_locking=True,transient_reset=True))
    mask=_transient_mask(audio,ratio,sr); smoothing=max(3,int(sr*0.004)|1)
    if len(mask)>=smoothing: mask=signal.savgol_filter(mask,smoothing,2,mode="interp")
    mask=np.clip(mask,0.0,1.0)[:,None]; return (long*(1.0-mask)+short*mask).astype(np.float32)


def process(audio: np.ndarray, sr: int, ratio: float, mode: str) -> np.ndarray:
    if mode=="classic": return phase_vocoder(audio,ratio,PVConfig(phase_locking=False,transient_reset=False))
    if mode=="locked": return phase_vocoder(audio,ratio,PVConfig(phase_locking=True,transient_reset=False))
    if mode=="transient": return phase_vocoder(audio,ratio,PVConfig(phase_locking=True,transient_reset=True))
    if mode=="adaptive": return adaptive_multiresolution(audio,ratio,sr)
    raise ValueError(f"unknown mode: {mode}")


def main() -> None:
    parser=argparse.ArgumentParser(); parser.add_argument("input",type=Path); parser.add_argument("output",type=Path)
    parser.add_argument("--time",type=float,required=True); parser.add_argument("--mode",choices=("classic","locked","transient","adaptive"),default="transient")
    args=parser.parse_args(); audio,sr=sf.read(args.input,always_2d=True,dtype="float32"); output=process(audio,sr,args.time,args.mode)
    args.output.parent.mkdir(parents=True,exist_ok=True); sf.write(args.output,output,sr,subtype="FLOAT")


if __name__=="__main__": main()
