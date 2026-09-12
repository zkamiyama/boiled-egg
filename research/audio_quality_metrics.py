"""Transparent pitch-shift diagnostics; NOT MOS, PESQ, or perceptual rankings.

All analysis uses float64 and channel power, never a canceling mono downmix.
Spectral flatness = geometric/arithmetic power mean. Welch/CSD definitions:
https://docs.scipy.org/doc/scipy/reference/generated/scipy.signal.welch.html
https://docs.scipy.org/doc/scipy/reference/generated/scipy.signal.coherence.html
Numerical log floor: -120 dB relative POWER. Silence is invalid, not a good score.
"""
from __future__ import annotations
import numpy as np
from scipy import signal

FLOOR = 1e-12


def audio(x: np.ndarray) -> np.ndarray:
    x = np.asarray(x, dtype=np.float64)
    if x.ndim == 1:
        x = x[:, None]
    if x.ndim != 2 or min(x.shape) < 1 or not np.isfinite(x).all():
        raise ValueError('nonempty finite frames-by-channels audio required')
    return x


def power(x: np.ndarray) -> np.ndarray:
    return np.mean(audio(x)**2, axis=1)


def positive(value: float) -> float:
    if not np.isfinite(value) or value <= 1e-24:
        raise ValueError('metric undefined for silence/vanishing power')
    return value


def db(value: np.ndarray | float) -> np.ndarray:
    return 10*np.log10(np.maximum(value, FLOOR))


def paired(x: np.ndarray, y: np.ndarray, rate: int) -> tuple[np.ndarray, np.ndarray]:
    x, y = audio(x), audio(y)
    if x.shape != y.shape or not isinstance(rate, (int, np.integer)) or rate < 8000:
        raise ValueError('equal shapes and valid sample rate required')
    positive(float(np.sum(x*x))); positive(float(np.sum(y*y)))
    return x, y


