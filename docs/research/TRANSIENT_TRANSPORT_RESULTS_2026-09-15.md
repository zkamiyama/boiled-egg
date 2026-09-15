# Complementary transient transport — results, 2026-09-15 JST

## Decision

Implemented and evaluated complementary component processing and local waveform
transport, rather than another phase-only correction. Anchored transport preserves
the analytical isolated2ms gate's width and energy at the tested ratios. Short
OLA also improves attack localization on new mixtures. **No variant is a general
improvement on the actual music corpus.** Spectral coloration and envelope losses
remain; the anchor detector additionally suppresses neighboring stereo events.

The detector failure is isolated with a post-hoc known-landmark experiment, not
claimed repaired in the frozen candidate. All alternatives remain research.
No main/product DSP/ABI/plugin/UI/state or current pitch/time-ramp change. This
is offline constant TSM, pitch1, without formant preservation, native-zplane
outputs, human listening/MOS or full-pipeline realtime qualification.

Draft PR13: research/transient-component-transport, based on
58f1c6b7c6e34967cad92f63cf6f6897d0f9b6fa from phase-edge-integration.
The base's three workflows were successful when checked.

## Implementation and research basis

Driedger/Mueller/Ewert's long-PV/short-OLA harmonic-percussive TSM motivates the
independent component split. SELEBI(2026) motivates investigating magnitude/phase
time localization jointly, but this implementation does not reproduce its NSDGT
construction. No competitor/reference implementation was copied.

The separator uses2048 Hann/hop256 at44.1/48k (doubled96k), linked channel-power
magnitude,31-frame/31-bin medians and a squared complementary mask. Harmonic
synthesis is normalized OLA; percussive is x-h, ensuring exact complementary
reconstruction before processing. The long branch uses the inherited2048
locked or heap PV; percussive OLA uses256-sample Hann-squared grains and64-sample
synthesis hop at48k, doubled96k.

Anchored variants detect energy peaks from1ms-smoothed/downsampled percussive
power,40ms spacing,5% maximum prominence and4x the local50ms median. A monotone
output-to-input map passes through(T*u,u), with local slope1 around landmarks.
Protected radius is12ms clipped to20% neighboring/end gaps times min(1,T).
This preserves local grain time scale, not all possible stereo transient times.
C++ map interpolation preallocates nothing and uses bounded binary lookup;
the Python renderer still allocates and consumes whole-signal data.

The first six-mode, five-source pilot was negative. An explicitly recorded
addendum then fixed two more modes before confirmation: duplicate-aware
unit-power synthesis weights. For each destination sample, group overlapping
weights by equal source-index offset and divide by
sqrt(sum_G(sum_{j in G}w_j)^2). This treats duplicates coherently and distinct
indices as uncorrelated, matching a white-noise covariance model. It uses no
measured input/output gain or oracle target. Colored residuals and tonal leakage
need not satisfy that model, so power preservation is not a universal guarantee.

Eight fixed modes are all retained: locked,heap,split_heap_long,
split_locked_ola,split_heap_ola,split_heap_anchor,split_heap_power,
split_heap_anchor_power. The two ordinary baselines call the existing renderer
without modifying its math. split_heap_long separates components but uses long
heap PV for both, isolating a penalty that can arise before short-grain synthesis.

## Commits and exact source

| Commit | Change |
|---|---|
|0107cb7e|Pre-evaluation protocol|
|b87df923|Bounded no-allocation anchor map|
|0070f223|Initial six-mode component renderer|
|5f8c0402|Negative-pilot record and fixed power-normalizer hypothesis|
|0e5bd535/e368dcc2|C bridge and validated Python binding|
|3f48a8d4|Duplicate-aware OLA normalization|
|26248cb4|CMake, independent C++ and Python numerical tests|
|346a2573|Dedicated kernel CI|
|46de66d9|Scope, reproduction and publication-limit README|

Validated code checkpoint:346a257378e67f38c43d5728d8f6753300f93694.
Tree:11b5d1e1f3c9799e2554d490b82a8c120a71350d. Subsequent README and this record
are documentation only. The working base came from the prior verified212-file
CI source. Final CI archive verifies223 tracked hashes. Every locally present
tracked file matches; four absent local files are the new workflow, protocol,
addendum and prior result document, not computational source differences.

## Protocol, inputs and counts

Pilot: Ardour_2,Female_4,Male_6,Rock_4,Triangle_02. Initial six-mode pilot90 outputs
preceded the power addendum. No further changes were tuned after remaining-source
or new-mixture confirmation began. The other15 sources are withheld only within
this iteration: the20 actual mono44.1k references have been reused historically.
No substitute recordings, training archive or vendor outputs were used.

