"""Offline alternating STFT/shared-channel-phase projections, fixed iteration count.

A reconstruction ablation, not output-envelope EQ. Project onto spectra of the
form source_coefficients * exp(j*one_rotation_per_bin), preserving interchannel
ratios/phases and magnitudes at that projection. Synthesis may still differ from
target magnitudes because the target is generally not STFT-consistent.
"""
import numpy as np


def synthesize(coeff, starts, window, length):
    n=len(window);audio=np.zeros((length,coeff.shape[2]));weight=np.zeros(length)
    for z,start in zip(coeff,starts):
        frame=np.fft.fftshift(np.fft.irfft(z,n=n,axis=0),axes=0)*window[:,None]
        lo=int(start)+n//2
        audio[lo:lo+n]+=frame;weight[lo:lo+n]+=window*window
    covered=weight>1e-15
    audio[covered]/=weight[covered,None]
    return audio


def analyze(audio,starts,window):
    n=len(window)
    return np.array([np.fft.rfft(np.fft.ifftshift(audio[int(t)+n//2:int(t)+3*n//2]*window[:,None],axes=0),axis=0) for t in starts])


def shared_phase_projection(target,estimate,previous):
    cross=np.sum(np.conj(target)*estimate,axis=2)
    rotation=np.ones_like(cross)
    valid=np.abs(cross)>0
    rotation[valid]=cross[valid]/np.abs(cross[valid])
    # If both channels cancel in the inner product, all angles tie: keep the
    # previous feasible point instead of choosing a new arbitrary phase.
    projected=target*rotation[:,:,None]
    projected[~valid]=previous[~valid]
    return projected


def refine(target,initial,starts,window,length,iterations):
    if (not isinstance(iterations,int) or not 0<=iterations<=16 or target.shape!=initial.shape or
        target.ndim!=3 or target.shape[1]!=len(window)//2+1 or len(starts)!=len(target) or
        not np.isfinite(target).all() or not np.isfinite(initial).all()):
        raise ValueError('invalid consistency projection dimensions/iterations')
    coeff=initial.copy();errors=[]
    symmetry=np.full(coeff.shape[1],2.);symmetry[0]=symmetry[-1]=1.
    power=float(np.sum(abs(target)**2*symmetry[None,:,None]))
    for i in range(iterations+1):
        audio=synthesize(coeff,starts,window,length)
        estimated=analyze(audio,starts,window)
        error=float(np.sum(abs(coeff-estimated)**2*symmetry[None,:,None])/max(power,1e-30))
        errors.append(error)
        if i<iterations:coeff=shared_phase_projection(target,estimated,coeff)
    return audio,errors
