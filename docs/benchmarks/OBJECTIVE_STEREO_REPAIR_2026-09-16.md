# Objective-first stereo repair — 2026-09-16 JST

## Decision

A specific static multichannel PV invariant defect is repaired without listener
responses, fitted audio alignment, output gain correction or relaxed thresholds.
The original 240-output stereo/time audit now passes all 120 proportional/silent
controls and all 60 exchange pairs. This is numerical/spatial correctness evidence,
not a claim that all natural music sounds better or that native zplane is beaten.

Draft PR26 is on quality/objective-stereo-coherence, based on the explicit-ramp
preview, not stable main. The final patch is applied explicitly to the separately
pinned PV source; ordinary branch defaults and stable main remain untouched.
Static stereo has additional CPU cost, so no unconditional production promotion
is claimed. Mono and dynamic-pitch arithmetic/output compatibility are retained.

## Resumption and source provenance

The resumed branch already contained the protocol, metrics, rejected static
reference-channel pilot and final pooled-increment patch at
89e0d698b3081a5868e2914ef0f88fccea3cfcf4. Those inherited implementations are not
claimed as newly invented during this continuation. New work adds dedicated CI,
correct dependency wiring, complete local/CI reruns, a static-path capacity
benchmark, supplemental artifact calibration and final documentation.

New commits:9508dda0 initial CI;6d51a9ea explicit audit dependency correction;
f4f8a14a static capacity benchmark;4e50fc51 reproduction/method README.
Validated code checkpoint is f4f8a14a0b51a556190130528ca254f8cdbb3882, tree
b8d7d5723792c0cc635fc5e3de3dae1ad09f3093. Later changes are documentation only.

Pinned DSP source:f8e5ef2cbce84f396597860a408b4a3084796115. The original local
source archive had 198 verified tracked hashes. The old audit comes separately
from894476d1c5a44cd0c2c9ff1cccb34e0fca792f5c; its code snapshot has143 hashes.
The final CI artifact10427536862 was downloaded: ZIP CRC and SHA256
8be99f62b2dca8150a29ed087da20dc06e837470d50b081868523b4e0bee64f3 pass.
All209 current branch source hashes verify, and all198 patched-PV file hashes
match the actual locally measured candidate. The measured benchmark matches its
committed bytes. Synthetic merge90a8d2635586ebe3064b11f7f29ddd944b506348 has the
same validated code tree. This is not a claimed main merge.

## Objective-method research and implementation choice

- Roberts/Paliwal OMOQDE (2020 preprint, 2021 journal) augments PEAQ features with
  TSM-specific descriptors and a learned MOS predictor. OMOQSE predicts TSM quality
  without a reference. Their published dataset correlations are not measurements
  of this SDK, pitch/formant operations or stereo. Neither model was executed or
  retrained here. A frozen source-and-engine held-out validation is required before
  using such a score for automatic natural-audio decisions.
- Google's ViSQOL is full-reference, uses mono downmix for multichannel audio, and
  recommends a clean same-content reference. It cannot replace spatial checks or
  justify comparing a shifted output against unshifted input as an ideal target.
- Zimtohrli (2025) compares auditory representations using modified DTW/NSIM.
  Its time matching must not hide the timing errors we are diagnosing. No
  Zimtohrli inference or trained score is claimed in this work.
- He/Williams/Fazenda, DAFx2025, tested objective metrics on hum, hiss, clipping
  and glitches and found differing sensitivities. This motivates multiple
  calibrated failure probes, not one universal aggregate quality score.

The implemented primary layer uses analytically specified channel relations and
metamorphic checks: polarity/gain, silence, channel exchange, identical block
partitions, exact length, reset and deterministic state. The spatial projector
measures channel-vector direction independently of a common complex rotation.
ILD/IPD and raw waveform residual remain separate because the projector is blind
to common-mode gain/timbre changes. These are physical diagnostics, not fitted
perceptual scores. Zero signal cannot qualify as perfect stereo preservation.

Eight committed calibration tests exercise common phase, relative phase, mono
collapse, graded error, gain/polarity, injected interchannel delay, zero/invalid
signals, readonly inputs and unfitted envelope changes. No listener data are
invented and no new human ratings were received.

