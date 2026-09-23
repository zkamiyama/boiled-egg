# PV first-stage FFT batching — protocol, 2026-09-24 JST

Issue71, parent67/69/15. Base d4093d87aba960a1965b1243f6e685a23420ff25,
tree6bb4857396279588d44ea64fd2b0f2a90b5eb6c2. PR64/68/70 are already integrated.
The hypothesis and scope were posted in Issue71 before implementation. This file
precedes all full audio/cost measurements; the first local numerical controls
have already executed and are not described as later blinded measurements.

## One bounded edit

In fft_plan::advance, length-two butterflies are independent, scalar operations
in the old traversal. Batch only their bookkeeping within the supplied budget.
Retain the stored complex root and the same multiply/add/subtract expressions,
including signed zero. Do not replace multiplication by a root of one with copy.
For every supported pause the data, cursor fields, remaining work and return value
must match the immutable predecessor bit for bit. Subsequent FFT stages, inverse
scale, scalar/SIMD selection, coroutine yield points and scheduler work budgets
are unchanged. No new state, sample buffer, table, allocation or public API.
The immediate non-cooperative transform is unchanged.

## Numerical controls

Compile the actual old fft.cpp in a renamed namespace, checking its source/header
SHA256 against the pinned predecessor. Compare 2..16384-point transforms, both
directions, scalar/SIMD, random/impulse/zero/signed-zero inputs, first-stage boundary
budgets 0/1/2/3/127/128/129/4096 and mixed budgets. Compare complete arrays and every
cursor field at each selected pause, not only final output. Small full-prefix
cases use budgets1/2/3; large full-prefix cases use127/128/129/4096/mixed to bound
quadratic test cost. Verify no allocation in advance and independent cursors on a
shared immutable plan. Reject an altered reference. Existing public formant,
noalloc, reset, partition and automation tests are retained.

## Full SDK measurement (fixed before running)

Reuse quality/pv_ring and quality/formant_detail specifications, public renderer,
fixtures, acoustic metrics and receipt validator; do not build a new audio scorer.
The thin experiment driver must label the actual baseline and this experiment,
not silently inherit the ring experiment's revision. All source, linked libraries,
runner, input and environment identities are bound before execution.

Quality: four known families x48/96k x+/-12st xdetail0/1 xthree repeats xold/new
=192 outputs. These are existing synthetic regressions, not a natural-voice holdout.
Require exact paired PCM, metadata, acoustic diagnostics and repeated outcomes.

Cost: two-second vowel120, stereo R=-0.5L when enabled,48/96k xmono/stereo x32/64
x+/-12st xstreaming/fixed-I/O xdetail0/1=64 settings. Alternate old/new, three
repetitions, fixed permitted CPU, same executable and actual loaded library check:
384 outputs. Retain every service time, construction, flush, complete input-block
count, p99/max, actual short final period and missed-period counts. No concurrent
builds during measurement. Record raw first run even if it fails.

Primary optimization goal for fixed-I/O: median per-setting time ratio<=1 and
maximum<=1.25, candidate/predecessor, using each setting's median of3 run means
per input block. Streaming is an unchanged computational-path control and reported
separately. Also retain the original comparator's stricter pooled64-setting cost
gate without redefining its outcome. Report full-path cost and counterexamples.
Do not pool the best repetitions from different runs. The separate best-of-three
maximum callback80% test and actual complete-run deadlines are not replaced by
average cost. No hardRT or96k deadline qualification is presumed.

## Integration gates and boundaries

GCC/Clang C++20/23, ASan/UBSan, applicable TSan, SDK ON26/OFF13 and installed
C11/C++ checks; inventory/JUnit unique counts and zero skips. Source scope must
permit only this runtime edit from the pinned predecessor while keeping earlier
scopes and old-client/export/PCM checks. Review exact final HEAD/CI/diff before
merge; do not bypass reviews or protection. Keep failures and rejected goals.
No new DSP quality, formant range, extreme time/pitch range, vendor comparison,
GUI, physical-device or MOS claim. No Google Drive writes.
