# Explicit pitch/time ramps and phase-gradient comparison — 2026-09-15 JST

## Decision and scope

The agreed order is implemented in draft PR #10: configurable pitch ramps,
streaming time-ratio ramps, then an independent phase-gradient experiment.
The two ramp features are public opt-in spectral C/C++ APIs. The phase-gradient
renderer is an offline research comparison, not a selected production backend.
The ordinary WSOLA/default plugin interpretation remains unchanged. Main stays
`bfbb6fd0b8196a99a29f6fd4989a467deeeaf1af`; PR #10 is stacked on draft #9.
Issues #1 and #2 are not closed and no research-quality promotion is implied.

This resume found the implementation already committed at
`940d6b24d55e68fdcdfa64d4a144a1f3b33a1d2c`. It continued and revalidated that work,
not a new invention of those kernels. Initial CI artifact10363992163 passed ZIP
CRC/SHA256 and all193 tracked source hashes. This pass fixes a genuine evaluator
mutation, adds installed-C ramp coverage, completes local compiler/sanitizer/
corpus/phase/timing reruns and documents contracts/results.

New code commits: `62bdb199` (nonmutating correlation and two regressions) and
`81eacdef` (installed-C pitch/time API and disabled-backend checks). Operational
docs are `2affe39c` and `68fbd153`. Validated checkpoint is
`68fbd153b455793d3ed0ff901947961b65133d4c`, tree
`9a4385ce6d717e7f0d11ade5a67ce76e177a9665`.
This result-record commit changes documentation only.

## 1. Configurable pitch ramps

New installed header `boiled_egg/automation.h` provides a fixed32-byte event
record and additive `process_realtime_ramps`, `push_ramps` and automation-info
functions, plus header-only RAII methods. Duration is counted in accepted input
samples. Duration0 is a step; for N>0, the event sample is sample1 and sampleN
reaches the target. Linear-ratio and logarithmic-ratio curves are supported;
logarithmic pitch ratio means linear semitones. Both ratio/semitone target IDs
are accepted. Interrupted or repeated-target ramps restart from the current
value. Caller block length does not define the trajectory.

Entire batches (max256) are validated before DSP mutation. Equal offsets have
deterministic array order. The API has a single audio owner; it is not a UI
mailbox. Legacy event functions retain the previous10-ms behavior. A separate
same-toolchain replay confirms36/36 legacy analytic trajectories are identical
to the previously validated dynamic-editor source, not merely close in metrics.

The realtime interface keeps time ratio1 and the same full-pitch-range delay:
Transient2112/4160 samples at48/96k, General3648/7232. No delay change is caused by
explicit ramp duration. STFT response still spreads over windows; an exact input
timestamp is not instantaneous audible pitch response.

## 2. Streaming time-ratio ramps

CONTINUOUS_TIME is an additional explicit construction flag, requiring
CONTINUOUS_PITCH and streaming I/O. One accepted-input history drives two clocks:
W=sum(T) for output position, V=sum(T*p) for intermediate PV position. Synthesis
and resampling use those clocks consistently. Explicit curves use compensated
summation; the old default-ramp arithmetic is not silently rewritten.

The coupled safety envelope is max(currentP,targetP)*max(currentT,targetT)<=2
following each equal-offset group, with each ratio in[.5,2]. It deliberately
rejects some safe opposing trajectories rather than permitting unbounded
synthesis coverage. It is not an output limiter.

Backpressure consumes only the accepted prefix. An event at or after the first
unaccepted sample is not consumed; callers drain then rebase/retry that suffix.
Pull does not advance ramp state. Flush freezes controls where real input ended
and emits round(W) samples; padding must not complete an unfinished ramp. Reset
discards trajectory history and retains requested targets. Uncoupled time/pitch
UI setters and legacy state writes are rejected on variable-time handles;
formant mailboxes still work. Fixed-I/O DAW inserts do not implement variable T.

The installed-C test independently expects64 samples ramping T=1 to2 to have
W=96.5 and97 output samples at EOS. Existing plugins keep their original events
and state: no new GUI ramp-duration knob or reinterpretation of host points is
claimed. User-selected durations are currently available through C/C++.

## Fresh ramp validation

| Study | Paired cases | Generated outputs | Result |
|---|---:|---:|---|
|Analytic55/220/6200Hz,48/96k,2qualities,3policies,2curves,pitch/time|144|288|all pass|
|Supplied20 mono44.1k references,2qualities,3policies,2curves,pitch/time|480|960|all paired outputs identical|
|Legacy10-ms compatibility|36|72|all paired outputs identical|

