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

## 2048 / 256 phase-locked baseline

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

This is consistent with the hypothesis that a long analysis window smears the magnitude trajectory itself; resetting phase alone cannot undo that magnitude smearing.

## Window-size experiment

All rows below use phase locking plus harmonic formant preservation.

| FFT / hop | Envelope delta vs derived Elastique | Envelope wins | Onset-correlation delta | Onset wins |
|---|---:|---:|---:|---:|
| 2048 / 256 | -2.148 dB | 74 / 80 | -0.199 | 10 / 80 |
| **1024 / 128** | **-2.134 dB** | **77 / 80** | **-0.0367** | **36 / 80** |
| 512 / 64 | -1.804 dB | 69 / 80 | **+0.0296** | **46 / 80** |

The 1024 window is therefore the current candidate for the manual **Transient** quality profile: it retains essentially all of the formant-envelope advantage while reducing the mean onset deficit by about 80%.

## Why 512 is not being promoted

A separate sustained-tone diagnostic tested 55, 80, 120, 220 and 440 Hz sources at -12, +7 and +12 semitones. The 512-sample window failed badly for low fundamentals: 55/80 Hz cases showed large pitch errors and strong spurious components, including a worst observed pitch error of roughly **819 cents**.

The same diagnostic for 1024 samples kept the tested pitch estimates within roughly **2.2 cents**, with a worst tone-to-spur diagnostic of about **23.9 dB**. The 2048 window remained cleaner at low frequencies, with the corresponding worst tone-to-spur diagnostic around **44.8 dB**.

Therefore:

- **General** research candidate: 2048 / 256 phase locked.
- **Transient** research candidate: 1024 / 128 phase locked.
- 512 / 64: do not expose as a full-band mode; retain only as a possible future high-frequency/multi-resolution branch.

## Listening

`research/make_blind_pitch_pack.py` creates a deterministic, level-matched blind pack from the evaluation renders. It randomizes derived Elastique, formant-off, harmonic-preserve and monophonic-preserve renders into anonymous A-D choices and emits an `index.html`, `manifest.csv`, and a separate `answer_key.csv`.

No third-party dataset audio or derived Elastique audio should be committed to this repository.