| Primary evaluation | Outputs |
|---|---:|
|20 actual references x T=.5/1.5/2 x8 modes|480|
|7 analytical fixtures x48/96k x T=.5/1/1.5/2 x8 modes|448|
|8 new mixture seeds x48/96k x T=.5/1.5/2 x8 modes|384|
|Total|1312|

Seeds26091520..26091527 are fixed mixed tonal/noise-burst stereo signals with
27ms staggered channel events. They are additional generated fixtures, not new
natural recordings. The initial90-output pilot and12 post-hoc oracle-landmark
renders are excluded from the primary total. A supplementary120-control replay
attempt timed out before publishing a result; no completed identity count is
claimed for that attempt. Existing direct baseline routing is unchanged.

All primary outputs have finite samples and exact rounded lengths, rates and
channels. Inputs and computational files/binaries are fingerprinted before and
after, cache cells have identity/payload hashes, final grids reject missing or
duplicate cells. One stale prose note in raw summaries says six modes; manifests,
mode rows and totals contain all eight (six originals plus two additions). Raw
files and measured script hashes are retained rather than silently edited.

Natural metrics retain prior5ms normalized RMS shape, positive RMS-flux onset,
global normalized Welch PSD and512/2048/8192 local-STFT descriptors. These are
source-relative descriptions, not ideal-waveform/vendor errors. No fitted shift,
DTW, raw gain normalization or limiter. Analytical targets scale event centers
but retain gate durations and local waveform energy; width error is distance from
that target, not a lower-is-always-better raw width. Mixed-event measurements use
the same1800Hz highpass on both candidate and oracle. Retain raw peaks and failures.

## Natural music: the new candidates regress

Mean over60 source/ratio conditions; lower errors and higher onset are preferable.

| Mode | RMS shape dB | Onset | Global PSD shape dB |
|---|---:|---:|---:|
|locked|1.602618|0.453783|1.347236|
|heap|1.880296|0.434090|0.771756|
|split_heap_long|2.067723|0.422046|1.825976|
|split_locked_ola|1.953040|0.432068|4.066545|
|split_heap_ola|2.142794|0.428347|4.003974|
|split_heap_anchor|2.236770|0.423610|2.770748|
|split_heap_power|1.966327|0.435041|3.660984|
|split_heap_anchor_power|2.116224|0.418311|2.500052|

Power normalization improves the simple-OLA variant's mean power/shape behavior,
but does not recover the full-band heap spectrum. Against heap, split_heap_power
RMS worsens+0.086031dB,95% descriptive interval[+0.013487,+0.164809],45losses/60;
PSD worsens+2.889228dB in60/60. Its onset difference+0.000950 crosses zero and
reverses to-0.005878 on the15-source confirmation subset. Do not select the
favorable five-source pilot as evidence of general onset improvement.

Anchor+power versus heap: RMS+0.235928dB (53losses/60), onset-0.015779
(37losses/60), PSD+1.728296dB (60losses/60). split_heap_long also worsens PSD60/60
by+1.054220dB. This shows the real-audio penalty is not confined to short-OLA
weight attenuation; decomposition and independent component synthesis also need
attention. It does not identify a single universal physical cause of coloration.

Examples: Child_4/T2 with plain heap+OLA loses1.052574dB RMS; Triangle_02/T2
loses11.667415dB global PSD shape. Anchor+power/Female_2/T.5 loses0.133926 onset.
Maximum natural sample peaks:heap1.871401,locked1.182040,plainOLA1.446611,
power1.605826,anchor/anchor+power1.568203. None is silently limited.

Intervals resample source clusters4000 times,seed260915,keeping ratios together;
no multiplicity correction. The global-PSD change is not a perceived-quality
percentage. No new native or derived-Elastique benchmark is inferred.

## Analytical successes and remaining failures

At48k, averaged over T=.5/1.5/2, the isolated2ms gate has oracle5-95% energy width
0.945523ms. Whole-gate duration and energy support are distinct from this width.

| Mode | Absolute width error ms | Absolute event-energy error dB |
|---|---:|---:|
|locked|9.182570|6.577616|
|heap|0.160309|2.444152|
|split_heap_ola|0.834024|4.450327|
|split_heap_power|0.832241|4.054215|
|split_heap_anchor|0.000000|less than1e-14|
|split_heap_anchor_power|0.000000|less than1e-14|

For this fixture, the input-derived anchors preserve the intended width, timing
and energy to numerical accuracy; oracle landmarks are NOT used in this primary
result. Longer20ms gates retain width/energy but have mean centroid error0.667ms
because detected energy peaks differ from nominal event centers. Success is
fixture-specific, not proof of natural-transient transparency.

New8 mixtures, both rates and nonunity ratios:

