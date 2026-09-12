#!/usr/bin/env python3
"""Independent offline HPSS and (WS)OLA research primitives, NOT realtime SDK.

Algorithmic references (no third-party implementation copied):
Driedger/Mueller/Ewert, IEEE SPL 21(1), 2014, doi:10.1109/LSP.2013.2294023.
Driedger/Mueller, DAFx 2014, TSM Toolbox, sections 2.1, 2.2 and 2.5.
This variant uses complementary soft masks, linked channel power and normalized
multichannel waveform correlation. It is not an exact reproduction of a paper.
"""
from __future__ import annotations

import math

import numpy as np
from scipy import signal
from scipy.ndimage import median_filter


def audio_array(audio: np.ndarray) -> np.ndarray:
    x = np.asarray(audio, dtype=np.float64)
    if x.ndim == 1:
        x = x[:, None]
    if x.ndim != 2 or min(x.shape) == 0 or not np.isfinite(x).all():
        raise ValueError('audio must be nonempty, finite, frames x channels')
    return x


def output_frames(frames: int, ratio: float) -> int:
    if frames < 1 or not math.isfinite(ratio) or not 0.25 <= ratio <= 4.0:
        raise ValueError('ratio must be finite in [0.25, 4], frames positive')
    return max(1, int(math.floor(frames * ratio + 0.5)))


def separate(audio: np.ndarray, fft_size: int = 2048, hop: int = 256,
             kernel: int = 17) -> tuple[np.ndarray, np.ndarray]:
    """Centered, noncausal median HPSS. The two outputs sum back to input.

    The temporal median includes future frames: this implementation allocates
    full spectrograms and must NEVER run in an audio callback.
    """
    x = audio_array(audio)
    if fft_size < 32 or fft_size & (fft_size - 1) or not 1 <= hop <= fft_size // 2:
        raise ValueError('invalid FFT/hop')
    if kernel < 3 or kernel % 2 != 1:
        raise ValueError('kernel must be odd and >= 3')
    padded = np.pad(x, ((0, max(0, fft_size-len(x))), (0, 0)))
    _, _, spectra = signal.stft(padded.T, window='hann', nperseg=fft_size,
                                noverlap=fft_size-hop, boundary='zeros', padded=True)
    # Power aggregation, not channel averaging: antiphase stereo must not cancel.
    magnitude = np.sqrt(np.mean(np.abs(spectra)**2, axis=0))
    harmonic = median_filter(magnitude, size=(1, kernel), mode='reflect')
    percussive = median_filter(magnitude, size=(kernel, 1), mode='reflect')
    denominator = harmonic**2 + percussive**2
    mask = np.divide(harmonic**2, denominator,
                     out=np.full_like(denominator, 0.5), where=denominator > 0)
    _, h = signal.istft(spectra*mask[None, :, :], window='hann',
                        nperseg=fft_size, noverlap=fft_size-hop, boundary=True)
    h = h.T[:len(x)]
    return h, x-h


def overlap_add(audio: np.ndarray, ratio: float, frame: int = 512,
                hop: int = 256, tolerance: int = 0) -> np.ndarray:
    """Fixed synthesis-grid OLA; positive tolerance enables linked WSOLA.

    Search is bounded around the nominal input position, not around the last
    chosen position. This limits cumulative timing drift. Correlation uses all
    channels, and a single offset is shared by every channel.
    """
    x = audio_array(audio)
    count = output_frames(len(x), ratio)
    if frame < 16 or frame % 2 or not 1 <= hop <= frame//2 or tolerance < 0:
        raise ValueError('invalid frame/hop/tolerance')
    if tolerance > frame:
        raise ValueError('tolerance must not exceed one frame')
    half = frame//2
    pad = 2*frame+tolerance
    source = np.pad(x, ((pad, pad), (0, 0)))
    window = signal.windows.hann(frame, sym=False)
    result = np.zeros((count+2*frame, x.shape[1]), dtype=np.float64)
    weight = np.zeros(len(result), dtype=np.float64)
    previous = None
    overlap = frame-hop
    for position in range(0, count+half, hop):
        nominal = pad+int(math.floor(position/ratio+0.5))-half
        nominal = int(np.clip(nominal, 0, len(source)-frame))
        chosen = nominal
        if tolerance and previous is not None:
            left = max(0, nominal-tolerance)
            right = min(len(source)-frame, nominal+tolerance)
            template = source[previous+hop:previous+hop+overlap]
            region = source[left:right+overlap]
            energy = float(np.sum(template*template))
            if len(template) == overlap and energy > 1e-24:
                dot = sum(signal.correlate(region[:, ch], template[:, ch],
                                          mode='valid', method='fft')
                          for ch in range(x.shape[1]))
                power = np.sum(region*region, axis=1)
                cumulative = np.r_[0.0, np.cumsum(power)]
                norms = np.sqrt(np.maximum(0.0, cumulative[overlap:]-cumulative[:-overlap])*energy)
                score = np.divide(dot, norms, out=np.full_like(dot, -np.inf), where=norms > 1e-24)
                best = float(np.max(score))
                if math.isfinite(best):
                    # Deterministic closest-nominal tie breaking (important for tones).
                    ties = np.flatnonzero(score >= best-1e-12)
                    offset = ties[np.argmin(np.abs(left+ties-nominal))]
                    chosen = left+int(offset)
        result[position:position+frame] += source[chosen:chosen+frame]*window[:, None]
        weight[position:position+frame] += window
        previous = chosen
    result = result[half:half+count]
    weight = weight[half:half+count]
    if np.any(weight <= 1e-12):
        raise RuntimeError('uncovered synthesis samples')
    result /= weight[:, None]
    if not np.isfinite(result).all():
        raise RuntimeError('non-finite OLA output')
    return result


def wsola(audio: np.ndarray, ratio: float) -> np.ndarray:
    """Fixed 2048/1024, +/-512-sample offline research preset at 44.1 kHz."""
    return overlap_add(audio, ratio, frame=2048, hop=1024, tolerance=512)
