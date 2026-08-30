#!/usr/bin/env python3
"""Independent offline formant-preserving pitch-shift prototypes.

These algorithms are research references only. They are deliberately kept out
of the realtime product core until objective/listening and realtime gates pass.

harmonic:
    linked-channel cepstral spectral-envelope preservation for harmonic and
    polyphonic material.
monophonic:
    framewise F0 estimation followed by harmonic-anchor envelope estimation,
    intended for voice and single-note instruments.
"""
from __future__ import annotations

import argparse
import math
from pathlib import Path

import numpy as np
import soundfile as sf
from scipy import signal

from pv_reference import PVConfig, phase_vocoder

EPS = 1.0e-10


def _linked_magnitude(spectrum: np.ndarray) -> np.ndarray:
    return np.sqrt(np.mean(np.square(np.abs(spectrum)), axis=0) + EPS)


def _cepstral_envelope(magnitude: np.ndarray, cutoff: int = 36) -> np.ndarray:
    bins = len(magnitude)
    n_fft = max(2, (bins - 1) * 2)
    logmag = np.log(np.maximum(magnitude, EPS))
    cep = np.fft.irfft(logmag, n=n_fft)
    cutoff = int(np.clip(cutoff, 4, max(4, n_fft // 4)))
    if cutoff + 1 < n_fft - cutoff:
        cep[cutoff + 1 : n_fft - cutoff] = 0.0
    return np.exp(np.fft.rfft(cep, n=n_fft).real)


def _estimate_f0(frame: np.ndarray, sr: int, fmin: float = 55.0, fmax: float = 1200.0) -> float | None:
    x = np.asarray(frame, dtype=np.float64)
    x = x - np.mean(x)
    energy = float(np.dot(x, x))
    if energy < 1.0e-9:
        return None
    x *= signal.windows.hann(len(x), sym=False)
    ac = signal.fftconvolve(x, x[::-1], mode="full")[len(x)-1:]
    if ac[0] <= EPS:
        return None
    ac /= ac[0]
    lag_min = max(1, int(sr / fmax))
    lag_max = min(len(ac) - 2, int(sr / fmin))
    if lag_max <= lag_min:
        return None
    segment = ac[lag_min:lag_max+1]
    peaks, props = signal.find_peaks(segment, height=0.20, distance=max(1, lag_min // 2))
    if len(peaks) == 0:
        lag = int(np.argmax(segment)) + lag_min
        if ac[lag] < 0.20:
            return None
    else:
        heights = props["peak_heights"]
        lag = int(peaks[int(np.argmax(heights))]) + lag_min
    if 1 <= lag < len(ac) - 1:
        y0, y1, y2 = ac[lag-1], ac[lag], ac[lag+1]
        denom = y0 - 2.0*y1 + y2
        if abs(denom) > 1.0e-9:
            lag = float(lag) + 0.5 * (y0 - y2) / denom
    return float(sr / lag) if lag > 0 else None


def _harmonic_envelope(magnitude: np.ndarray, sr: int, f0: float | None) -> np.ndarray:
    bins = len(magnitude)
    n_fft = max(2, (bins - 1) * 2)
    freqs = np.fft.rfftfreq(n_fft, 1.0 / sr)
    if f0 is None or not math.isfinite(f0) or f0 < 20.0:
        return _cepstral_envelope(magnitude, 32)

    harmonic_freqs = np.arange(f0, freqs[-1] + 0.5*f0, f0)
    if len(harmonic_freqs) < 3:
        return _cepstral_envelope(magnitude, 32)
    indices = np.clip(np.rint(harmonic_freqs / (sr / n_fft)).astype(int), 1, bins - 1)
    values = []
    anchors = []
    radius = max(1, int(round(f0 / (sr / n_fft) * 0.25)))
    for frequency, index in zip(harmonic_freqs, indices):
        lo = max(0, index - radius)
        hi = min(bins, index + radius + 1)
        peak = float(np.max(magnitude[lo:hi]))
        anchors.append(float(frequency))
        values.append(math.log(max(peak, EPS)))
    anchors = np.asarray(anchors)
    values = np.asarray(values)
    if len(values) >= 7:
        width = min(len(values) if len(values) % 2 else len(values)-1, 11)
        if width >= 5:
            values = signal.savgol_filter(values, width, 2, mode="interp")
    anchors = np.r_[0.0, anchors, freqs[-1]]
    values = np.r_[values[0], values, values[-1]]
    return np.exp(np.interp(freqs, anchors, values))


def _envelope_correct(
    original: np.ndarray,
    shifted: np.ndarray,
    sr: int,
    pitch_ratio: float,
    strategy: str,
    n_fft: int = 2048,
    hop: int = 256,
    max_gain_db: float = 18.0,
) -> np.ndarray:
    if original.ndim == 1:
        original = original[:, None]
    if shifted.ndim == 1:
        shifted = shifted[:, None]
    channels = shifted.shape[1]
    target = len(shifted)
    window = np.sqrt(signal.windows.hann(n_fft, sym=False))
    pad = n_fft // 2
    orig = np.pad(original.astype(np.float64), ((pad, pad+n_fft), (0, 0)))
    test = np.pad(shifted.astype(np.float64), ((pad, pad+n_fft), (0, 0)))
    output = np.zeros_like(test)
    weight = np.zeros(len(test), dtype=np.float64)

    limit = max(len(orig), len(test)) - n_fft + 1
    starts = range(0, max(1, limit), hop)
    max_log_gain = max_gain_db * math.log(10.0) / 20.0
    for start in starts:
        of = orig[start:start+n_fft]
        sf = test[start:start+n_fft]
        if len(of) < n_fft:
            of = np.pad(of, ((0, n_fft-len(of)), (0, 0)))
        if len(sf) < n_fft:
            sf = np.pad(sf, ((0, n_fft-len(sf)), (0, 0)))
        ospec = np.fft.rfft(of * window[:, None], axis=0).T
        sspec = np.fft.rfft(sf * window[:, None], axis=0).T
        omag = _linked_magnitude(ospec)
        smag = _linked_magnitude(sspec)

        if strategy == "harmonic":
            oenv = _cepstral_envelope(omag, 36)
            senv = _cepstral_envelope(smag, 36)
        elif strategy == "monophonic":
            mono = np.mean(of, axis=1)
            f0 = _estimate_f0(mono, sr)
            oenv = _harmonic_envelope(omag, sr, f0)
            senv = _harmonic_envelope(smag, sr, None if f0 is None else f0 * pitch_ratio)
        else:
            raise ValueError(f"unknown formant strategy: {strategy}")

        correction = np.log(np.maximum(oenv, EPS)) - np.log(np.maximum(senv, EPS))
        correction = np.clip(correction, -max_log_gain, max_log_gain)
        # Smooth the gain curve to prevent harmonic-bin noise from becoming EQ ripple.
        if len(correction) >= 17:
            correction = signal.savgol_filter(correction, 17, 2, mode="interp")
        gain = np.exp(correction)
        corrected = sspec * gain[None, :]
        frame = np.fft.irfft(corrected.T, n=n_fft, axis=0).real * window[:, None]
        stop = min(start + n_fft, len(output))
        n = stop - start
        output[start:stop] += frame[:n]
        weight[start:stop] += np.square(window[:n])

    output /= np.maximum(weight[:, None], 1.0e-8)
    result = output[pad:pad+target]
    result[~np.isfinite(result)] = 0.0
    return result.astype(np.float32)


def pitch_shift(audio: np.ndarray, sr: int, semitones: float, strategy: str = "off") -> np.ndarray:
    pitch_ratio = 2.0 ** (float(semitones) / 12.0)
    # Stretch first, then resample back to the original frame count. This mirrors
    # the product decomposition while keeping this reference implementation simple.
    stretched = phase_vocoder(
        audio,
        pitch_ratio,
        PVConfig(fft_size=2048, analysis_hop=256, phase_locking=True, transient_reset=True),
    )
    shifted = signal.resample(stretched.astype(np.float64), len(audio), axis=0).astype(np.float32)
    if strategy == "off":
        return shifted
    return _envelope_correct(audio, shifted, sr, pitch_ratio, strategy)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--pitch", type=float, required=True, help="pitch shift in semitones")
    parser.add_argument("--strategy", choices=("off", "harmonic", "monophonic"), default="harmonic")
    args = parser.parse_args()
    audio, sr = sf.read(args.input, always_2d=True, dtype="float32")
    output = pitch_shift(audio, sr, args.pitch, args.strategy)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    sf.write(args.output, output, sr, subtype="FLOAT")


if __name__ == "__main__":
    main()