| Mode | Width error ms | Centroid error ms | Event energy error dB | Outside-support fraction |
|---|---:|---:|---:|---:|
|locked|8.056417|0.062940|5.468513|0.335971|
|heap|15.317832|5.170693|5.967956|0.493523|
|split_heap_ola|1.884480|0.063083|2.658955|0.036686|
|split_heap_power|1.884741|0.063029|2.680360|0.036718|
|split_heap_anchor|1.028154|3.732679|1.314985|0.495395|
|split_heap_anchor_power|1.028385|3.732347|1.384100|0.495383|

Short OLA reduces event smearing/leakage here. Anchors give narrower, more
energetically faithful bursts but put some at the wrong time. Do not equate
smaller width error with overall improvement. Tonal banks at48k have partial
error about0.010833dB for heap and0.0243dB for the split short-OLA variants;
no new sustained advantage. Worst measured55Hz frequency error0.010414cents
is a no-pitch-change TSM check, not pitch-shifter accuracy. Primary unity max
absolute reconstruction error1.6653345369377348e-16.

## Specific detector failure isolated after confirmation

The staggered-stereo fixture contains8 events, adjacent-channel spacing27ms.
The fixed40ms minimum detector spacing keeps only4/8 within1ms. At48k/T2,
missed-event inverse-map placement errors reach11.428571ms. This is a definite
failure of the current detector/map combination, not phase-kernel arithmetic.

A labeled post-hoc diagnostic injects the8 known source landmarks into the
otherwise unchanged anchored renderers. Across48/96k and three ratios,12 outputs:
anchor mean centroid error4.430001e-7ms, anchor+power9.950027e-11ms;
mean width errors2.323389e-6/4.980397e-10ms; outside-support fractions0.
This isolates the detector's role in this case. **The real algorithm does not
have these landmarks, and this is not a corrected candidate or independent
confirmation.** No detector threshold was retuned after seeing the results.
The natural-music decomposition/phase problem remains separate.

## Local and hosted validation

- GCC14.2/Clang17 x C++20/23:2/2 isolated CTests each.
- Matched Clang ASan+UBSan, leak detection enabled:2/2.
- Anchor map:102800 independent long-double interpolation checks; invalid batches
  leave output untouched; empty query accepted; zero processing allocations.
- Local Python16/16: complement/read-only, monotone unit-slope knots,20560 native
  vs independent NumPy queries, short/odd/silence/duration/identity, anti-phase,
  channel permutation, determinism, oracle gain/delay/width calibration and a
  brute-force duplicate-weight covariance oracle. No skips.
- Unchanged public spectral SDK root regression:23/23.

At346a2573 dedicated kernel workflow34931113261 passes5/5 jobs. Existing product
ci34931113273 and research-pv34931113290 also pass. Downloaded artifact10382105517:
ZIP SHA25630818af0376f262a3790cf55cefdd186c0c21f5c384f01cecee3a70ba2190711;
CRC and223 tracked source hashes verify. Synthetic mergef409642757e1ca4cba7394816f6ffed86e1ff0d9
has the same11b5d1e1 tree as the code checkpoint. A fresh build of the downloaded
checkout passes2/2 CTests. These are kernel/product-regression successes, not
full-Python-study CI or offline-renderer host qualification.

## Explicit partial publication

A create-tree call containing fixtures.py,metrics.py,study.py was safety-blocked
by the connector. It was not retried by another route. Those measured files are
local-only in the delivery. test_transport.py is committed but requires this
local overlay, so it cannot run from the checkout alone. The dedicated workflow
honestly tests only the standalone kernels. This limitation is not hidden by
skipping missing imports or claiming16 Python tests passed in hosted CI.

Local-only summary/diagnosis/control-replay scripts and all raw results are also
included. Primary measured script notes still mention six modes, while the
explicit eight-mode manifest/grid is authoritative; raw data are not altered.
The code README documents which commands are checkout-only and which need the
local evaluation overlay. No external SDKs, fonts, user recordings/MOS or
rendered audio are redistributed in the bundle.

Primary result CSV SHA256:
- pilot_final a4583369fb0a927cba4c6bfd8bbdc29eae596cc0015d9252ff96e446b5af6ca9
- confirmation d85e9a2d51cf52bb9d46925651bcabd4149d803b6beb494828b88b55fe3d1a38
- synthetic c66e9d07a056dc9847af01a0a44069734a46ea4359eeedffa1dfdba9062c3c13
- mixtures 63dae56bbba83fd4bc23b7b547bbff9209f333d068d74302852e48059a194bde

## Next implication, not an implemented result

Do not keep increasing STFT projection iterations or rely on isolated-attack
wins. The next specific target is a channel-linked detector that retains nearby
independent events, together with recombination that preserves the relationship
between separated components. Its evaluation needs new event spacings and new
mixtures after freezing the design; oracle landmarks above are not a deployable
solution. A decomposition-free localized analysis remains a distinct alternative.

Primary sources:
https://www.audiolabs-erlangen.de/resources/2014-SPL-HPTSM/
https://arxiv.org/html/2602.16421v1
