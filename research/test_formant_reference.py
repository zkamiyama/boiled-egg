#!/usr/bin/env python3
from __future__ import annotations

import math
import unittest

import numpy as np
from scipy import ndimage, signal

from formant_reference import pitch_shift

SR = 48000
DURATION = 1.25


def spectral_envelope(audio: np.ndarray) -> np.ndarray:
    x = np.mean(audio, axis=1) if audio.ndim == 2 else audio
    n_fft = 8192
    frames = []
    window = signal.windows.hann(n_fft, sym=False)
    hop = 2048
    padded = np.pad(x.astype(np.float64), (n_fft // 2, n_fft // 2))
    for start in range(0, max(1, len(padded) - n_fft + 1), hop):
        frame = padded[start:start+n_fft]
        if len(frame) < n_fft:
            frame = np.pad(frame, (0, n_fft-len(frame)))
        frames.append(np.abs(np.fft.rfft(frame * window)) + 1.0e-10)
    mag = np.mean(np.stack(frames), axis=0)
    logmag = np.log(mag)
    # Heavy smoothing removes individual harmonics and leaves the broad formant contour.
    return ndimage.gaussian_filter1d(logmag, sigma=18.0)


def envelope_distance(reference: np.ndarray, test: np.ndarray) -> float:
    a = spectral_envelope(reference)
    b = spectral_envelope(test)
    # Ignore very low/DC and near-Nyquist bins where the synthetic fixtures carry little energy.
    lo = 10
    hi = int(len(a) * 0.85)
    a = a[lo:hi] - np.mean(a[lo:hi])
    b = b[lo:hi] - np.mean(b[lo:hi])
    return float(np.sqrt(np.mean(np.square(a - b))))


def formant_gain(freq: float) -> float:
    # Three broad vocal-tract-like resonances plus a gentle spectral tilt.
    resonances = (
        1.5 * math.exp(-0.5 * ((freq - 650.0) / 150.0) ** 2),
        1.1 * math.exp(-0.5 * ((freq - 1250.0) / 220.0) ** 2),
        0.8 * math.exp(-0.5 * ((freq - 2600.0) / 320.0) ** 2),
    )
    return (0.08 + sum(resonances)) / math.sqrt(max(freq, 80.0) / 80.0)


def harmonic_fixture(fundamentals: list[float]) -> np.ndarray:
    frames = int(SR * DURATION)
    t = np.arange(frames, dtype=np.float64) / SR
    x = np.zeros(frames, dtype=np.float64)
    for f0 in fundamentals:
        phase = 0.17 * f0
        harmonic = 1
        while harmonic * f0 < 9000.0:
            frequency = harmonic * f0
            amplitude = formant_gain(frequency) / max(1.0, harmonic ** 0.12)
            x += amplitude * np.sin(2.0 * np.pi * frequency * t + phase * harmonic)
            harmonic += 1
    fade = min(1024, frames // 10)
    envelope = np.ones(frames)
    envelope[:fade] = np.linspace(0.0, 1.0, fade)
    envelope[-fade:] = np.linspace(1.0, 0.0, fade)
    x *= envelope
    x /= max(np.max(np.abs(x)), 1.0e-9)
    return x.astype(np.float32)[:, None]


class FormantReferenceTests(unittest.TestCase):
    def test_harmonic_strategy_improves_polyphonic_envelope(self) -> None:
        source = harmonic_fixture([110.0, 138.59, 164.81])
        plain = pitch_shift(source, SR, 7.0, "off")
        preserved = pitch_shift(source, SR, 7.0, "harmonic")
        self.assertEqual(len(source), len(preserved))
        self.assertTrue(np.all(np.isfinite(preserved)))
        plain_distance = envelope_distance(source, plain)
        preserved_distance = envelope_distance(source, preserved)
        print(f"polyphonic formant envelope: plain={plain_distance:.6f} preserved={preserved_distance:.6f}")
        self.assertLess(preserved_distance, plain_distance * 0.98)

    def test_monophonic_strategy_improves_single_note_envelope(self) -> None:
        source = harmonic_fixture([140.0])
        plain = pitch_shift(source, SR, -7.0, "off")
        preserved = pitch_shift(source, SR, -7.0, "monophonic")
        self.assertEqual(len(source), len(preserved))
        self.assertTrue(np.all(np.isfinite(preserved)))
        plain_distance = envelope_distance(source, plain)
        preserved_distance = envelope_distance(source, preserved)
        print(f"monophonic formant envelope: plain={plain_distance:.6f} preserved={preserved_distance:.6f}")
        self.assertLess(preserved_distance, plain_distance * 0.98)


if __name__ == "__main__":
    unittest.main()