Analytic and corpus compare block32 with257 on identical inputs. Independent
closed-form curves and long-double sums check W/V and final duration. There are
1008 settled pitch plateaus: max absolute error **0.128467 cents**, with unchanged
5-cent and1e-5 stereo controls. Max relative stereo error7.65439e-8. Max W/V error
3.36441e-8 samples in analytic tests and7.33417e-9 in the natural set. These are
control/settled-tone and integration tests, not whole-transition perceptual or
native-vendor accuracy. The20-file source hashes are recorded; no MOS is used.
Natural raw peak max1.619558,195/480 outputs above unity, retained without limiting.

C++ additionally checks20000 independent pitch samples,8000 independent time/P
integral samples,48 pitch-paired cases,25 time-paired cases (including deliberate
backpressure),20 half-sample duration boundaries, empty/short/EOS/reset behavior,
invalid groups and no-allocation processing. Old profile/state contracts remain.

## 3. Independent phase-gradient comparison

`research/phase_gradient/heap_integrator.hpp` independently implements the
magnitude-prioritized time/frequency trapezoidal integration idea in Algorithm1
of Prusa/Holighaus, *Phase Vocoder Done Right* (EUSIPCO2017; arXiv2202.07382).
The test covers513000 affine-field phase values,917916 bounded heap removals and
zero kernel processing allocations; a Python exhaustive-priority oracle also
checks random fields. No competing or copyleft implementation is imported.

The Python renderer uses centered gradients needing one future frame and is
OFFLINE. Its Hann windows, shared-channel phase, deterministic low-bin fallback,
unity bypass and Fourier resampling are explicit adaptations. No formant
preservation, variable-time automation or host/callback qualification is claimed
for this renderer. Only the C++ integration kernel is allocation-free.

All three variants have identical input/windows/hops/resampler: locked,
temporal-only trapezoid, and heap time/frequency integration. The fresh study
has72 analytical and180 natural outputs,252 total. These are additional to the
1248 primary new-ramp outputs: **1500 primary outputs**, excluding the72 legacy
compatibility rerenders. A model's generated output is not a new independent
source sample.

### Analytical means at48k, six shifts

| Descriptor | Locked | Temporal trapezoid | Heap |
|---|---:|---:|---:|
|Partial relative-energy error,lower|0.557228dB|0.072112dB|**0.007490dB**|
|Short-attack5-95% energy width,lower|7.160486ms|23.325281ms|**0.994823ms**|

At96k, partial errors0.556615/0.073155/0.007502dB and attack widths
7.219187/23.567104/0.980580ms. Only one partial bank and one gated-attack family
are used here; these are not broad perceptual evidence.

### Natural TSM,20 sources x ratios0.5/1.5/2.0

| Descriptor | Locked | Temporal trapezoid | Heap |
|---|---:|---:|---:|
|5-ms normalized RMS shape error,lower|**1.602618dB**|3.744826dB|1.880296dB|
|Positive RMS-flux correlation,higher|**0.453783**|0.295040|0.434090|
|Global normalized Welch PSD shape,lower|1.347236dB|2.269444dB|**0.771756dB**|

Heap improves global PSD in60/60 conditions versus locked, mean delta-0.575480dB,
descriptive source-cluster95% interval[-0.949568,-0.332933]. But RMS shape worsens
in43/60, delta+0.277678dB, interval[+0.132627,+0.447685]. Onset wins25/60, mean
delta-0.019693, interval[-0.041546,+0.002428]. The Ocarina_02 x2 case loses1.935585dB
RMS shape; Solo_flute_2 x0.5 loses0.190771 onset correlation. Losses are retained.

A global PSD can improve while local timing worsens. These source-relative
metrics are not errors against an ideal native stretch and differ from earlier
STFT/cepstral metrics in this project. Do not pool values from those definitions.
The20-source corpus has been used historically; it is not a fresh holdout.
Intervals use4000 source-cluster draws,seed20260915,no multiplicity correction.
The heap is therefore retained as research, not promoted as a universal upgrade.

The paired-summary script and its three extra calibration tests ran locally but
the connector blocked their GitHub create-tree request. They remain explicitly
local-only analysis files in the delivery, not represented as committed or CI
executed. Core implementation, primary study, primary tests and this report are
committed. The blocked write was not retried through a different GitHub route.

## Evaluator defect found and fixed

Initial research-pv run34884245117 failed its identity onset requirement:
0.9987337906777963 < existing0.999. This was reproduced locally. `_corr` used
`asarray` and in-place mean subtraction, which could modify caller arrays and
overlapping slices used by shift search. Three tests (the original plus input
purity/known-shift regressions) fail before the fix and pass afterward.

