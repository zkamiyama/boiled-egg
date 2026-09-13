# Bounded phase-owner refinement — 2026-09-14 JST

## Decision

The new isolated refinement improves sustained partial balance, including eight post-design oscillator banks. **It does not solve the old coherence guard's natural-audio pitch-onset regression.** It retains approximately the old guard's real-corpus descriptors with additional CPU cost. No default, product ABI, plugin/state, fixed-delay contract or main change; no promotion or human listening. Native zplane pitch and physical CPU-tail attribution remain unresolved.

The starting branch HEAD was b64efd13c4c8e77c6558d7c6bd6098604bc4d5bb. GitHub comparison confirmed no ordinary runtime change since the verified8401ddaa archive. Its222 source hashes were checked. The experiment is a patched working tree, not a claim that the branch default enables the guard. Actual source/analysis/binary hashes are in the delivery. The measured old-guard header differs from the repository-applied patch by two comments; the study harness differs by blank lines, with identical computational AST. The final helper/test blobs match the committed bytes, and applying the refinement patch to the measured old guard exactly reproduces the measured changed runtime.

## Implementation and commits

When an assigned peak has an incompatible phase-derived frequency, the old guard uses the bin's own predicted phase. The new helper first searches nearby peak owners within a fixed +/-4-bin neighborhood, using modulo-hop phase compatibility. If no eligible peak exists, it preserves the own-bin fallback.

The final candidate additionally requires **abs(candidate_bin-bin)*hop < bins-1**, equivalent to a strict FFT/(2*hop) geometric distance. This rejects distant partials that match only because phase advance is aliased. At most nine lookups are needed; no new persistent buffer, FFT, lookahead or magnitude manipulation is added. Both immediate and cooperative paths use the same helper. Formant policies and transient holdoff remain unchanged. This is an engineering refinement, not a claimed new reproduction of SELEBI or another paper.

| Commit | Change |
|---|---|
| bae09396 | Initial compatible-owner helper |
| c158844a | Exhaustive selector tests |
| 8f28c10f | Isolated immediate/cooperative patch |
| c1e69376 | Complete-grid resumable three-way study |
| 2d6da06a | Cache/grid/routing/error regressions |
| cb8a4bfa | Final geometric anti-alias bound |
| 1203b2de | Distant-alias rejection tests |
| 858fa5c8 | Eight new post-design banks |
| 45f0e5a5 | Dense-automation CPU benchmark |
| a0a4403b | Dedicated patched-build CI |

The final helper blob is0ec94c936c8130f4a6f9f7b279fb361da29bd92f; the final C++ regression blob is822e1cbfa37769bc41e132af97c1e4c99ba59ea4.

### Rejected attempts and data reuse

Separate ordinary-Fuzzy phase-history recovery failed to improve onset; stationarity gating suppressed needed close-partial corrections; extended holdoff did not improve the tradeoff. Their source diffs and pilots are retained.

An unbounded-neighbor version looked promising on five development sources but worsened the four-bank48k partial error from0.638466 to1.259334dB. The final geometric bound supersedes that version. Its full2058-output study remains separate negative evidence.

The initial source split labels positions0,4,8,12,16 as development and the other15 as confirmation. **The final bound was designed after seeing the wide proposal's full results, so that15-source subset is not an untouched final holdout.** The real corpus has also been reused historically. Eight synthetic seeds93273–93280 were generated after fixing the final design; there was no further tuning on those results.

## Final evaluation

All variants are Fuzzy: ordinary baseline, old guard, bounded refinement. Each comparison uses the same source WAV; no raw output normalization, limiter, fitted alignment or DTW. All outputs have finite samples and exact frames/rates/channels. Pitch is centered/scaled, scheduled SIMD block32; direct TSM is centered/scaled, immediate block64, pitch1/Formant Off.

