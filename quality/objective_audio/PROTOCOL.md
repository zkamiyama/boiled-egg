# Objective-first qualification, 2026-09-16

Roadmap #15/#17. User requests fewer human-listening dependencies. Correctness
and reproducible defect repairs do not wait for ratings; broad perceptual claims
still require a validated estimator/domain or listening evidence. No inferred MOS.

Base b3f6d8c53bcf1f9380aa104c4bfcb773609e8ec5 (public spectral preview). The previously
reported proportional-stereo residual is reproduced on the known two-second
48k fixture. Diagnose independent unbounded per-channel phase accumulation using
three matched variants: original, wrapped-phase-only, shared bounded phase rotation.
The exact numerical threshold remains1e-5. No fitted delay/gain, limiting, mono
collapse or post-render correction. Preserve WSOLA, mono and dynamic ramp behavior
unless a change is explicitly recorded. Work on the opt-in preview, not stable main.

## Frozen confirmation

After the diagnostic pilot, freeze the chosen source before confirmation:
48/96k x General/Transient x Off/Harmonic/Monophonic x operations
(T,p_semitones)=(1,0),(.9,0),(1.1,0),(1,-7),(1,+7).
Reproduce the earlier proportional/silent-channel/burst/channel-exchange audit.
Additional seeded broad-spectrum signals use seeds26091601..26091604, gains
-0.375,0.25,-2,0, and both 0.25s/2s where applicable. Include positive/negative
channel ratios, silent channel, unequal channel energy, channel permutations,
and signals with independent spatial content. Do not tune thresholds to results.
Track startup/middle/tail separately without deleting any interval.

A ratio test cannot identify a unique transformed waveform. Use a phase-invariant
spectral channel-vector/projector distance in addition to raw residual, plus
interchannel level/phase diagnostics on active bins. These are physical spatial
constraints, not calibrated audibility scores. Zero energy cannot be a perfect
pass. Identical/muted/swapped/common-phase/relative-delay/mono-collapse and graded
error controls calibrate the metric before using it as evidence.

Compare full mono renders before/after; preserve bytes if the mono path is not
changed. Existing fixed-delay, arbitrary-ramp, exact-duration, no-allocation,
GCC/Clang20/23, ASan/UBSan tests remain. Evaluate the earlier stereo fixtures
unchanged; new seed controls are within-session confirmation, not new natural
recordings. No automatic product promotion or native-zplane superiority claim.

## Literature-informed objective hierarchy

Roberts/Paliwal OMOQDE (2021, arXiv2006.06153) and OMOQSE (arXiv2009.02940)
are TSM-trained quality predictors, not interchangeable with ordinary speech MOS.
Their published correlations/RMSE are dataset-level results, not accuracy promises
on this SDK, formant shifting or stereo. ViSQOL v3 compares a clean reference and
mono-downmixes multichannel audio; it cannot replace spatial tests. Zimtohrli
(arXiv2509.26133) is full-reference and uses auditory representations/time matching;
it must not be used to silently align away timing errors. DAFx2025 He/Williams/
Fazenda tests show different metrics miss different hum/hiss/clipping/glitch cases.

Use analytical targets, metamorphic invariants and calibrated artifact probes as
hard automated gates. Keep source-relative spectral/envelope errors diagnostic.
A future frozen perceptual model must be validated against held-out existing MOS
by source AND engine, with no leakage from the repeatedly used20-source corpus.
Do not fabricate ratings, retrain until a favored DSP wins, or transfer native
vendor claims from derived or unrelated reference audio.

Primary references:
https://arxiv.org/abs/2006.06153
https://arxiv.org/abs/2009.02940
https://github.com/google/visqol
https://arxiv.org/abs/2509.26133
https://dafx25.dii.univpm.it/wp-content/uploads/2025/09/DAFx25_paper_5.pdf
