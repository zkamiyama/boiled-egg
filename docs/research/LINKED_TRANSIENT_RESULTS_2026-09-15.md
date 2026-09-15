# Linked detection and shared-phase transient recombination — 2026-09-15 JST

## Decision

The known27ms opposite-channel deletion is repaired on the narrow-burst regression.
Across the new quiet-background stereo grid, all384 true event times are found,
including a30dB quieter channel. New mixed burst signals have much smaller event
placement errors. However, per-channel normalization introduces many false events
on tonal residuals; this detector is not ready for general use.

Shared full-band phase makes complementary add-back numerically exact. Localized
residual replacement reduces the preceding split/anchor method's coloration but
still underperforms unmodified full-band heap on the real-corpus mean spectral and
RMS descriptors. No universal quality winner or production promotion.

Draft PR14, research/linked-transient-recombination, is stacked on PR13. No main,
product DSP/API/ABI, existing formant/automation, state or plugin/UI changes. All
new renderers are offline constant TSM, pitch1. No native-zplane execution,
listening/MOS or complete realtime-pipeline qualification.

## Implementation

Protocol af6cd27e preceded measurements. The candidate was not retuned after new
mixtures or the actual corpus were evaluated. This is an independently implemented
engineering study, inspired by the prior HPTSM/phase-vocoder work, not a complete
reproduction of HPTSM, SELEBI or another published method.

### Detector ablation

Keep the previous1ms smoothed power envelope,5% maximum-relative prominence and
4x local51ms median test. Compare global40ms, global6ms, and6ms per-channel peak
selection followed by1ms fusion. Normalized channel prominence ranks events in a
fusion group; largest wins and earliest time breaks ties. A group is bounded by
its first candidate, so many sub-ms gaps cannot transitively merge a large span.
The same fused event map applies to all channels. No known event times are passed
to the detector or renderer.

The new C++ fusion kernel preallocates a bounded work array at construction and
validates the entire batch before modifying output. Sorting and grouping allocate
nothing in tested processing calls. The Python envelope/detector and full renderer
allocate and use whole-signal information; they are not a causal host backend.

### Recombination ablation

Let A_R be analysis, multiplication by a full-input-derived common phase rotation
R, and fixed synthesis/normalization. Once R is fixed this operator is linear:
A_R(h)+A_R(p)=A_R(h+p). The shared-long control verifies that identity rather than
letting the two separated components evolve independent phase histories.

The shared-linked mode replaces all of the percussive component with anchored
short-OLA transport. The localized mode replaces only q=g*p:

Y = A_R(x) - A_R(q) + transport(q).

The input gate is1 within half the protected radius, cosine-tapered to0 at the
radius. Radius is min(12ms,20% of adjacent/end gaps * min(1,T)), fixed by protocol.
No output-fitted gain, limiter, envelope matching or fitted time alignment. This
preserves add-back algebra, not necessarily the desired waveform after replacement.
All other separation, heap, grain and covariance-normalizer kernels are inherited.

Seven declared modes are locked, heap, independent_legacy, independent_linked,
shared_long, shared_linked and localized_shared. shared_long is a mathematical
control, not an independent audio-quality improvement.

## Evidence and counts

| Final study | Count |
|---|---:|
|20 supplied mono44.1k references x T=.5/1.5/2 x7 modes|420 outputs|
|6 analytical families x48/96k x T=.5/1/1.5/2 x7 modes|336 outputs|
|8 new mixtures x48/96k x T=.5/1.5/2 x7 modes|336 outputs|
|192 detector inputs x3 detectors|576 comparisons; not extra processed outputs|
|Primary processed-output total|1092|

New mixture seeds26091580..26091587 and spacings4,7,12,19,27,38,54,83ms were fixed
before confirmation. Detector inputs span both rates, eight spacings, relative
levels0/-20/-30dB, same/opposite channels and quiet/tonal backgrounds. Their true
event centers are scoring data only. The supplied20 reference files are used
unchanged and fingerprinted. No training archive or substitute recordings.

The entire real corpus has been studied historically. The old five-source pilot
membership is retained only for descriptive all20/other15 summaries; this iteration
performed no quality-driven pilot tuning before the full run. The other15 are not
a pristine holdout. No per-source winning algorithm is selected.