| Final experiment | Generated outputs | Measurement rows |
|---|---:|---:|
|15 fixtures,48/96k,six pitches plus unity; three modes on two vowels|798|798|
|20-source exact pitch x6 x3 formant modes x3 variants|1080|1080|
|60 direct-TSM ratios x3 variants, plus provided baselines|180|240|
|8 new banks x2 rates x6 pitches x3 variants|288|288|
|**Total final evidence**|**2346**|**2406**|

Earlier proposals, pilots, tonal gates and software tests are not added to this final count. Repeated supplied baselines are not new independent audio. The20 real references are mono44.1k; training references are not pooled. The journal binds source/configuration/binary/analysis identity and per-cell hashes; incomplete grids cannot publish a final report.

## Sustained partial balance

Mean normalized partial-energy error against analytic shifted oscillators, lower is better. Means use six nonunity pitches; dB-error reductions are not percentages of perceived quality.

| Fixture set / rate | Ordinary Fuzzy | Old guard | Bounded refinement |
|---|---:|---:|---:|
|Original harmonic+inharmonic,48k|5.107818|0.157781|**0.081926 dB**|
|Previous four banks,48k|3.778136|0.638466|**0.417561 dB**|
|Previous four banks,96k|3.767703|0.633340|**0.411723 dB**|
|Eight new banks,48k|3.689187|0.369310|**0.142935 dB**|
|Eight new banks,96k|3.679472|0.366628|**0.140276 dB**|

At each rate, the new banks give17 improvements,30 ties within1e-9 and1 slight regression versus the old guard. The loss is seed93275,+12st: +0.000689dB at48k and+0.000612dB at96k. The design was not changed afterward. This is synthetic sustained-content evidence, not general musical superiority.

Final nonunity synthetic old/new WAV identity:12/12 attack,36/36 noise and36/36 stereo cases. That does not guarantee all natural transients are unchanged.

## Natural pitch: onset problem remains

120 conditions, Harmonic preservation:

| Descriptor | Ordinary Fuzzy | Old guard | Bounded refinement |
|---|---:|---:|---:|
|Broad-envelope error,lower|5.215338|5.059962|5.060476dB|
|Onset correlation,higher|**0.876904**|0.873586|0.873586|
|RMS-shape error,lower|**0.870860**|0.878747|0.877602dB|
|Maximum raw peak|1.621937|1.695722|1.632235|

New-minus-old-guard onset is-1.38e-8, descriptive source-cluster95% interval[-0.000692,+0.000695]. RMS-shape delta is-0.001144dB, interval[-0.003156,+0.000191]. The maximum peak decreases but this is not all-condition peak or audible improvement. Off and Monophonic results are retained too. **The intended general onset repair was not achieved; do not promote on sustained results alone.**

## Direct TSM against provided Elastique

All60 target conditions, same source/duration, pitch1/Formant Off:

| Descriptor | Provided Elastique | Old guard | Bounded refinement | New wins/60 |
|---|---:|---:|---:|---:|
|Broad-envelope error|2.104070|1.940758|1.939720dB|43|
|Log-spectral distance|6.315414|6.023543|6.021181dB|48|
|Onset correlation|0.680285|0.730168|0.730285|50|
|RMS envelope shape|1.872449|1.319013|1.318834dB|56|

This **retains**, rather than dramatically extends, the previous guard's advantage on the supplied descriptors. New-minus-provided spectral delta is-0.294233dB, interval[-0.496097,-0.095550]; envelope delta-0.164350dB, interval[-0.315728,-0.028692]. Bootstrap4000draws,20source clusters,seed20260914; all ratios remain within each cluster. These are descriptive intervals, not multiplicity-corrected perceptual validation.

The supplied files do not identify SDK version/mode. No current native pitch engine was run, no per-file winning mode selected, and no new MOS generated. These numbers do not establish latest-native zplane superiority.

## CPU cost and tails

Same shared Linux VM,CPU0,three rotated sequential repeats;48/96k,stereo,32/64frames,six pitches. Each cell has800warmup+2000measured callbacks and four formant events per callback. No builds or corpus renders overlap the repeats. Each variant has144000measured callbacks. The existing fixed-delay bridge is used.

