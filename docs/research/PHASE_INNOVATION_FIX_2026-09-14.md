# Phase-innovation weighting: onset regression repair — 2026-09-14 JST

## Decision

The new isolated candidate reverses the bounded coherence guard's **mean natural-pitch onset regression** on the supplied20-source set. Its mean onset and broad-envelope descriptors both beat ordinary Fuzzy under Harmonic preservation. The direction also holds in15 sources excluded from this iteration's pilots and a separately selected12-source training-reference subset. This is not an all-condition or perceptual victory.

It sacrifices some of the previous aggressive guard's sustained-partial precision and adds CPU work. Rare deadline misses, native-zplane pitch acquisition and hosted CI remain unresolved. No default, product/main/ABI/plugin/state/fixed-delay change or automatic promotion was made.

## Implementation and provenance

Initial branch HEAD: c07edd06de91cda0082376d2beacdb40142c766d. GitHub comparison confirmed no ordinary runtime changes since8401ddaa. All222 prior baseline source hashes were verified. The bounded predecessor was restored from the prior measured-source bundle. This is a patched research working tree, not an assertion that branch defaults enable the guard.

| Commit | Addition |
|---|---|
|5c009459|Causal frequency-innovation reliability and circular interpolation helper|
|f91e160b|Independent numerical calibration|
|095303a1|Matching immediate/cooperative implementation patch|
|8e15d5f8|Frozen-design oscillator/training confirmation runner|
|38246e51|Paired source-cluster summaries with actual pilot membership|
|31f7044b|Cohort, artifact and paired-statistics regressions|
|02d55757|Dedicated isolated-build CI|

The old guard corrects an incompatible peak assignment after its flux holdoff, without checking the predictability of the current instantaneous-frequency estimate. The new correction weight is

`clamp(1 - abs(wrap((current_IF - previous_IF)*hop))/hop/(pi/FFT_size), 0, 1)`.

The ordinary and corrected rotations are interpolated on the shortest phase-circle arc. This is an engineering reliability measure, not a calibrated probability or an automatic profile selector. The bounded neighbor selector, onset holdoff, magnitudes, windows/hops, shared-channel rotations and formant policies remain unchanged. Previous frequency is read before replacement; reset clears both frequency/reliability state. One preallocated bins-float vector is added:2052bytes atFFT1024 or4100bytes atFFT2048, excluding allocator overhead. No new FFT, lookahead, waveform crossfade, output normalization or limiter.

The helper extraction reproduces30/30 prototype pilot WAV hashes. Applying the new patch to the measured bounded predecessor exactly reproduces the measured two runtime files and helper. Delivery includes exact source snapshots and a combined patch for the8401 baseline; do not apply the combined patch over an already patched guard.

## Selection and evidence integrity

Actual pilot sources are sorted indices with index%4==1: Ardour_2, Female_4, Male_6, Rock_4 and Triangle_02, six pitches/Harmonic. Naive resets, approximate group-delay resets, waveform mixing, alternate correction-strength/support rules and smaller hops did not achieve the intended pilot tradeoff; their diffs and results are retained. These are exploratory ablations, not reproductions of a published method.

The design was frozen after these pilots and before the full corpus, synthetic and training confirmations. No further tuning followed confirmation. The inherited owner-study CSV's `split` column describes its older index%4==0 split, NOT this iteration. Raw files are retained unedited; the new summarizer explicitly uses the actual five-source set and tests that the stale column cannot drive selection. The15 remaining sources are within-iteration confirmation, not a pristine holdout: the20-source corpus has been used historically.

Eight new oscillator seeds120000–120007 were fixed before rendering. Twelve references were selected before rendering from the supplied88-source training archive, four per original music/solo/voice category with Random(20260914). They do not overlap the20 test names;10 are stereo and2mono. The archive has been studied previously, so it is not a never-used population.

| Final study | Generated outputs | Rows |
|---|---:|---:|
|15 analytical fixtures,48/96k,six pitches plus unity,three variants|798|798|
|20-source exact pitch x6 x3 formant policies x3 variants|1080|1080|
|Direct TSM60 ratios x3 variants, plus provided baseline|180|240|
|Eight new banks x2 rates x6 pitches x3 variants|288|288|
|12 separate training references x6 pitches,Harmonic,x3 variants|216|216|
|**Total**|**2562**|**2622**|