Natural RMS/flux/global-Welch-PSD/local-STFT definitions are unchanged from the
committed phase-edge study. Event errors compare the actual output to an analytic
waveform whose event centers move but local gate shape is retained. Per-channel
bounded/Voronoi windows avoid counting neighboring events twice. Mixture event
scores use the same1800Hz highpass on output and oracle, so those results describe
the high-frequency transient portion, not whole-signal tonal fidelity. Raw output
is not normalized or limited. Width error is absolute distance from the oracle,
not lower-is-always-better raw width. Detection uses one-to-one matching within2ms.

## Detection: the known failure is fixed, general selectivity is not

Quiet-background opposite-channel grid:48 conditions,384 expected event times.

| Detector | True positives | False positives | Missed | Recall |
|---|---:|---:|---:|---:|
|Global40ms|208|0|176|54.17%|
|Global6ms|248|0|136|64.58%|
|Per-channel6ms+fusion|384|0|0|100%|

Thus merely reducing the refractory interval is insufficient for the quieter
channel in this grid. Channelwise candidates recover it. The original27ms test
also finds8/8 rather than4/8 with a20dB quieter channel. Dual-mono duplicates fuse,
and detector channel permutation/global scaling/polarity regressions pass.

But on the opposite-channel tonal-background grid the new detector has327 true,
1088 false and57 missed events: recall85.16%, pooled precision23.11%. The same-
channel tonal-background grid has264 true,1660 false,120 missed. Across all192
signals:1223 true,2748 false,313 missed. Quiet same-channel close/weak events are
still missed (248/384). Global controls make no false detections in this particular
grid but miss many weak/close events. The normalized channel floor can amplify
irrelevant residual structure; do not present quiet-grid recall as general success.
CI independently reproduces every one of the576 TP/FP/FN count rows.

## New mixtures: timing improves with linked landmarks

Mean over48 source/rate/ratio cases; same highpass applied to output and oracle.

| Mode | Width error ms | Centroid error ms | Event-energy error dB | Outside-support fraction |
|---|---:|---:|---:|---:|
|Locked|8.038854|0.083919|5.493450|0.332600|
|Heap|9.919674|3.374290|4.754744|0.441933|
|Independent legacy anchor|0.564186|2.723427|0.763676|0.378574|
|Independent linked anchor|0.438933|0.067380|0.446926|0.007151|
|Shared linked anchor|0.438933|0.067381|0.446925|0.007151|
|Localized shared|0.768806|0.255251|0.548514|0.037209|

This is a genuine improvement for those generated transients, without oracle
landmarks. The localized gate sacrifices some event precision to change less of
the rest of the signal. It is not uniformly better than full replacement.
The narrow/staggered analytical families similarly improve, while20ms gates retain
detection-center errors. All1092 primary outputs have exact lengths, finite
samples and expected rate/channels. Unity and anti-phase controls pass.

## Actual music: coloration is reduced, not eliminated

Means over60 actual source/ratio conditions; lower errors/higher onset are better.

| Mode | RMS shape dB | Onset correlation | Global PSD shape dB | Local2048 shape dB |
|---|---:|---:|---:|---:|
|Locked|1.602618|0.453783|1.347236|4.613709|
|Heap|1.880296|0.434090|0.771756|4.782577|
|Independent legacy|2.116224|0.418311|2.500052|6.689065|
|Independent linked|2.037489|0.426805|2.437621|6.537903|
|Shared long|1.880296|0.434090|0.771756|4.782577|
|Shared linked|2.061774|0.422986|2.408766|6.496009|
|Localized shared|1.926622|0.428027|1.159063|5.152680|

Shared-long add-back differs from full-band heap by at most6.661338e-16 over the
actual60 conditions. This confirms the algebraic control, not the quality of
changing the percussive branch. Full replacement still has significant penalties
with either independent or shared phase: independent phase histories are not the
only problem to solve.

Localized versus the previous independent legacy anchor:
- RMS delta-0.189601dB,51wins/9losses, source-cluster95% interval[-0.281486,-0.096182].
- Global PSD delta-1.340989dB,58wins/2losses, interval[-1.700350,-1.000094].
- Local2048 delta-1.536385dB,55wins/5losses.
- Onset delta+0.009717,37wins/23losses; interval[-0.001902,+0.022596] crosses0.