def temporal(x: np.ndarray, y: np.ndarray, rate: int) -> dict:
    """Unaligned time diagnostics. Not an ideal-output error on natural music.

    Transport is W1 between normalized 1-ms channel-power bins. 10-ms RMS shape
    error removes one global level per signal; evaluates source bins above -40 dB
    of its maximum; the logarithm has a -120 dB relative-power floor. No time warp.
    """
    x, y = paired(x, y, rate)
    p, q = power(x), power(y)
    result = {}
    for ms in (1, 10):
        n = max(1, round(rate*ms/1000))
        # Keep the trailing partial bin: zero padding preserves its energy.
        length = ((len(p)+n-1)//n)*n
        a = np.pad(p, (0, length-len(p))).reshape(-1, n).sum(axis=1)
        b = np.pad(q, (0, length-len(q))).reshape(-1, n).sum(axis=1)
        a /= positive(float(a.sum())); b /= positive(float(b.sum()))
        if ms == 1:
            result['energy_transport_ms'] = float(np.sum(np.abs(np.cumsum(a-b)))*1000*n/rate)
        else:
            mask = a > a.max()*1e-4
            result['rms_shape_error_db'] = float(np.sqrt(np.mean((db(a[mask])-db(b[mask]))**2)))
            result['active_bins'] = int(mask.sum())
    result['rms_gain_db'] = float(db(np.mean(q)/np.mean(p)))
    result['peak'] = float(np.max(np.abs(y)))
    # This is an explicitly specified FIR oversampling estimate, NOT BS.1770.
    up = signal.resample_poly(y, 4, 1, axis=0, window=('kaiser', 8.6))
    result['peak_4x_estimate'] = float(np.max(np.abs(up)))
    return result


def attacks(x: np.ndarray, rate: int, starts: list[float], duration: float) -> dict:
    """Energy quantiles around known synthetic gates, with no alignment search."""
    p = power(x)
    if not starts or duration <= 0 or duration >= .1:
        raise ValueError('valid isolated attack gates required')
    values = []
    for start in starts:
        a, b = round((start-.1)*rate), round((start+duration+.1)*rate)
        if a < 0 or b > len(p):
            raise ValueError('attack window outside signal')
        local = p[a:b]
        total = positive(float(local.sum()))
        cdf = np.cumsum(local)/total
        times = np.arange(a, b)/rate
        quantiles = np.interp([.05, .95], cdf, times)
        center = np.sum(times*local)/total
        values.append((1000*(quantiles[1]-quantiles[0]),
            100*np.sum(local[times < start])/total,
            100*np.sum(local[times >= start+duration])/total,
            1000*(center-(start+duration/2)),
            100*np.sum(local[times < center-duration/2])/total,
            100*np.sum(local[times >= center+duration/2])/total))
    v = np.asarray(values)
    return dict(attack_width_ms=float(v[:,0].mean()), pre_energy_pct=float(v[:,1].mean()),
                post_energy_pct=float(v[:,2].mean()), centroid_bias_ms=float(v[:,3].mean()),
                centered_pre_energy_pct=float(v[:,4].mean()), centered_post_energy_pct=float(v[:,5].mean()))


def spectrum(x: np.ndarray, rate: int) -> tuple[np.ndarray, np.ndarray]:
    x = audio(x)
    if len(x) < rate:
        raise ValueError('at least 1 second required for steady-spectrum diagnostics')
    x = x[rate//4:-rate//4]
    nfft = 1 << int(np.ceil(np.log2(len(x)*4)))
    z = np.fft.rfft(x*signal.windows.hann(len(x), sym=False)[:,None], n=nfft, axis=0)
    return np.fft.rfftfreq(nfft, 1/rate), np.mean(np.abs(z)**2, axis=1)


def partials(x: np.ndarray, oracle: np.ndarray, rate: int, frequencies: np.ndarray) -> dict:
    """Known partials within +/-4 Hz; spectral floor -120 dB; oracle -40 dB mask.

    Envelope error compares normalized partial powers, not sample phases. Leakage
    is power outside the union of those bands / total; lower (more negative) better.
    No extra distortion SNR label is applied to this finite-window diagnostic.
    """
    paired(x, oracle, rate)
    f, p = spectrum(x, rate); _, q = spectrum(oracle, rate)
    frequencies = np.asarray(frequencies, dtype=float)
    if (not len(frequencies) or not np.isfinite(frequencies).all() or
        np.min(frequencies) <= 4 or np.max(frequencies) >= rate/2-4 or
        (len(frequencies) > 1 and np.min(np.diff(np.sort(frequencies))) <= 8)):
        raise ValueError('non-overlapping in-band partial frequencies required')
    union = np.zeros(len(f), dtype=bool)
    a, b = [], []
    for freq in frequencies:
        lo, hi = np.searchsorted(f, [freq-4, freq+4], side='left')
        union[lo:hi] = True
        a.append(p[lo:hi].sum()); b.append(q[lo:hi].sum())
    a, b = np.asarray(a), np.asarray(b)
    a /= positive(float(a.sum())); b /= positive(float(b.sum()))
    valid = b > b.max()*1e-4
    return dict(partial_envelope_error_db=float(np.sqrt(np.mean((db(a[valid])-db(b[valid]))**2))),
        off_partial_energy_db=float(db(p[~union].sum()/positive(float(p.sum())))),
        oracle_off_partial_energy_db=float(db(q[~union].sum()/positive(float(q.sum())))),
        analyzed_partials=int(valid.sum()))


def noise(x: np.ndarray, rate: int, band: tuple[float, float]) -> dict:
    """Stationary-noise texture: 2-40ms autocorrelation, PSD flatness, 10ms CV.

    The ideal is a same-band stochastic control, NOT zero envelope modulation.
    Crop 250ms at each edge. Whiteness within a band is not a music-quality score.
    """
    x = audio(x)
    if len(x) < rate or not 0 < band[0] < band[1] < rate/2:
        raise ValueError('long noise signal and valid band required')
    x = x[rate//4:-rate//4]
    n = round(rate*.04)
    f, psd = signal.welch(x, rate, window='hann', nperseg=n, noverlap=n//2,
                         detrend=False, axis=0)
    psd = psd.mean(axis=1)
    selected = psd[(f >= band[0]) & (f <= band[1])]
    selected /= positive(float(selected.mean()))
    flat = float(np.exp(np.mean(np.log(np.maximum(selected, FLOOR)))))
    centered = x-x.mean(axis=0)
    signal_len = 1 << int(np.ceil(np.log2(2*len(x))))
    fft = np.fft.rfft(centered, n=signal_len, axis=0)
    ac = np.fft.irfft(np.abs(fft)**2, n=signal_len, axis=0).sum(axis=1)[:len(x)]
    ac /= positive(float(ac[0]))
    lag = float(np.max(np.abs(ac[round(.002*rate):round(.04*rate)+1])))
    step = round(.01*rate)
    rms = np.sqrt(power(x[:len(x)//step*step]).reshape(-1,step).mean(axis=1))
    return dict(noise_flatness=flat, noise_lag_peak=lag,
                noise_rms_cv=float(rms.std()/positive(float(rms.mean()))))


def stereo(x: np.ndarray, rate: int, band: tuple[float, float]) -> dict:
    """Statistical stereo image for stationary correlated-noise fixtures only."""
    x = audio(x)
    if x.shape[1] != 2 or len(x) < rate or not 0 < band[0] < band[1] < rate/2:
        raise ValueError('long stereo signal and valid band required')
    x = x[rate//4:-rate//4]
    l, r = x.T
    pl, pr = positive(float(np.mean(l*l))), positive(float(np.mean(r*r)))
    n = round(.04*rate)
    kwargs = dict(fs=rate, window='hann', nperseg=n, noverlap=n//2, detrend=False)
    f, ll = signal.welch(l, **kwargs); _, rr = signal.welch(r, **kwargs)
    _, lr = signal.csd(l, r, **kwargs)
    mask = (f >= band[0]) & (f <= band[1]) & (ll*rr > float(ll.max()*rr.max())*FLOOR)
    if not mask.any():
        raise ValueError('no stereo energy in measurement band')
    coherence = np.abs(lr[mask])**2/(ll[mask]*rr[mask])
    return dict(lr_correlation=float(np.corrcoef(l,r)[0,1]),
                coherence=float(np.mean(coherence)), ild_db=float(db(pr/pl)))
