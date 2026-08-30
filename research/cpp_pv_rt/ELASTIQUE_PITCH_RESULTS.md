# Elastique-derived pitch comparison checkpoint

This document records an **engineering comparison**, not a claim that the original Roberts/Paliwal MOS labels apply to pitch shifting.

The supplied Roberts/Paliwal test set contains pitch-preserving time-scale-modified outputs from Elastique. For each Elastique test item, this evaluation measures its actual duration ratio relative to the reference and resamples the Elastique output back to the original reference length. That converts the time-scale result into a pitch-shifted comparison signal whose pitch ratio is the measured duration ratio. The extra resampling stage is part of this evaluation construction, so the result must not be described as a native Elastique pitch-shifter measurement.

## Corpus and range

- 20 reference files.
- 4 Elastique TSM conditions per source: **80 conditions** total.
- Derived pitch range: approximately **-11.57 to +23.69 semitones**.
- boiled egg render time ratio: 1.0.
- Objective diagnostics: broad cepstral spectral-envelope RMSE and normalized spectral-onset correlation.
- Negative envelope delta means boiled egg preserves the original broad envelope better than the derived Elastique comparison signal.

The reproducible harness is `research/eval_elastique_pitch.py`.

## General: 2048 / 256 phase locked

With harmonic formant preservation:

- envelope delta vs derived Elastique: **-2.148 dB mean**;
- envelope wins: **74 / 80**;
- onset-correlation delta: **-0.199 mean**;
- onset wins: **10 / 80**.

With monophonic formant preservation:

- envelope delta: **-1.841 dB mean**;
- envelope wins: **73 / 80**;
- onset-correlation delta: **-0.198 mean**.

With formant processing disabled, envelope delta is **+0.315 dB mean** and wins only **33 / 80**. This strongly supports keeping formant preservation, but also shows that the main remaining objective weakness is temporal/transient clarity rather than the broad spectral envelope.

## Existing transient phase reset

The current frame-level transient-reset mode did **not** solve the temporal problem. At 2048 samples, harmonic formant mode produced an onset-correlation delta of about **-0.206**, slightly worse than ordinary phase-locked processing. Directly, transient-reset minus phase-locked onset correlation averaged roughly **-0.0068**.

At a 1024-sample window the result remained negative: phase-locked onset delta was about **-0.0367**, while the reset variant was about **-0.0469**. The selected user-facing Transient profile therefore remains phase locked. This is consistent with the hypothesis that a long analysis window smears the magnitude trajectory itself; resetting phase alone cannot undo magnitude smearing.

## Window and hop experiments

All rows below use phase locking plus harmonic formant preservation.

| FFT / hop | Envelope delta vs derived Elastique | Envelope wins | Onset-correlation delta | Onset wins |
|---|---:|---:|---:|---:|
| 2048 / 256 | -2.148 dB | 74 / 80 | -0.199 | 10 / 80 |
| 1024 / 64 | -1.614 dB | 69 / 80 | -0.0456 | — |
| 1024 / 128 | -2.134 dB | 77 / 80 | -0.0367 | 36 / 80 |
| **1024 / 256** | **-2.694 dB** | **79 / 80** | **-0.0363** | **34 / 80** |
| 512 / 64 | -1.804 dB | 69 / 80 | **+0.0296** | **46 / 80** |

For 1024 / 256, the full formant-strategy sweep produced:

- **Harmonic:** envelope delta **-2.694 dB**, 79 / 80 wins, onset delta **-0.0363**;
- **Monophonic:** envelope delta **-2.404 dB**, 78 / 80 wins, onset delta **-0.0400**;
- **Off:** envelope delta **-0.273 dB**, 53 / 80 wins, onset delta **-0.0413**.

The 1024 / 256 configuration is therefore the selected manual **Transient** research profile. Relative to General it keeps the large temporal improvement, improves the broad-envelope result further, and costs less CPU than the earlier 1024 / 128 candidate.

## Low-frequency safety and realtime checkpoint

A separate sustained-tone diagnostic tests 55, 80, 120, 220 and 440 Hz sources at -12, +7 and +12 semitones.

- **1024 / 256 Transient:** maximum measured pitch error about **2.153 cents**; minimum target-tone/spur ratio about **23.56 dB**.
- 1024 / 128 old candidate: comparable tonal safety, minimum target-tone/spur about 23.87 dB.
- 2048 / 256 General: minimum target-tone/spur about **44.83 dB**.
- 512 / 64: fails low fundamentals badly, including a worst observed pitch error around **819 cents** and target-tone/spur around **-59 dB**.

On the same GitHub hosted runner, the most recent 96 kHz / 32-frame p99/deadline diagnostic was:

- 512 / 64: **0.220**;
- 1024 / 128: **0.546**;
- **1024 / 256: 0.386**;
- 2048 / 256: **0.709**.

Hosted-runner absolute p99 is noisy, so CI archives the absolute value but primarily gates same-VM relative regressions plus gross overruns.

Therefore:

- **General:** 2048 / 256 phase locked.
- **Transient:** **1024 / 256 phase locked**.
- 512 / 64: do not expose as a full-band mode; retain only as a possible future high-frequency / multi-resolution branch.

## Listening

`research/make_blind_pitch_pack.py` creates a deterministic, level-matched blind pack from the evaluation renders. `research/make_blind_profile_pack.py` selects attack-sensitive conditions and creates a General-vs-Transient profile comparison with separate Overall and Attack/clarity votes.

No third-party dataset audio or derived Elastique audio should be committed to this repository.