New versus old guard, median of24 paired cell medians: **mean CPU +3.96%; CPU p99 +7.96%**. This is a quality/cost tradeoff, not a speed optimization.

| Rate/block | Old guard worst-pitch median p99/deadline | New |
|---|---:|---:|
|48k/32|0.194315|0.214940|
|48k/64|0.134247|0.133421|
|96k/32|0.509829|0.525933|
|96k/64|0.303978|0.348804|

All raw cell p99 ratios are below1 in this run, but individual CPU deadline misses remain: ordinary110,old95,new72 per144000calls. New maximum individual CPU ratio is17.664873. The lower miss count is not proof of a tail fix; maxima differ and cause remains unknown. Algorithmic frame/FIFO underruns are0, which is distinct from CPU deadlines. Raw maxima/misses are retained. No portable hard-RT or physical root-cause claim.

## Local validation and hosted failure

- GCC14.2 C++20/23 and Clang17 C++20/23:21/21 CTests each.
- Matched-Clang ASan+UBSan, leak detection:21/21.
- Exhaustive selector test:188520 comparisons per run, plus boundary/alias/fallback/purity checks.
- Research Python:210/210; legacy TSM:6/6; no skips in this restored scope.
- Scheduled tonal/high-band gate:270/270, unchanged thresholds.
- Unchanged controls versus wide-v1 study:900/900 natural and532/532 synthetic WAV hashes match.

CTest covers pure C, allocation-free processing, linked stereo, reset, compact/fixed delay and immediate/cooperative/SIMD equality. Python scope is195 restored tests+10 prior overlay+5new study tests, not an assertion about every interrupted module in the complete remote branch. No fresh manual DAW/native-vendor qualification.

**Hosted CI remains failed/unverified.** New run34774181910 at a0a4403b returns GCC and Clang failures with steps:null after about2seconds. GCC log retrieval returns404 BlobNotFound; annotations are unavailable through the connector. No billing/quota/source cause is assumed. Existing gates were not disabled and local success is not reported as hosted success.

## Reproduce

Apply to a disposable bounded worktree, not production/main:

```sh
git apply research/experiments/fuzzy_coherence_guard.patch
git apply research/experiments/fuzzy_coherence_guard_alias_fix.patch
git apply research/experiments/fuzzy_phase_owner_refinement.patch
cmake -S research/cpp_pv_rt -B build-bounded -G Ninja \
  -DCMAKE_BUILD_TYPE=Release -DCMAKE_CXX_STANDARD=20 \
  -DCMAKE_CXX_FLAGS=-DBOILED_EGG_EXPERIMENT_COHERENCE_GUARD=1
cmake --build build-bounded -j2
ctest --test-dir build-bounded --output-on-failure
g++ -O2 -std=c++20 research/experiments/phase_owner_refinement_test.cpp -o build-bounded/owner-test
build-bounded/owner-test
# Build ordinary and old-guard worktrees separately, then:
OPENBLAS_NUM_THREADS=1 python research/eval_phase_owner_study.py --suite synthetic \
  --baseline /absolute/build-base --guard /absolute/build-old-guard \
  --refined /absolute/build-bounded --cache results/cache --output results/synthetic
# --suite corpus additionally requires --refs, --tests and --catalog.
```

SHA256 measurements: synthetic7e2b4f8a10d38e6bb0f4f072a18d2c409a87b0f322481a55cc43f1d4779d346b; corpus480e8ad152c192f3c5ba3a361545321482f926230ce999637c7d96249b5d76eb; new banks600f2dd1cc0037b03fbcba82f0722476ec5f6b10600dbe2bbe84e22b5f6dbe06.

The accompanying full report/bundle retains measured source, reproducible combined patches, failed proposal diffs/results, final CSV/JSON, CPU repetitions, hashes and logs. User audio/MOS and generated audio are excluded. The next unresolved algorithmic target remains mixed-transient phase behavior, not further unqualified claims from pure tones.
