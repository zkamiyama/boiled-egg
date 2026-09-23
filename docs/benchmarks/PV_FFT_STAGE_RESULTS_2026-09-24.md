# Exact first-stage FFT batching — results, 2026-09-24 JST

Issue71, parent67/69/15. Base main d4093d87aba960a1965b1243f6e685a23420ff25,
tree6bb4857396279588d44ea64fd2b0f2a90b5eb6c2. PR64/68/70 are already integrated.
This continuation adds no formant algorithm, range extension or costly research
mode. Only the length-two stage in fft_plan::advance changes runtime code.

## Implementation and exactness

Batch independent adjacent butterfly pairs within the caller's existing budget.
The old traversal processed one scalar pair per bookkeeping loop. Preserve the
stored root, complex multiply/add/subtract and pair order; even a root of one is
not replaced by identity. Finish each call with the same cursor fields, return
value and coefficient array. Other stages, immediate FFT, inverse normalization,
SIMD choice, scheduling quantum/yields, FFT/window/hop, buffers and allocation are
unchanged. There are no new members or tables. Public ABI/state/IDs/defaults and
latency/tail are unchanged. This is a cost optimization, not an acoustic upgrade.

The actual predecessor fft.cpp/header are compiled in another namespace, with
both input file SHA256 values checked by CMake. Controls cover 2..16384 points,
forward/inverse, scalar/SIMD, random/impulse/zero/signed-zero, zero/small/boundary
budgets, resumed and completed cursors. Each selected pause compares full arrays
bitwise and all cursor fields. GCC20 controls ran560 first-stage boundary cases,
512 small-prefix cases,240 large-prefix cases,96 signed-zero cases,56 immediate
cases,4 zero-budget cases,4 no-allocation cases and1 shared-plan thread case.
Full-prefix tests compared99,092 pauses, in addition to the560 first-stage checks.
This establishes tested numerical equivalence, not arbitrary invalid-cursor safety.

## Predeclared experiment and provenance

Issue71 specified the hypothesis before implementation. Protocol commit
284306e912e8d3205ce027f5cec2f0e63f2ae65b followed the first numerical tests but
preceded all full audio/cost measurement. Plan SHA256
3add265df759a14da46f1bc68aee3a43c05ec01bd9bd5a010e2537c922f84077
was posted in comment5797560514 before execution. No DSP/measurement rule or
threshold was tuned after the results. A thin driver reuses the unchanged
quality/pv_ring comparator, renderer, fixture and metrics, explicitly rebinding
its provenance BASE constant to the actual predecessor. Its historical pooled
cost gate remains visible; the primary fixed-I/O stratum is reported separately.

Known streaming regression:192 outputs,96 exact paired PCM/metadata/acoustic
records, all repeats identical. This path is unchanged; it is not misrepresented
as testing the modified cooperative path. Cost:64 settings xold/new x3=384
outputs,192 exact paired PCM/metadata records, all repeats identical. Fixed-I/O
includes the changed cooperative implementation. All576 outputs/receipts were
read back with hashes, length, finite/nonzero data and metadata checked. These
are known synthetic regressions, not natural-voice holdouts, MOS or vendor runs.

Cost grid:2-second vowel120,48/96k,mono/stereo(R=-.5L),32/64-frame blocks,+/-12st,
streaming/fixed-I/O,detail0/1. Same executable, checked loader resolution, fresh
libraries, old/new order alternated,3 repetitions, CPU0 affinity, no parallel
local builds. Use median run mean service time per input block for each setting,
then summarize candidate/predecessor ratios. Construction/flush/raw service arrays
and actual short-final-block periods remain separately recorded.

|Path|Settings|Median ratio|Maximum ratio|Faster settings|
|---|---:|---:|---:|---:|
|Fixed-I/O|32|0.8957414843|0.9887477335|32/32|
|Streaming unchanged-path control|32|0.9925931217|1.0529931735|20/32|

The fixed-I/O mean-cost reduction is about10.4% in this environment. Both its
predeclared median<=1/max<=1.25 goal and the original pooled64 gate pass. Full-path
median ratio is0.89574148 fixed and0.99081081 streaming. Do not claim a streaming
algorithm speedup from small unchanged-path timing fluctuations. Fixed48/96k
stratum medians are0.90163117/0.89180460. No favorable rerun replaces this first
complete measurement. Old/new construction median ratios1.00537/1.00139 by I/O
are small differences, not a construction speedup claim.

## Deadline counterexamples remain

|Fixed-I/O rate|Best-of-three maximum within80% period, old/new|Actual period exceedances, old/new|All-period complete runs, old/new|
|---|---|---|---|
|48k|16/16 ->14/16|24 ->20|37/48 ->37/48|
|96k|2/16 ->3/16|186 ->135|8/48 ->9/48|

In48k the best-maximum gate regressed in2 settings despite lower mean cost.
At96k13/16 settings remain outside the80% criterion. Preserve those observations;
do not call all callbacks successful or attribute every maximum to interrupts.
Streaming bursts are not audio callback qualifications. This is an unpaced shared
Linux environment, not physical DAC/DAW or hard-realtime certification. #67/#69's
broader deadline and environment issues remain open.

## Tests and integration controls

Actual local tests, unique inventories/JUnit and zero skips:
- GCC14 C++20/23 and Clang17 C++20/23:8/8 FFT tests each.
- Clang ASan/UBSan/leaks:8/8; GCC TSan shared-plan independent cursors:1/1.
- Existing public formant/ring controls:13/13.
- Fresh SDK spectral ON26/26 and OFF13/13; relocated shared C11/C++5/5 each.
- Reused comparator8 + new provenance3 Python tests:11/11.
- Prior strict source audits plus4 new rejection tests:24/24.

The new exact FFT source scope chains through the immutable accepted
ring/formant/duration/package/C1 references. It allows one identified fft.cpp edit
and rejects unrelated/missing/extra runtime or protected-tree changes. No old
client, export, full CSV or PCM comparison is removed. Final HEAD review/CI,
artifact readback and main status are recorded in the PR and latest Issue71.
CI uses its own binaries and plan; local timing is not relabelled as CI timing.

Measured identities:
- Old SDK ELF: b3fcf4108455a0ca13b58a3918594df90ba6486e8c937d5dfa7e6cd7d4ca3b30
- New SDK ELF: f74b4d6e4ba81d8a8b93d0f628df9c093d02c4d7a8f92bf26857e4b577279913
- Common renderer: 709ba9a7a73c7073506c0eec0f9bd3177395edc7a925f169c5c7371e891bf031
- Runtime FFT source: bf6a0c99952c1983f611488f5cb029c77d5dd5858c86f122853f79a70a870b5c

The baseline was restored from downloaded PR70 artifact10755328796 after direct
git clone failed DNS resolution. Its395source hashes and tree matched current
main; its old audio and binaries were not used as new measurements. Numerical
and build outputs live outside source. Protocol/result documentation added to
final delivery does not change the measured runtime/runner files. Full evidence
retains raw data, all callbacks, old/new binaries, commands and identities. No
Google Drive writes, external engine runs or private binary redistribution.
