# Full-band anchor ownership: results — 2026-09-20 JST

PR #43; related #41/#19/#17, parent #15. Base main
18e74119694d869e01db22592941da887314795c, tree
ec0ee7895abbc0dd4f505d9e7164e4f89b4756fa. Protocol
3438d30533a0a1e2f9c7519759fd0e955fe21907 precedes new renders.

## Decision

Retain the isolated NRT kernel, calibration and negative result as a reproducible
research unit. **Do not promote this candidate or change the product default.**
Explicit anchor timing improves events, but the anchored full-band translation
imposes incompatible phase offsets on sustained bass. Every arm has zero joint
bass/event passes in the12 nonidentity correctly marked mixture cells. This
rejects this particular construction, not the possibility of satisfying both
properties with a different representation. Issue41 remains unfixed/open.

No separation or residual replacement, learned score, automatic detector,
source-dependent mode choice, PV fallback or synthesized ideal replacement is
used by the renderer. Prior PR13/14 losses are not reimplemented. Classical
WSOLA and nonlinear anchorpoint TSM provide context (Driedger/Mueller TSM Toolbox,
https://www.audiolabs-erlangen.de/resources/MIR/TSMtoolbox/); this ownership rule is
our bounded engineering adaptation, not an exact reproduction or priority claim.

## Implementation and scope

New research/anchor_wsola C++20/23 kernel and C-callable research header are NOT
installed product ABI. Existing298 files remain unchanged. Existing SDK/defaults,
state/IDs/latency/tail, plugins, transport and GUI are untouched. The new kernel
is an independent centered WSOLA/WOLA adaptation, not SDK-WSOLA PCM equivalence.
The two baseline arms call the actual unchanged C ABI via wsola_offline.py.

Mono48/96k, time1, constant pitch ratio[.5,2], <=3second normalized finite nonzero
input, <=16 supplied integer landmarks. No live/freeze/ramp/stereo/formant/job
cancellation API. Window4096/8192, hop W/4, search20ms, normalized correlation,
Hann overlap and64tap Blackman-sinc final resampling. Details are in the protocol
and source. Pitch0 has a declared exact-copy bypass, separately counted below.

free uses unconstrained similarity selection; snap inserts/locks grains around
marked output centers; owned also masks every conflicting contribution touching
6ms source or destination neighborhoods. A surviving contribution must have the
same source-minus-intermediate-output intercept as the owning mark. No surviving
weight means explicit error4, not a silent sample or hidden fallback. Invalid
marks, scope/budget failures and output arithmetic errors are distinct failures.
Trace includes chosen/expected centers, owner, correlation and masked counts for
successful renders. The API intentionally writes no PCM or trace on rejection.

Supplied markers are diagnostic/edited-offline input, NOT successful transient
detection. The runner keeps actual marks and true event metadata separate and
includes missing,2ms-late and false-marker controls. No natural corpus or MOS is
claimed in this first unit.

## Complete experiment and provenance

12 one-second families x2rates x3shifts(-12,0,+12) x5arms x3repetitions =1080
attempts,360 cells. Families and all exact parameters are in the protocol:
41/61/83/97Hz tones, harmonic61, sparse4k bursts, mixed61, dense83 with27ms pair,
missed61, offset61, false61 and53Hz/3k extension. These are fixed synthetic
extensions, not independent natural recordings. Three repetitions are numerical
reproducibility checks, not independent quality observations.

Initial full plan c7810534303843e883c200f6e71e02d6c21fd1646a843b195ec8c7837bbb4874
was registered before execution in Issue41 comment5746666463. After an assessor
failure-receipt repair, plan
5d243ad3fb326088edc8361cf1510d0bf2bc48ba20ae9b23caa7b411043377c2
was registered before the full rerun in comment5746717713. Inputs, marks,
waveform kernel, binaries, acoustic metrics and gates did not change.

Each run has1074 completed audio outputs plus6 explicit coverage refusals:
dense83/+12/owned at48/96k, three times each. All360 repeated status/PCM outcomes
are identical. Old/new1074 PCM, traces and acoustic metric records match exactly;
all6 refusal pairs match. All2148 completed-output file and decoded-PCM references
were independently read back and verified. execution_complete=false remains
visible:1080 attempts is NOT1080 successful renders.

## Fixed acoustic tests and results

Pure-tone clean pass requires <=5cent dominant-frequency error, <=1dB target
sinusoid amplitude error AND <=1% unexplained energy. Measurement interval is
.15-.85seconds, unrestricted dominant-peak estimator, no target-only search,
alignment or gain fitting. Pure counts below exclude false-marker controls.

Events use the same1kHz zero-phase fourth-order highpass on measured output and
an analytic local-resampling oracle, disjoint midpoint windows capped80ms,
energy centroid/5-95% width and event energy. Gates are absolute position<=1ms,
width<=1.2oracle and energy within3dB. Raw sparse-event results and separate
SDK-default-relative regressions are also retained. The comparison oracle has
unchanged event centers, carrier*pitch and sigma/pitch; it is an explicit property
choice for these generated bursts, not a unique ideal for arbitrary audio.

Mixture bass uses the same500Hz lowpass for diagnosis only and the whole.15-.85s
interval. It is not a perfect separated source or the signal supplied to the
renderer. Full raw RMS/peak/max sample step and out-of-event energy stay visible.

|Arm|Completed cells/72|Clean pure/24|Correct-marker event cells/24|Mixture bass/18|Joint mixture/18|
|---|---:|---:|---:|---:|---:|
|SDK default|72|8|8|6|6|
|SDK long_wide|72|24|8|16|6|
|free|72|24|8|15|6|
|snap|72|24|15|6|6|
|owned|70|24|22|6|6|

24pure cells include8identity cells.24event cells include8identity cells.
18mixture cells include6identity cells. **Every one of the6 joint passes in every
arm is identity; nonidentity joint passes are0/12.** Coverage refusals stay in
those denominators. owned's22 event passes do not erase default-relative stops:
4 further individual events worsen by the separate relative rule, plus2 rejected
cells. False/missing/late-marker results remain in the complete72 cells per arm.

### A concrete tradeoff: mixed61,48k,+12st

|Property|SDK long_wide|free|owned|
|---|---:|---:|---:|
|Bass dominant-frequency error,cent|-0.1611|-2.0596|-11.3661|
|Target sinusoid amplitude error,dB|-0.00961|-0.33379|-6.19215|
|Unexplained low-band energy fraction|0.001884|0.071883|0.752800|
|First event position error,ms|-18.2522|-8.4621|-0.4304|
|Second event position error,ms|-20.5383|-9.7905|-0.0763|
|First/second width,ms|26.25/17.7083|see raw record|1.8542/1.7500|

Oracle event width is1.75ms. owned event energy errors are+0.0775/+0.0148dB.
The -6.192dB number describes the fitted target-frequency component, NOT total
output loudness. Raw RMS is0.05557: much of the bass energy is redistributed
rather than simply attenuated. Whole-interval phase/sideband failures must not be
hidden by selecting a short locally clean interval.

False landmarks on otherwise pure61Hz,48k,+12, are a useful negative control:
free has -0.1263cent, amplitude -0.000803dB, unexplained energy0.0001285; owned
has -12.7895cent, amplitude -8.8395dB, unexplained energy0.86375. There is no true
attack to detect badly in this control: the anchor constraint itself damages the
sustained phase. It does not establish the causal explanation for every DSP loss.

## Mechanistic interpretation: local phase constraints

For source x(t)=A sin(2*pi*f*t), full-band local copy around source anchor a and
pitch resampling p impose, neglecting finite resampler error,

    y_a(t) = A sin(2*pi*f*p*t + 2*pi*f*(1-p)*a).

Two anchor neighborhoods generally require different tonal phase offsets. They
agree modulo2*pi only if f*(1-p)*(a2-a1) is an integer. With61Hz,p2,and.4second
spacing this is -24.4cycles, equivalent to -144degrees. Similarity alignment away
from anchors cannot remove both hard local phase constraints without changing
something else. This derivation is for the implemented translation/copy model;
it is NOT a theorem that bass accuracy and attack timing cannot coexist.

At a dense pair a,a+d with p2, a destination near2a+d maps under the first anchored
intercept to source a+d, and under the second to source a. The ownership rule
forbids each from copying the other marked neighborhood. With this grain support
and nearest-owner selection, no contribution survives in part of the overlap.
That explains the observed error4. We did not replace it with zeros, interpolated
output, relaxed6ms guards or a different algorithm after seeing the result.

A **post-screen analytical feasibility control**, saved separately as
analytic_feasibility.py/json, synthesizes a globally coherent target sinusoid plus
locally resampled bursts. It meets both gates18/18. That uses known generator
parameters and is ONLY an evaluator feasibility check, not a real-input renderer,
extra candidate success or predeclared confirmation result. It rules out treating
the observed zero joint passes as a general impossibility claim.

## Execution, memory and tests

Final3-repeat medians summarized across completed cells (seconds): SDK default
0.010376,SDK long_wide0.012451,free0.021459,snap0.017229,owned0.016871. owned timing
covers70/72 cells because2 rejected; it cannot be advertised as an all-input speed
win. SDK includes Python streaming and handle lifecycle; new-kernel timing wraps
one native call with internal allocation/resampling. These are not equivalent
kernel microbenchmarks or callback80%/1.25x realtime tests.

Maximum analytical native workspace estimate for this1-second grid is4,880,620
bytes; host buffers/allocator/process overhead are separate. Whole-process
peakRSS187,812KiB includes Python, analysis and accumulated results. This is not
per-instance owned memory. The first SDK cold construction33.862ms is retained
separately. Offline allocation is intentional; no no-allocation/hard-RT claim.

Local controls actually executed:
-55 unique Python methods,skip0 (11new plus44existing scoped controls).
-GCC/Clang C++20/23:7CTest each, all passed; Clang ASan/UBSan/leaks7/7.
-TSan independent-call thread test1/1; not same-instance concurrent lifecycle.
-Fresh unchanged spectral-ON SDK: complete26/26,inventory/JUnit checked,skip0.

Initial dense test expected success and failed with coverage error4. Its original
test/log is retained; before the grid the test was split into sparse repeat and
explicit dense rejection without changing synthesis. An early SDK call and ASan
build were interrupted; incomplete logs are retained and not counted as passes.

After the first full grid, injected failure of the SDK baseline caused assessor
KeyError on missing metrics. Original assessor/fault log remain saved. The repair
blocks unexpected failures with profiles=null; known coverage rejection is only
accepted at the exact preflight-known dense cells, never across arbitrary inputs.
The55th test checks all-failed and fabricated all-uncovered grids. Final1080
attempts were rerun after the guard; old timing is not relabelled.

## Identity and reproduction

Final measured kernel source SHA256:
761a8cb83ea16715dfff08262d7b255fa72fb11e43c00ef15725852355dfe9c4
Kernel ELF SHA256:
988a2f74fd54a1e8d7cf574fc03cb84824b00fd7f40a587f3f464ea2ffaf96f9
Final assessor SHA256:
b20c85a5c274bac67b453c4fef3d485458a375c41ca418375cb62b1acc601905
Final test SHA256:
37366568d240705ad293321083cea3d3f4e1d317773005e9a1f9f41e1606d785
Unchanged SDK ELF SHA256:
218abecb11273524ad41e42c97d93a7b88889c2a536ab6c74dee1a65ffb63cb8
Final local summary SHA256:
641ea76cb8bd782af3c240221c950526585e5320bc3b5dbaf22c17ed68e8994f

Python3.13.5,NumPy2.3.5,SciPy1.17.0,SoundFile0.13.1. Build and write evidence OUTSIDE
source, because plan hashes bind every source file present at preparation:

```sh
cmake -S . -B /tmp/anchor-sdk -DCMAKE_BUILD_TYPE=Release -DBOILED_EGG_ENABLE_EXPERIMENTAL_SPECTRAL=ON
cmake --build /tmp/anchor-sdk -j2
cmake -S research/anchor_wsola -B /tmp/anchor-kernel -DCMAKE_BUILD_TYPE=Release
cmake --build /tmp/anchor-kernel -j2
export PYTHONPATH=eval OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
python eval/anchor_ownership.py prepare --native /tmp/anchor-kernel/libanchor_wsola.so --sdk /tmp/anchor-sdk/libboiled_egg.so --output /tmp/anchor-plan
# Register printed plan SHA before the next run; do not reuse this machine's SHA.
python eval/anchor_ownership.py run --plan /tmp/anchor-plan/plan.json --plan-sha256 REGISTERED_SHA --output /tmp/anchor-results
```

Final CI/head/review/merge identities are recorded in PR43 and latest Issue
comments. CI uses its own plan/binary/timing identities. Product promotion,
automatic detection, real audio, formant/stereo/ramp, platform/DAW/hardware,
long-file job API and general naturalness remain unqualified. The next useful
design needs independent freedom for sustained-phase coherence and event timing;
merely improving the detector or increasing the window does not remove this
construction's phase constraint. New candidate tuning needs a new protocol/grid.
