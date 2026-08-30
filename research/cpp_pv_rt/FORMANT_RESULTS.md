# Formant v0.3 integrated quality checkpoint

This document records the reproducible engineering checkpoint for `research/formant-v0.3-integrated`. It is **not** a perceptual-parity claim. The Roberts/Paliwal dataset audio remains local and is not redistributed.

## Test matrix

- Source corpus: Roberts/Paliwal TSM **reference test set**, 20 mono WAV files at 44.1 kHz.
- Pitch shifts: `-12, -7, -3, +3, +7, +12` semitones.
- Formant variants: `off`, `harmonic`, `monophonic`.
- Total renders: **360**.
- DSP mode: phase locked.
- Time ratio: 1.0.
- Default formant gain limit: 15 dB.
- Objective envelope metric: cepstrally smoothed log-spectral envelope, 150 Hz–6 kHz, with per-frame global gain removed before the envelope RMSE calculation.
- Onset diagnostic: correlation of positive changes in a per-frame normalized log spectrum.

## Why energy centering was added

The original `formant-v0.2` spectral-envelope correction improved envelope error but could also behave as a broadband gain stage. In the first 360-render pass, maximum output peak reached about **2.34**, with individual formant-on cases gaining more than 4–5 dB RMS over the corresponding formant-off render.

The integrated v0.3 backend therefore:

1. computes the relative per-bin formant EQ;
2. recenters its magnitude-squared-weighted **log gain** around 0 dB;
3. applies a linked-channel scalar to remove any remaining positive broadband spectral-power gain.

The relative formant contour remains, while the correction no longer has a large systematic loudness bias. The operation uses existing fixed arrays and scalar state only; it does not allocate or lock in the processing path.

## 20-reference result

| Diagnostic | Harmonic | Monophonic |
|---|---:|---:|
| Paired envelope wins vs off | **120 / 120** | **120 / 120** |
| Paired envelope losses vs off | **0** | **0** |
| Mean envelope improvement | **+2.696 dB** | **+2.311 dB** |
| Median envelope improvement | **+2.609 dB** | **+2.147 dB** |
| 10th percentile improvement | **+0.811 dB** | **+0.672 dB** |
| 90th percentile improvement | **+4.859 dB** | **+4.097 dB** |
| Voice subset mean improvement | **+3.551 dB** | **+3.081 dB** |
| Voice subset wins | **42 / 42** | **42 / 42** |
| Mean onset-correlation delta | **+0.0070** | **+0.0095** |
| Worst onset-correlation delta | **-0.0687** | **-0.0662** |
| Mean RMS delta vs off | **-0.036 dB** | **-0.028 dB** |
| 95th percentile abs RMS delta vs off | **0.273 dB** | **0.283 dB** |
| Maximum peak ratio vs off | **1.504x** | **1.382x** |
| 95th percentile peak ratio vs off | **1.260x** | **1.225x** |

Exact output duration was preserved in all **360 / 360** renders (maximum duration error: **0 frames**).

### Harmonic envelope improvement by pitch shift

| Shift | Mean improvement |
|---:|---:|
| -12 st | +3.559 dB |
| -7 st | +3.136 dB |
| -3 st | +2.164 dB |
| +3 st | +1.780 dB |
| +7 st | +2.588 dB |
| +12 st | +2.951 dB |

### Monophonic envelope improvement by pitch shift

| Shift | Mean improvement |
|---:|---:|
| -12 st | +2.864 dB |
| -7 st | +2.570 dB |
| -3 st | +1.777 dB |
| +3 st | +1.602 dB |
| +7 st | +2.359 dB |
| +12 st | +2.697 dB |

## Synthetic correctness gates

The CI regression fixture uses the same six pitch shifts and checks exact duration, pitch, stereo linkage and envelope preservation.

- Maximum measured pitch error: about **0.0031 cent**.
- Stereo linked-gain relationship error on the synthetic two-channel fixture: roughly **4.5e-5 relative RMS**.
- Both formant strategies improve their intended synthetic envelope fixtures at every tested pitch shift.

The research workflow also runs GCC and Clang under C++20 and C++23, ASan/UBSan, no-allocation tests, and the 48/96 kHz callback p99/deadline matrix. The callback gate is **p99/deadline < 0.90**, including 96 kHz / 32-frame cases.

## Remaining promotion gates

Do not promote this backend to the product core yet. Before promotion:

- run deterministic blind listening packs on voice, solo instruments, chords and mixes;
- compare formant-off/harmonic/monophonic against external baselines where licensing permits;
- listen specifically for frame-rate amplitude modulation/pumping introduced by gain centering;
- inspect the remaining worst-case peak-ratio cases and decide whether the SDK should expose explicit output headroom, a formant-strength control, or a lower default gain limit;
- repeat the full realtime gate after any such change.
