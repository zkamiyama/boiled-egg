"""Analytical envelope-preservation checks, not a perceptual or natural-voice model.

No analyzed waveform is normalized, aligned, or modified. Relative contour error
removes one scalar from the METRIC; absolute gain and out-of-harmonic energy are
reported separately. Fixture/ideal construction does not import the tested DSP.
"""
from __future__ import annotations
import math
import numpy as np

CONTOURS = {
    'open': ((650., 110., 1.), (1250., 180., .8), (2500., 260., .6)),
    'closed': ((300., 90., 1.), (2200., 220., .75), (3100., 290., .5)),
}
FUNDAMENTALS = (110., 220.)
SHIFTS = (-12, -7, -3, 3, 7, 12)


def envelope(frequencies: np.ndarray, contour: str) -> np.ndarray:
    if contour not in CONTOURS:
        raise ValueError('unknown analytical contour')
    f = np.asarray(frequencies, dtype=np.float64)
    return .04 + sum(a * np.exp(-.5 * ((f - center) / width) ** 2)
                     for center, width, a in CONTOURS[contour])


def specification(rate: int, f0: float, contour: str, pitch: float = 1.,
                  preserved: bool = False) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    if (rate not in (48000, 96000) or f0 not in FUNDAMENTALS
            or not math.isfinite(pitch) or not .5 <= pitch <= 2.):
        raise ValueError('analytical grid controls')
    k = np.arange(1, math.floor(8000 / f0) + 1, dtype=np.float64)
    frequencies = k * f0 * pitch
    amplitudes = envelope(k * f0 * (pitch if preserved else 1.), contour) / np.sqrt(k)
    phases = .173 * k + .019 * k * k
    return frequencies, amplitudes, phases


def fixture(rate: int, f0: float, contour: str, pitch: float = 1.,
            preserved: bool = False) -> np.ndarray:
    frequencies, amplitudes, phases = specification(rate, f0, contour, pitch, preserved)
    # This fixed gain is derived from the ORIGINAL analytical coefficients only;
    # ideal outputs keep it, even if preservation changes their total energy.
    _, original, _ = specification(rate, f0, contour)
    gain = .1 / np.sqrt(.5 * np.sum(original * original))
    time = np.arange(2 * rate, dtype=np.float64) / rate
    x = np.zeros(len(time), dtype=np.float64)
    for frequency, amplitude, phase in zip(frequencies, amplitudes, phases):
        x += gain * amplitude * np.sin(2 * np.pi * frequency * time + phase)
    return x.astype(np.float32)[:, None]


def band_amplitudes(audio: np.ndarray, rate: int, frequencies: np.ndarray) -> tuple[np.ndarray, float]:
    x = np.asarray(audio, dtype=np.float64)
    f = np.asarray(frequencies, dtype=np.float64)
    if (x.ndim != 2 or x.shape[1] != 1 or x.shape[0] != 2 * rate
            or not np.isfinite(x).all() or f.ndim != 1 or not len(f)
            or not np.isfinite(f).all() or np.any(f <= 0) or np.any(f >= rate / 2)
            or (len(f) > 1 and np.any(np.diff(f) <= 20))):
        raise ValueError('finite mono two-second waveform and separated frequencies required')
    # Prespecified steady interval, identical for all engines. No fitted latency.
    segment = x[rate // 4:7 * rate // 4, 0]
    window = np.hanning(len(segment))
    spectrum = np.fft.rfft(segment * window)
    power = np.abs(spectrum) ** 2
    bins = np.fft.rfftfreq(len(segment), 1 / rate)
    support = np.zeros(len(bins), dtype=bool)
    amounts = []
    for frequency in f:
        selected = np.abs(bins - frequency) <= 4.
        if np.any(support & selected) or not np.any(selected):
            raise ValueError('overlapping or empty harmonic support')
        support |= selected
        amounts.append(2 * np.sqrt(np.sum(power[selected]) / (len(segment) * np.sum(window * window))))
    total = float(np.sum(power))
    outside = float(np.sum(power[~support]) / max(total, 1e-30))
    return np.asarray(amounts), outside


def contour_error(observed: np.ndarray, expected: np.ndarray) -> tuple[float, float]:
    a, b = np.asarray(observed, float), np.asarray(expected, float)
    if (a.shape != b.shape or a.ndim != 1 or not len(a) or not np.isfinite(a).all()
            or not np.isfinite(b).all() or np.any(a < 0) or np.any(b <= 0)):
        raise ValueError('invalid nonnegative amplitudes')
    difference = 20 * np.log10(np.maximum(a, 1e-12) / b)
    gain = float(np.mean(difference))
    return float(np.sqrt(np.mean((difference - gain) ** 2))), gain


def measure(audio: np.ndarray, rate: int, f0: float, contour: str,
            pitch: float, preserved: bool) -> dict:
    frequencies, target, _ = specification(rate, f0, contour, pitch, preserved)
    _, kept, _ = specification(rate, f0, contour, pitch, True)
    _, original, _ = specification(rate, f0, contour)
    scalar = .1 / np.sqrt(.5 * np.sum(original * original))
    selected = (frequencies >= 150.) & (frequencies <= 6000.)
    # Include all original harmonics for leakage measurement, not only the scored band.
    observed, leakage = band_amplitudes(audio, rate, frequencies)
    error, gain = contour_error(observed[selected], scalar * target[selected])
    retained, _ = contour_error(observed[selected], scalar * kept[selected])
    return dict(target_contour_rmse_db=error, retained_contour_rmse_db=retained,
                mean_partial_gain_db=gain, out_of_harmonic_power_fraction=leakage,
                evaluated_partials=int(np.count_nonzero(selected)), peak=float(np.max(np.abs(audio))),
                raw_rms=float(np.sqrt(np.mean(np.asarray(audio, float) ** 2))))