## Mechanism and scope of the repair

The old static non-Fuzzy multichannel PV evolves growing per-channel phase
accumulators and reconstructs each channel separately using magnitude/phase.
Those separate histories and finite-precision operations break a prescribed
proportional channel relationship. The first shared-rotation pilot used a
channel-index-dependent dominant reference; it fixed proportionality but failed
48/60 earlier exchange checks. That pilot is retained and rejected, not combined
with the final patch.

The adopted static path combines interframe phase increments on the circle:

advance = arg(sum_c |X_c|^2 exp(j*(phase_c - previous_phase_c))).

It derives one bounded rotation per bin and multiplies each original complex
channel coefficient by the same rotation/formant gain. It does not average raw
phase angles or collapse channels to mono. Both immediate and cooperative frame
paths use identical logic. Two bins-sized float arrays are allocated during
construction, not processing/reset. No new FFT, lookahead, output limiter, delay
fit or post-render stereo repair. Public ABI, state, latency/tail and manual
quality/formant selections are unchanged. The patch is limited to static
multichannel non-Fuzzy processing; mono, WSOLA and dynamic timeline paths keep
their original arithmetic.

## Fresh primary objective results

The earlier audit's input construction and1e-5 threshold are unchanged. It has
48/96k, General/Transient, Off/Harmonic/Monophonic, five operations, and four
stereo fixtures. Only our six PV configurations are rerun here; the prior R3
observations are not silently changed or relabeled as a new vendor comparison.

| Original audit | Before | Candidate |
|---|---:|---:|
|Valid raw outputs|240/240|240/240|
|Proportional-channel controls|0/60|60/60|
|Silent-right controls|60/60|60/60|
|Channel-exchange pairs|60/60|60/60|
|Maximum proportional residual|4.5778143e-4|6.4439659e-8|

The baseline CLI correctly exits1 and the candidate exits0. All metadata are
finite/FLOAT/exact accepted length, no measurement errors. Raw output hashes and
failed baseline receipts are retained. Maxima are over each complete grid, not
necessarily a comparison of the same single worst case.

A separate declared fixture generator and seeded regression study also pass:

| Study | Paired conditions | Before pass | Candidate pass | Worst residual before/after |
|---|---:|---:|---:|---:|
|Two-second proportional replication|60|0|60|5.6329000e-4 / 6.7259266e-8|
|Four seeded/gain/length configurations|240|120|240|5.3333513e-3 / 1.0941928e-7|

The confirmation gains are-.375,.25,-2 and0, with .25s/2s signals across both
rates, qualities, policies and operations. These seeds were already examined in
the interrupted rejected pilot; they are regression coverage, not a pristine
held-out natural population. No threshold or algorithm tuning followed these
fresh reruns. Startup/middle/tail errors, spatial projector and ILD/IPD are kept.

The compiled public-SDK spatial test covers288 static configurations, each at
blocks32/257 and including streaming/realtime I/O, pitches.5/1/2 and four gains.
Failures fall144->0; maximum relative error4.8665e-4->9.59452e-8. Twelve dynamic
pitch cases have identical local before/after output fingerprint
18071795476616882226 and preserve their block equivalence. Cross-compiler or
CI fingerprints need not match that local value; only matched runs are compared.

Actual20 supplied mono references x2 qualities x3 policies at+7st:120/120 whole
WAV hashes are identical before/after,240 renders. Source WAV hashes are retained;
no substitute dataset or six-pitch mono coverage is implied by that count.

The primary fresh standalone studies generate1320 outputs:480 original-audit,
120 replication,480 seeded and240 actual-mono outputs. Related fixtures and
reruns are not independent source samples. C++ test processing and supplemental
reuse of these outputs are not counted again as quality evidence.

## Supplemental same-target artifact audit, explicitly local-only

An attempted GitHub publication of target_artifacts.py was safety-blocked. It
was not retried through another path/action. This optional diagnostic and its
six tests remain local-only in the delivery; the committed tests and CI do not
depend on them. All six local tests pass. They check known gain, delay, polarity,
graded noise, total mute and energy injected into reference-silent regions.