Pilots and270-case tonal gates are excluded from this total. All rendered outputs have finite samples and exact expected frames/rates/channels. Inputs are identical within comparisons; input/renderer/analysis hashes and complete grids are checked. Exact pitch uses centered/scaled, scheduled SIMD block32; direct TSM uses immediate block64,pitch1,Off. No fitted shift/DTW or output normalization. An interruption after57 corpus journal cells was resumed with identical configuration, then all180 cells completed. Cached reuse is not additional evidence.

Raw names: baseline=ordinary Fuzzy, guard=bounded predecessor, refined=innovation candidate. Original raw summaries are not relabeled with newer executable identities.

## Natural pitch: mean regression reversed

120 conditions,Harmonic:

| Descriptor | Ordinary | Bounded predecessor | Innovation |
|---|---:|---:|---:|
|Onset correlation,higher|0.876904|0.873586|**0.879516**|
|Broad-envelope error,lower|5.215338|**5.060476**|5.109378dB|
|RMS-shape error,lower|**0.870860**|0.877602|0.874343dB|
|Maximum sample peak|1.621937|1.632235|1.605265|

New-minus-ordinary onset is+0.0026114, descriptive95% source-cluster interval[+0.0005887,+0.0049607],76wins/38losses/6ties. Against the predecessor:+0.0059299, interval[+0.0031853,+0.0088176],79wins/35losses/6ties. Envelope error improves versus ordinary by−0.105961dB,93wins/21losses/6ties, but loses about0.0489dB of the predecessor's benefit. RMS shape remains0.003484dB worse than ordinary; its interval crosses0.

Actual15-source confirmation: Harmonic onset versus ordinary+0.0032452, interval[+0.0006960,+0.0062390],62wins/28losses. Against predecessor:+0.0071779, interval[+0.0039666,+0.0106995],64wins/26losses.

Full-set onset also improves under Off (ordinary0.869052,predecessor0.870119,new0.874208) and Monophonic (0.872910,0.870312,0.874684). The Monophonic confirmation-only interval versus ordinary crosses0; do not present identical evidence strength for all modes.