Against unmodified heap, localized RMS still worsens+0.046326dB (45losses/60),
global PSD+0.387307dB (52losses/60), and local2048+0.370103dB (60losses/60).
Onset mean is-0.006063 and its interval crosses0. It is therefore not promoted.
The largest localized global-PSD loss versus heap is Synth_Bass_2/T2,+3.187204dB;
Triangle_02/T1.5 loses0.089339 onset correlation. Natural raw peak maxima:
heap1.871401,independent legacy1.568203,independent linked1.639646,shared linked
1.539932,localized1.522061. Lower aggregate maximum is not an all-condition peak
improvement or clipping guarantee.

Intervals use4000 source-cluster draws,seed26091591,with all ratios retained in
clusters; no multiplicity correction. Source-relative differences are not native
vendor errors, perceptual percentages or independent listening evidence.

## Verification and provenance correction

GCC14.2/Clang17 xC++20/23:2/2 isolated CTests each. Matched Clang ASan+UBSan,
leak detection enabled:2/2. New event fusion checks24173 exhaustive fused times,
empty/invalid/chain/capacity/input-purity and zero processing allocations.
All14 new Python tests pass, no skipped imports. Existing public spectral SDK
GCC20 regression:23/23. Only the event-fusion/phase kernels are allocation-free;
no new complete32/64-frame realtime benchmark or DSP promotion is claimed.

The first complete local study was followed by a build-matrix reconfiguration of
its build directory. The ELF hashes changed although computational source did
not. Those initial measurements are retained separately and are NOT associated
with the later binaries. Every case was rerun against immutable copied final
GCC20 libraries. All1092 final output PCM hashes and all576 detector rows match
the earlier run, but repeated runs are not extra independent evidence. Final
manifest dependencies match their files after the completed rerun.

Final libraries:
- phase heap SHA25671617b61df237dbe9b30947d3b2af64f18019ab6adc10dfa7b24ec1d0be847fe
- event fusion SHA2568cea5ef3b6f62f42b53b55befe00ebf348bece42762250fda65624eb2f2141e8

The immutable primary manifests bind all computational Python modules, both
libraries and original source WAV hashes. Journals bind every cell/payload; the
independent auditor checks the exact expected key grid and every CSV value
against those journals.120 additional inherited heap/legacy-anchor controls are
replayed from unmodified code and match final outputs exactly. They are not added
to the primary count.

## Hosted CI and self-contained publication

Validated checkpoint075b65a7e1c3b85a30446d81c2878c556e971978; tree
2a708aba9536bd047c20d566d709c7fd45fdee33. This result record is documentation only.
All three triggered PR workflows succeed:
- research-linked-transients34934725258:5/5 jobs, GCC/Clang20/23,14 Python tests,
  detector576 comparisons,synthetic336 outputs,ASan/UBSan and artifact upload.
- existing product ci34934725264.
- existing research-pv34934725256.

Downloaded artifact10382848072 ZIP SHA256
89af3bb127ba803c97f4ee9b63bb53c922351e2b65c5c5949a4d08fd6e5f65a4;
CRC and239 tracked hashes verify.234 locally present tracked files match exactly;
the five locally absent files are workflow/protocol/README/prior results, not
computational differences. Synthetic mergea63e788873c198cdcccdb0fe13bbc4108205df3d
has the same tree. A fresh build of that downloaded source passes2/2 CTests and
14/14 Python tests. CI detector TP/FP/FN rows agree576/576 with local final results.

Unlike the previous study's partial publication, all new code, evaluation, audit
and calibration files were committed successfully. No prior safety-blocked file
was republished through a different route. This new study uses only committed
legacy renderers/metrics and new independently scoped fixtures/checks. The prior
PR13's original overlay limitation is not claimed repaired.

## Reproduction and retained scope

See research/linked_transients/README.md for checkout-only build/test commands,
all four study suites and the auditor. Only the actual-corpus suite needs the
original20 reference WAVs; do not substitute other recordings. The delivery
contains the verified source, immutable measured kernels, final and superseded
measurements, journals, controls, logs, hashes and reports. It excludes user
recordings/MOS, generated audio, external SDKs and fonts.

Next scientific question: how to qualify per-channel transient evidence without
boosting stationary leakage, and how to replace only coherent localized event
content rather than a generic percussive residual. These are implications of
measured failures, not additional methods already solved in this pass.

Primary conceptual sources checked:
https://www.audiolabs-erlangen.de/resources/2014-SPL-HPTSM/
https://arxiv.org/abs/2202.07382
https://arxiv.org/html/2602.16421v1