Commit62bdb199 centers into new arrays. The threshold, imported data and DSP are
unchanged. Read-only input, overlapping views, repeated shift search and known
5-frame delay are covered. Do not retroactively validate old evaluator output
with the corrected implementation. The fresh ramp and phase studies use their
own independent calculations and do not import this legacy evaluator.

## Practical callback capacity

After local builds/renders/tests, CPU0-affined wall-only runs covered24 settings:
48/96k,stereo,General/Transient,3policies,32/64frames,3repeats. Warmup is the
reported delay plus0.5seconds. Two explicit pitch commands per callback cover
steps,1sample and long linear/log ramps with interruptions; formant mailbox
updates are included. All per-state output fingerprints agree.

86400 steady calls plus67986 cold calls retained. Under the unchanged predeclared
rule max-over-states(best-of3)<=80%period, **24/24 pass**, worst ratio0.406473.

| Rate/block | General worst-policy state-best ratio | Transient |
|---|---:|---:|
|48k/32|0.138431|0.081195|
|48k/64|0.093612|0.068712|
|96k/32|0.406473|0.253125|
|96k/64|0.271949|0.161715|

Raw local period misses140/86400,maximum raw ratio62.235215,and46/72 actual full
steady runs below period are retained. State-best capacity is not p99/WCET or a
stitched successful continuous run. No empty-clock subtraction or fitted-noise
removal. This public-SDK benchmark does not qualify a whole DAW graph or the
variable-output streaming path as fixed-I/O realtime. Physical CPU-tail cause is
not resolved. Independent CI passes24/24 with worst state-best0.407433,zero raw
steady misses,72/72 full steady runs; it does not replace local outliers.

## Software and hosted gates

Local GCC14.2/Clang17 xC++20/23, spectral ON: **23/23 each**. Matched-Clang
ASan+UBSan with leak detection:23/23. Static spectral build:23/23. Default spectral
OFF:13/13. Installed shared-ON/shared-OFF/static-ON C11/C++ consumers: **3/3 each**.
Local TSan passes a realtime pitch owner and independent streaming-time owner
with concurrent UI formant updates and atomic target reads. No suppression.

Python: explicit-ramp7/7, existing dynamic12/12, phase-kernel7/7, legacy dataset3/3;
local-only paired summary adds3/3,32 distinct tests in this stated scope. This is
not all historical research modules. No tests skipped in these local suites.

All eight PR workflows at68fbd153 completed successfully:
- automation-ramps34916563555 (4compiler variants and address/thread instrumentation);
- ci34916563508 (existing product/ABI/hosts);
- spectral-backend-preview34916563507 (ON/OFF,install/static);
- dynamic-pitch-editor34916563492 (actual plugins/editor and dynamic checks);
- dynamic-plugin-sanitizers34916563496;
- research-pv34916563516 (previous failure repaired);
- dataset-tools34916563524;
- rt-measurement-audit34916563485.

Final artifact10376307865 SHA256:
`9d98e3f9acbf93cc6ecb7976583610894ee480cd0ab4c9f1cc16e377ff6125ea`.
ZIP CRC and196 tracked source hashes were verified. Its synthetic merge commit
50aadcdc57756762bafbf5e733fee203f1c74807 has the same tree as68fbd153. A fresh
build from that downloaded source again passes23/23 and produces the SAME local
library SHA256 as the library used in measurements:
`b25182a3246fb2cdf4b3e414b01b7b5ad26ee2b51e32c38f8a238e038d257e63`.
No manual DAW, native zplane output, blind listening or cross-platform GUI result
is added. The prior UI is unchanged; user-requested duration controls live in
the new SDK API, not a new plugin control panel.

## Reproduction and delivery

Build the opted-in spectral library normally, then run CTest and the installed
consumer project. Usage and backpressure contracts are in AUTOMATION_RAMPS.md.

```sh
cmake -S . -B build -G Ninja -DCMAKE_BUILD_TYPE=Release \
  -DBOILED_EGG_ENABLE_EXPERIMENTAL_SPECTRAL=ON
cmake --build build -j2
ctest --test-dir build --output-on-failure
OPENBLAS_NUM_THREADS=1 python quality/automation_ramps/study.py \
  --library "$PWD/build/libboiled_egg.so" --output results/analytic --workers 2
# For actual reference audio add --refs /absolute/reference/directory.
```

The accompanying bundle retains source snapshots, raw CSV/JSON, commands, failure
and passing logs, source/executable checksums, and explicitly local-only paired
analysis. Original recordings/MOS, fonts and external SDK sources are excluded.
The legacy replay's old library hash is recorded separately; cross-compiler or
cross-machine bit identity is not implied. Draft #10 and stable main remain
separate until the broader adoption gates are deliberately evaluated.
