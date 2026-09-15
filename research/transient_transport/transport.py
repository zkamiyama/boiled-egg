"""Offline complementary HP separation and percussive grain time transport.

Independent adaptation of the long-PV/short-OLA idea of Driedger et al. (2014).
Anchored grain mapping is an experimental ablation, not SELEBI reproduction.
Only constant TSM/pitch=1; no formants, automatic product profile or RT claim.
"""
from pathlib import Path
import importlib.util
import numpy as np
from scipy import ndimage, signal

_spec = importlib.util.spec_from_file_location('transport_legacy_pv', Path(__file__).parents[1]/'phase_gradient/experiment.py')
base = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(base)
MODES = ('locked', 'heap', 'split_heap_long', 'split_locked_ola', 'split_heap_ola', 'split_heap_anchor')


def audio(x):
    x = np.asarray(x, dtype=np.float64)
    if x.ndim == 1:
        x = x[:, None]
    if x.ndim != 2 or not 1 <= x.shape[1] <= 8 or not np.isfinite(x).all():
        raise ValueError('finite mono/planar multichannel signal required')
    return x


def separate(x, rate):
    """Shared power mask; p=x-h enforces complementary time-domain synthesis."""
    x = audio(x)
    if rate not in (44100, 48000, 96000):
        raise ValueError('unsupported research sample rate')
    if not len(x):
        return x.copy(), x.copy(), dict(separation_residual=0., percussive_energy_fraction=0.)
    n = 2048 * (2 if rate == 96000 else 1)
    hop = n//8
    window = signal.windows.hann(n, sym=False)
    centers = np.arange(0, len(x)+n//2+hop, hop)
    padded = np.pad(x, ((n//2,2*n), (0,0)))
    z = np.array([np.fft.rfft(padded[t:t+n]*window[:,None], axis=0) for t in centers])
    magnitude = np.sqrt(np.mean(abs(z)**2, axis=2))
    horizontal = ndimage.median_filter(magnitude, size=(31,1), mode='nearest')
    vertical = ndimage.median_filter(magnitude, size=(1,31), mode='nearest')
    denominator = horizontal**2 + vertical**2
    mask = np.divide(horizontal**2, denominator, out=np.full_like(denominator,.5), where=denominator>0)
    harmonic = np.zeros_like(padded)
    weight = np.zeros(len(padded))
    for i,t in enumerate(centers):
        frame = np.fft.irfft(z[i]*mask[i,:,None], n=n, axis=0)
        harmonic[t:t+n] += frame*window[:,None]
        weight[t:t+n] += window**2
    den = weight[n//2:n//2+len(x)]
    if den.min() <= 1e-12:
        raise ValueError('separation coverage hole')
    harmonic = harmonic[n//2:n//2+len(x)]/den[:,None]
    percussive = x-harmonic
    return harmonic, percussive, dict(
        separation_residual=float(abs(harmonic+percussive-x).max()),
        percussive_energy_fraction=float(np.sum(percussive**2)/max(np.sum(x**2),1e-30)))


def detect_anchors(percussive, rate):
    """Input-derived energy peaks only; no oracle or output-dependent tuning."""
    x = audio(percussive)
    if not len(x):
        return np.empty(0, dtype=np.float64)
    step = max(1, round(rate*.001))
    power = np.mean(x*x, axis=1)
    envelope = ndimage.uniform_filter1d(power, size=step, mode='constant')[::step]
    maximum = float(envelope.max())
    if maximum <= 1e-24:
        return np.empty(0, dtype=np.float64)
    floor = ndimage.median_filter(envelope, size=51, mode='nearest')
    peaks,_ = signal.find_peaks(envelope, distance=max(1,round(.04*rate/step)), prominence=.05*maximum)
    peaks = peaks[envelope[peaks] > 4*floor[peaks]]
    return (peaks*step).astype(np.float64)


def anchor_knots(length, ratio, anchors, rate):
    """Return strictly monotone output->input knots, locally unit slope.

    Every anchor maps (ratio*u,u). Protected intervals are non-overlapping and
    leave strictly positive joins even for compression. Endpoint positions exact.
    """
    anchors = np.asarray(anchors, dtype=np.float64)
    if (length<=0 or not np.isfinite(ratio) or not .5<=ratio<=2 or anchors.ndim!=1
            or not np.isfinite(anchors).all() or np.any(np.diff(anchors)<=0)
            or np.any(anchors<=0) or np.any(anchors>=length)):
        raise ValueError('invalid anchor map')
    out,src = [0.], [0.]
    edges = np.r_[0.,anchors,float(length)]
    for i,u in enumerate(anchors):
        radius = min(.012*rate, .2*min(u-edges[i],edges[i+2]-u)*min(1.,ratio))
        for delta in (-radius, 0., radius):
            out.append(ratio*u+delta)
            src.append(u+delta)
    out.append(ratio*length)
    src.append(float(length))
    return np.asarray(out), np.asarray(src)


def map_positions(positions, out_knots, in_knots):
    """Piecewise linear reference (linear extrapolation at endpoints)."""
    positions = np.asarray(positions, dtype=np.float64)
    if (positions.ndim!=1 or not np.isfinite(positions).all()
            or len(out_knots)<2 or len(out_knots)!=len(in_knots)
            or not np.isfinite(out_knots).all() or not np.isfinite(in_knots).all()
            or np.any(np.diff(out_knots)<=0) or np.any(np.diff(in_knots)<=0)):
        raise ValueError('invalid interpolation coordinates')
    j = np.clip(np.searchsorted(out_knots, positions, side='right')-1, 0, len(out_knots)-2)
    return in_knots[j]+(positions-out_knots[j])*(in_knots[j+1]-in_knots[j])/(out_knots[j+1]-out_knots[j])


def ola(percussive, rate, ratio, anchored=False, mapper=None):
    x = audio(percussive)
    target = int(np.floor(len(x)*ratio+.5))
    if not len(x):
        return np.zeros((target,x.shape[1])), dict(anchors=0, grain_frames=0, min_weight=0.)
    win = 256*(2 if rate==96000 else 1)
    hop = win//4
    w = signal.windows.hann(win, sym=False)**2
    synth = np.arange(0,target+win//2+hop,hop)
    anchors = detect_anchors(x,rate) if anchored else np.empty(0)
    out,src = anchor_knots(len(x),ratio,anchors,rate)
    continuous = (mapper or map_positions)(synth,out,src)
    centers = np.floor(continuous+.5).astype(np.int64)
    y = np.zeros((target+2*win,x.shape[1]))
    den = np.zeros(len(y))
    for s,c in zip(synth,centers):
        a,b = max(0,c-win//2),min(len(x),c+win//2)
        frame = np.zeros((win,x.shape[1]))
        if b>a:
            frame[a-c+win//2:b-c+win//2] = x[a:b]
        y[s:s+win] += frame*w[:,None]
        den[s:s+win] += w
    weights = den[win//2:win//2+target]
    if target and weights.min()<=1e-12:
        raise ValueError('OLA coverage hole')
    result = y[win//2:win//2+target]/weights[:,None]
    return result, dict(anchors=len(anchors),grain_frames=len(synth),min_weight=float(weights.min()) if target else 0.)


def render(x, rate, ratio=1., mode='split_heap_ola', kernel=None, mapper=None):
    x = audio(x)
    if (mode not in MODES or rate not in (44100,48000,96000)
            or not np.isfinite(ratio) or not .5<=ratio<=2):
        raise ValueError('invalid research controls')
    if mode in ('locked','heap'):
        return base.render(x,rate,time=ratio,mode=mode,kernel_path=kernel)
    h,p,stats = separate(x,rate)
    hm = 'locked' if mode=='split_locked_ola' else 'heap'
    hy,hs = base.render(h,rate,time=ratio,mode=hm,kernel_path=kernel)
    if mode=='split_heap_long':
        py,ps = base.render(p,rate,time=ratio,mode='heap',kernel_path=kernel)
    else:
        py,ps = ola(p,rate,ratio,mode=='split_heap_anchor',mapper)
    y = hy+py
    if not np.isfinite(y).all():
        raise ValueError('nonfinite reconstruction')
    return y, dict(stats, **{'h_'+k:v for k,v in hs.items()}, **{'p_'+k:v for k,v in ps.items()})