Separate12-source training subset: Harmonic onset0.874524/0.870142/**0.876133** (ordinary/predecessor/new). Versus predecessor:+0.005992, interval[+0.002000,+0.010596],50wins/22losses. Versus ordinary:+0.001609,43wins/29losses, but interval[−0.000657,+0.003626] crosses0. Envelope errors5.243549/5.076049/5.115754dB. Do not pool this subset with the20-source test set.

Counterexamples remain. Brass_and_perc_9 at−7st loses0.028725 onset correlation against ordinary. Child_4 at+3st worsens RMS-shape error by0.090837dB. Training maximum peak increases from predecessor1.176939 to1.259323. Test-set maximum reduction is not a universal peak improvement.

Intervals use4000 source-cluster draws,seed20260914,retaining pitches within sources; no multiplicity correction or perceptual-significance claim.

## Sustained content: tradeoff retained explicitly

Mean partial-envelope error against analytical shifted oscillators:

| Set/rate | Ordinary | Bounded predecessor | Innovation |
|---|---:|---:|---:|
|Original harmonic/inharmonic,48k|5.107818|**0.081926**|0.540640dB|
|Previous four banks,48k|3.778136|**0.417561**|1.064534dB|
|New eight banks,48k|2.487071|**0.152852**|1.219338dB|
|New eight banks,96k|2.486619|**0.153800**|1.210999dB|

Some steady mixtures also have changing local frequency estimates, so correction weakens. The new candidate remains substantially better than ordinary Fuzzy but worse than the aggressive guard on these banks. It is not a Pareto-dominant replacement or a percentage improvement in perceived quality. Twelve attack,36noise and36stereo nonunity synthetic cases have identical whole-WAV hashes across all three variants; that is fixture-specific.

## Provided Elastique direct TSM

60 target conditions,same source/duration,pitch1,Off:

| Descriptor | Provided Elastique | Bounded predecessor | Innovation | New wins/60 |
|---|---:|---:|---:|---:|
|Envelope RMSE|2.104070|**1.939720**|1.991920dB|41|
|Log-spectral distance|6.315414|**6.021181**|6.157028dB|42|
|Onset correlation|0.680285|**0.730285**|0.729491|49|
|RMS-shape error|1.872449|1.318834|**1.318068dB**|57|

All four new means beat the supplied baseline, but spectral/envelope difference intervals cross0. Onset delta+0.049206 interval[+0.031153,+0.068991] and RMS delta−0.554381dB interval[−0.718509,−0.403967] remain favorable. The supplied SDK version/mode is unknown. No native-pitch result, best-profile selector, MOS transfer or overall sonic-superiority percentage.

## CPU cost and remaining tails

Same VM/CPU0,three rotated sequential repeats;48/96k stereo,32/64frames,six pitches,four formant events per callback.800warmup+2000measured callbacks per cell,24cells/repeat,144000 measured callbacks/variant. No build/render/test work overlaps timing.

Against predecessor, median paired changes are **mean CPU+4.19%,p99+10.01%**. Against ordinary:+10.39% mean,+26.81% p99. This is not a CPU optimization.

| Rate/block | Predecessor worst-pitch median p99/deadline | Innovation |
|---|---:|---:|
|48k/32|0.158109|0.176963|
|48k/64|0.113892|0.127036|
|96k/32|0.511809|0.585870|
|96k/64|0.334592|0.338333|

All raw cell p99 ratios are below1 in these repeats. Individual CPU misses:ordinary30,predecessor35,new58 per144000callbacks; new wall misses61. Largest new individual CPU/deadline ratio8.854955. Algorithmic frame/FIFO underruns0 is not CPU deadline safety. No physical tail mechanism was isolated or fixed; previous VM-wide control evidence does not prove every new miss environmental.

## Validation and unresolved external gates

GCC14.2 C++20/23 and Clang17 C++20/23 each pass21/21 CTests. Matched-Clang ASan+UBSan with leak detection:21/21. New helper:116845 comparisons plus initialization/alias/branch-cut/rate-scaling checks across tested toolchains. CTest covers pure C,no-allocation,reset,fixed/compact latency and immediate/cooperative/SIMD consistency.

Restored Python scope:215/215 research+6/6 legacy,no skips. This is210 restored tests plus five new tests, not every interrupted remote module: the separately fetched native-contract and earlier adaptive-NSGT modules are outside this restored local scope. No new manual DAW/native-vendor qualification.

Scheduled CLI quality:270/270,unchanged thresholds; max low-tone error2.153085cents,min target/spur22.816859dB,max high-band p95 ripple0.145946dB.

Hosted run **34790731313** at02d55757 failed GCC/Clang immediately,with `steps:null`; GCC check103814326513 lasted about1second. Annotation retrieval is unsupported by the connector; readable failure details are unavailable. No billing/quota/source cause is inferred, no gate disabled. Local success is not hosted success.

Native zplane outputs remain unavailable. Official REAPER acquisition was retried but failed from this environment. No native engine ran or vendor synthetic scores were invented. Ultimate physical CPU-tail attribution and hard-RT qualification remain open. The measured mean-onset issue is addressed, not every musical case or all remaining platform issues.

## Reproduce

In an isolated worktree:

```sh
git apply research/experiments/fuzzy_coherence_guard.patch
git apply research/experiments/fuzzy_coherence_guard_alias_fix.patch
git apply research/experiments/fuzzy_phase_owner_refinement.patch
git apply research/experiments/fuzzy_phase_innovation.patch
cmake -S research/cpp_pv_rt -B build-innovation -G Ninja \
  -DCMAKE_BUILD_TYPE=Release -DCMAKE_CXX_STANDARD=20 \
  -DCMAKE_CXX_FLAGS=-DBOILED_EGG_EXPERIMENT_COHERENCE_GUARD=1
cmake --build build-innovation -j2
ctest --test-dir build-innovation --output-on-failure
g++ -O2 -std=c++20 research/experiments/phase_innovation_guard_test.cpp -o build-innovation/innovation-test
build-innovation/innovation-test
```

Build ordinary and bounded-predecessor trees separately. `eval_phase_owner_study.py` uses baseline/guard/refined to identify those three builds. Use `eval_innovation_confirmation.py` for the frozen new-bank/training selection, and `summarize_phase_innovation.py` for this iteration's actual pilot/confirmation split. Raw legacy annotations remain untouched.

Delivery retains source snapshots,patches,failed proposals,complete measurement CSV/JSON,CPU repetitions and logs. User audio/MOS,third-party native executables and rendered audio are not redistributed. The longer artifact report includes reproduction commands and detailed method limits.
