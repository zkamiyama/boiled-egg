# Multi-resolution transient research checkpoint

This document records the current realtime multi-resolution experiment on `research/formant-v0.3-integrated`. It is **not** yet part of the shipping/product core.

## Current realtime architecture

```text
input
  |---------------------------|
1024 / hop 256              512 / hop 192
phase locked                phase locked
selected formant policy     selected formant policy
  |                           |
 low/mid path             high-frequency path
  |                           |
 complementary 6.5 kHz linear-phase crossover
                |
              output
```

Defaults:

- low/mid branch: FFT **1024**, analysis hop **256**;
- high branch: FFT **512**, analysis hop **192**;
- crossover: **6.5 kHz**;
- crossover FIR: **129 taps**, Kaiser beta 8;
- linked multichannel processing;
- exact-duration streaming output;
- no heap allocation in normal processing after construction.

The 1024-point branch protects low-frequency pitch stability. A 512-point full-band processor is deliberately not used because deterministic low-tone tests show catastrophic failures on some 55/80 Hz large-shift cases.

## Why hop 192

The first realtime wrapper used a 512 / hop-128 high branch. It recovered useful transient detail, but at 96 kHz / very small host blocks the second FFT stream left little callback headroom. Simply delaying the high branch by 64 input frames preserved samples bit-for-bit but made the critical CPU burst distribution worse, so that scheduler-stagger experiment was rejected and never committed.

Turning formant analysis off only in the high branch reduced average CPU somewhat, but did not reliably improve p99 and caused a small mean onset regression; that experiment was also rejected.

Increasing only the high-band hop from 128 to **192** is the current accepted research change. It reduces high-band FFT frame rate by one third while leaving the low/mid analysis and crossover unchanged.

## Primary product range: +/-12 semitones

The Roberts/Paliwal reference test set was evaluated against the existing derived-Elastique engineering diagnostic. The diagnostic is produced from the supplied pitch-preserving Elastique TSM renders followed by our own offline exact-length resampling; it is **not** claimed to be a native Elastique pitch-shifter render.

Within the primary target range, 60 conditions are available.

| Realtime candidate | Mean envelope delta vs derived Elastique | Envelope wins | Mean onset-corr delta | Onset wins | Max peak |
|---|---:|---:|---:|---:|---:|
| 1024/256 + 512/128 | -2.243 dB | 59 / 60 | -0.01723 | 29 / 60 | 1.439 |
| **1024/256 + 512/192** | **-2.244 dB** | **59 / 60** | **-0.01678** | **30 / 60** | **1.437** |

Negative envelope delta is better. Positive onset-correlation delta is better.

Paired directly against the hop-128 realtime wrapper over the same 60 conditions, hop 192 changes mean envelope error by about **-0.0016 dB** and mean onset correlation by about **+0.00045**. In other words, the one-third reduction in high-band analysis rate did not cost measurable quality in the primary range in this diagnostic.

Exact output duration remained correct in **60 / 60** target-range renders.

## Low-frequency tonal safety

A deterministic 48 kHz test renders 55, 80, 120, 220 and 440 Hz fundamentals at -12, +7 and +12 semitones through the complete realtime multi-resolution wrapper.

Current hop-192 checkpoint:

- maximum measured pitch error: about **2.153 cents**;
- minimum target-tone/spur diagnostic: about **23.006 dB**;
- exact duration in every case;
- finite output in every case.

These values are effectively unchanged from the hop-128 wrapper. `research/test_multires_candidate.py` makes this a CI regression gate with 3-cent and 22-dB safety thresholds.

## Realtime CPU checkpoint

`boiled_egg_multires_rt_bench` now records both wall-clock callback time and Linux `CLOCK_THREAD_CPUTIME_ID`. Thread CPU time removes scheduler wait from the number, while wall time remains useful for observing host-like deadline behavior. Neither is a portable realtime guarantee on a shared VM.

In three pinned local 96 kHz runs comparing hop 128 with hop 192, the median thread-CPU p99/deadline changed as follows:

| Host block | Pitch ratio | hop 128 median | hop 192 median |
|---:|---:|---:|---:|
| 32 | 0.667 | 1.288x | **0.892x** |
| 32 | 1.498 | 1.195x | **0.935x** |
| 64 | 0.667 | 0.766x | **0.459x** |
| 64 | 1.498 | 0.833x | **0.469x** |
| 128 | 0.667 | 0.616x | **0.335x** |
| 128 | 1.498 | **0.697x** | 0.734x |

The absolute values vary with VM frequency/cache state, but average callback CPU also dropped by roughly 10--17% in the critical 64/128-frame cases. Five of six critical p99 medians improved substantially. Hosted CI therefore archives both CPU and wall p99 and uses only a loose gross-regression threshold; promotion decisions use repeated same-machine comparisons.

## Wide stress range

The complete supplied Elastique subset extends to roughly **+23.7 semitones**, outside the current +/-12 product target. We keep those 80 conditions as a stress suite rather than silently dropping them.

Across all 80 conditions, hop 192 still has strong broad-envelope results (79/80 wins versus the derived diagnostic), but a near-+24-st mix case can create a very large peak (about **17.4** in the current stress run). The same family of extreme conditions is already pathological in the individual PV branches. This means hop 192 is acceptable only as a target-range research candidate; it is **not** evidence for a +/-24-st product guarantee.

Before widening the advertised pitch range, the extreme-upshift peak mechanism needs a separate fix and dedicated regression gate.

## Earlier offline crossover experiment

Before the realtime wrapper existed, an offline experiment combined 1024/256 with 512/64 using a 6 kHz complementary FIR. The 129-tap crossover preserved most of the long-window envelope quality while improving onset correlation versus 1024/256. That experiment established the basic multi-resolution direction, but its exact hop/crossover settings are historical and should not be confused with the current realtime defaults above.

## Remaining promotion gates

Do not promote multi-resolution to the product core yet. Next gates are:

1. complete GitHub CI for GCC/Clang C++20/23, ASan/UBSan, pure-C API, no-allocation and tonal safety after the hop-192 change;
2. archive repeated 48/96 kHz callback CPU/wall diagnostics;
3. build a blind listening pack that includes the realtime multi-resolution candidate, General, Transient and the derived-Elastique diagnostic;
4. inspect the remaining +/-12 peak outliers and listen for crossover coloration or high-band phase texture;
5. separately attack the >+12-st stress peak pathology before considering a wider pitch range.
