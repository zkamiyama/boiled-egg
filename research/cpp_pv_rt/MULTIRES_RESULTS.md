# Multi-resolution transient research checkpoint

This document records the first two-resolution experiment built on top of the validated `Transient` research profile. It is **not** yet part of the shipping/product core.

## Motivation

The 512 / 64 phase-locked branch produces substantially sharper temporal behavior than the full-band profiles and, on the 80-condition derived-Elastique engineering comparison, averages a positive onset-correlation delta. It cannot be used full-band because low fundamentals fail catastrophically. The experiment therefore keeps the validated 1024 / 256 branch for the full/low-frequency signal and replaces only the high-frequency content with the 512 / 64 result.

The offline evaluator is `research/eval_multiresolution.py`.

## Architecture under test

```text
input
  |------------------------|
1024 / 256               512 / 64
phase locked             phase locked
Harmonic formant         Harmonic formant
  |                        |
 low-pass 6 kHz       high-pass 6 kHz
  |                        |
  +---------- sum ---------+
```

The crossover filters are complementary linear-phase FIRs. If the two branch signals are identical their sum is the original signal (apart from the common FIR delay/cropping convention). The current practical candidate uses **129 taps** at **6 kHz**.

## 80-condition result

Compared with the derived-Elastique engineering signal:

- mean broad-envelope delta: **-2.639 dB**;
- envelope wins: **77 / 80**;
- mean onset-correlation delta: **-0.0120**;
- onset wins: **38 / 80**.

Compared directly with the 1024 / 256 Harmonic-formant branch:

- mean broad-envelope change: **+0.055 dB** (small regression);
- worst broad-envelope regression: about **+0.246 dB**;
- mean onset-correlation change: **+0.0243**;
- onset improves in the majority of tested conditions.

Level stability relative to the 1024 / 256 branch:

- 95th-percentile absolute RMS delta: about **0.059 dB**;
- 95th-percentile peak ratio: about **1.013x**;
- maximum peak ratio: about **1.030x**.

Exact duration remains unchanged in the offline crossover evaluator.

## FIR-length sweep at 6 kHz

| FIR taps | Envelope delta vs derived Elastique | Envelope wins | Onset delta vs derived Elastique | Mean envelope delta vs 1024/256 | Mean onset delta vs 1024/256 | Worst envelope delta vs 1024/256 |
|---:|---:|---:|---:|---:|---:|---:|
| 33 | -2.500 dB | 68 / 80 | -0.01325 | +0.194 dB | +0.0230 | +0.867 dB |
| 65 | -2.589 dB | 72 / 80 | -0.01286 | +0.105 dB | +0.0234 | +0.466 dB |
| **129** | **-2.639 dB** | **77 / 80** | **-0.01201** | **+0.055 dB** | **+0.0243** | **+0.246 dB** |
| 257 | -2.662 dB | 78 / 80 | -0.01162 | +0.032 dB | +0.0247 | +0.161 dB |
| 513 | -2.676 dB | 79 / 80 | -0.01170 | +0.018 dB | +0.0246 | +0.178 dB |

129 taps is the current realtime-oriented candidate: it retains most of the 257/513-tap benefit with substantially fewer per-sample MACs.

## Crossover sweep

A lower crossover can push the mean onset metric beyond the derived-Elastique engineering baseline, but it exposes too much of the 512 branch and creates envelope failures on extreme material. For example, around 4.5 kHz the mean onset delta is approximately neutral/slightly positive, but some extreme mix cases regress several dB in broad-envelope error.

At **6 kHz**, the crossover is deliberately conservative: it preserves almost all of the 1024 / 256 envelope behavior while still recovering a meaningful fraction of the high-frequency transient advantage.

## Low-frequency safety

The same 55, 80, 120, 220 and 440 Hz tonal set used for the Transient profile was recombined through the 6 kHz crossover. With 129 taps:

- maximum measured pitch error remains about **2.153 cents**;
- minimum target-tone/spur diagnostic remains about **23.56 dB**.

This confirms that the catastrophic low-frequency behavior of the 512 branch is effectively excluded by the high-pass branch in the tested cases.

## Next gate

The next step is a real streaming C++ wrapper that runs the 1024/256 and 512/64 engines concurrently and performs the complementary crossover without allocation or locking in the hot path. It must pass:

- exact-duration flush;
- no-allocation tests;
- ASan/UBSan;
- linked-stereo regression;
- 48/96 kHz callback p99 diagnostics;
- the existing tonal safety gate;
- the 80-condition external/offline evaluator before any product promotion.