The supplement keeps silent-region energy separate from active-only spectral
scores, so an artifact in an otherwise silent region is not scored as harmless.
It is not an implementation of OMOQ, PEAQ, ViSQOL or a trained audibility metric.

A labeled post-hoc reuse of96 existing unity outputs compares them directly with
their unchanged inputs, a valid same-target reference only because T=p=1 here.
There are no new renders, fits, thresholds or source retuning. For the24 paired
burst/exchanged-burst cases, maximum relative waveform error drops0.475462 to
2.51696e-7; for proportional/silent fixtures it drops about0.006388 to2.85970e-7.
The maximum burst inactive-reference energy ratio falls6.28979e-6 to6.30079e-15.
These checks reinforce unity reconstruction, not general transformed-audio quality.
The full post-hoc measurements and the publication boundary are preserved.

## Correctness and instrumentation

Fresh local GCC14.2 and Clang17, C++20/23, patched full preview:23/23 CTests each.
Matched-Clang ASan+UBSan with leak detection:23/23. The additional static spatial
executable also passes for each of those builds. Patched GCC ThreadSanitizer:
spectral-thread and ramp-thread tests2/2, no suppressions. Original GCC20 also
passes its23 legacy CTests, showing why the stronger stereo regression mattered.
Eight committed objective metric tests and six local-only artifact tests pass.
No new manual DAW, native-vendor or whole-program cross-platform GUI result.

## Practical CPU: capacity passes, cost increases

Timing used immutable GCC20 original/candidate libraries, CLOCK_MONOTONIC_RAW
only, CPU0 affinity, three rotated sequential repetitions. No build, rendering
or test work overlapped these measurements. Each pitch.5/1/2 covers24 settings:
48/96k stereo x2 qualities x3 policies x32/64 blocks. Each cell warms up through
its declared delay plus.5s, then records1200 calls. Two formant events occur per
callback; hashing and signal generation are outside the clock bracket.

Each variant has259200 steady and199026 cold calls. All within-variant repeated
state fingerprints agree. Under the unchanged empirical policy
max_states(best_of_3)<=80%period, original72/72 and candidate72/72 pass.

| Pitch | Candidate worst state-best/period |
|---|---:|
|.5|0.747873|
|1|0.643947|
|2|0.708513|

This is not a speed optimization. Across72 paired cells, median per-cell median
mean-time ratio is1.187569 (about+18.76%); maximum is1.318788. Six cells exceed
1.25x mean cost, so it does NOT satisfy a universal25% regression budget.
The scoped accuracy/cost tradeoff requires explicit review, not a relaxed gate.

Raw steady deadline misses:original94/259200, candidate119/259200. Actual complete
steady runs:original164/216, candidate162/216. Largest raw duration/period:
original4.209891,candidate6.774210. All records remain. Capacity is not WCET,
p99, a stitched uninterrupted success, or a guarantee about a complete DAW graph.
No physical cause is assigned to these outliers. The benchmark was run locally;
its source is committed, but current dedicated CI does not run this cost matrix.

## Hosted result and integration boundary

At code checkpoint f4f8a14a, objective-stereo-coherence35046712207 succeeds5/5:
GCC/Clang20/23 full patched tests and spatial/metric checks, GCC20 strict original
240-output audit, and ASan/UBSan of the actual patched code. Existing product
workflow35046712216 also succeeds. The earlier6d51a9ea checkpoint succeeded too.
CI confirms the exact old stereo constraints, not merely evidence generation.
Its raw compiler-dependent numbers remain distinct from local measurements.

The branch contains an explicitly applied patch and reviewable tests/results,
not an automatic replacement of stable main or every preview/plugin path.
No listener response is required to conclude that the declared numerical stereo
invariant is repaired. General naturalness and system-wide promotion are separate
claims. The next objective work should validate frozen TSM predictors on existing
held-out subjective data and investigate the measured static-path cost, rather
than block this scoped correctness result on new listening submissions.

Primary references consulted:
- https://arxiv.org/abs/2006.06153
- https://arxiv.org/abs/2009.02940
- https://github.com/google/visqol
- https://arxiv.org/abs/2509.26133
- https://dafx25.dii.univpm.it/wp-content/uploads/2025/09/DAFx25_paper_5.pdf
