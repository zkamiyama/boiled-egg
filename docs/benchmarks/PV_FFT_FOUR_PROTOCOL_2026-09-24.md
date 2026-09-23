# Length-four cooperative FFT batching — protocol, 2026-09-24 JST

Issue73, parent67/69/15. Base0d3feae8bb85b39f5058eecf8d77b6869c5cd476,
tree b7802edbac925df1d58f659b21d2f0761c21d7b0. PR64/68/70/72 are integrated.
The hypothesis was posted in Issue73 before implementation. Initial numerical
controls already ran; all full audio/cost measurements are still prospective.

## Fixed implementation scope

Batch complete four-point blocks only when length==4, column==0 and budget>=2.
Hoist the two unchanged roots and loop bookkeeping. Retain scalar complex
multiply/add/subtract and the old two-butterfly SSE2 grouping and instruction
order. Do not special-case roots of one or imaginary units. Partial/odd budget
and column1 use the existing path. At each advance return the entire coefficient
array, cursor fields and return value must equal the immutable predecessor.
Other stages, immediate FFT, inverse scaling, SIMD choice, scheduler/yield/work
budget, windows/hops/FFT size, buffers, allocations, ABI/state/IDs/defaults and
latency/tail do not change. No new algorithm or formant/range qualification.

## Correctness

Compile the real predecessor fft.cpp/header in a renamed namespace and enforce
both SHA256 identities. Reuse previous complete-prefix controls, then add explicit
length4 entry at column0/1, budgets0/1/2/3/4/5/127/128/129/4096/N2/N2+1, sizes4
through16384, forward/inverse, scalar/SIMD, random/impulse/zero/signedzero. Retain
noallocation and independent cursors on a shared immutable plan. Check GCC/Clang
C++20/23, a SIMD-disabled build, ASan/UBSan and TSan when executable. Reject altered
reference input. Reuse existing public formant/ring, SDK and installed consumers.

## Full SDK evidence, fixed before measurement

Reuse the unchanged quality/pv_ring comparator and quality/formant_detail
renderer, fixtures, metrics and receipts. A new thin driver names this actual
baseline and protocol instead of reusing the previous experiment's identity.
Bind all source/input/runner/library/dependency hashes and CPU in a plan, publish
its SHA256 before running. No concurrent builds during measurements.

Quality: four existing synthetic families x48/96k x+/-12st xdetail0/1 x3repeats
xold/new =192 streaming outputs. These are known regressions, not a natural-voice
holdout. Require exact paired PCM, metadata, acoustic metrics and repeats.

Cost: two-second vowel120 x48/96k xmono/stereo x32/64frames x+/-12st xstream/fixed
xdetail0/1 =64settings,3repeats,old/new alternating =384 outputs. Use the same
executable and verify the loaded library. Compare per-setting median of3 mean
service times per input block, not per successful pull. Retain creation, flush,
p99/max, all individual service times, actual final short period, deadline misses
and complete-run counts. Main target is fixed-I/O median ratio<=1 and max<=1.25;
streaming is unchanged-path control. Preserve the existing pooled64 gate too.
Keep first-run failures. No parameter/threshold tuning after seeing measurements.
The best-of-three maximum80%-period criterion and actual complete runs remain
separate. Neither average speedup nor one good maximum establishes hardRT.

## Integration

Keep all earlier pinned source audits and unchanged old-client/export/PCM checks.
Allow only the identified runtime file difference from the fixed predecessor.
Small implementation/control/evidence commits, exactHEAD CI/diff/self-review;
no review/protection bypass. If correctness or cost fails, retain the negative
result and do not promote this candidate. No vendor execution or Drive writes.
