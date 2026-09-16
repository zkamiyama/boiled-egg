# Static-stereo cost reduction — 2026-09-16

Roadmap #15/#17, scoped follow-up to #25/#26. Preserve the verified pooled static
phase algorithm while removing unused work. Do not replace it with a new phase
estimator. Main, mono, dynamic timeline, Fuzzy, public ABI and plugin defaults
remain unchanged. Baseline DSP is f8e5ef2; corrected predecessor applies
pooled_static_stereo.patch. New optimization applies AFTER that patch.

## Planned invariant-preserving transformations

The static phase-locked path reads predictions only at its assigned peak owners.
Find-peaks partitions bins around ordered distinct peaks, so each selected owner
owns itself. Evaluate only these predictions (all bins for Classic). Finish all
predictions before updating rotations. Do not change active floating-point
expressions or peak selection. Skip unused per-channel output-phase reconstruction
on this path, cache its common complex correction once per bin, and avoid copying
an unused previous-output-phase array. Keep the cooperative yield locations in
loops so scheduler chunk boundaries and step budgets are not expanded. Cache
storage is created with the engine, never in process/reset.

## Validation fixed before measurements

Compare the original engine, the verified pooled predecessor, and the optimized
predecessor separately. Require exact predecessor/optimized output equality in
same-toolchain runs, not merely improved scalar scores. Retain the previous
1e-5 stereo controls, channel exchange, silent channels and unity checks. Exercise
both immediate and scheduled processing, changing peak ownership, broadband noise,
independent channels, resets, positive/negative channel relationships and partial
last blocks. Include mono and dynamic compatibility. Analytical test cases are
engineering coverage, not new natural recordings or listener evidence.

Run GCC/Clang C++20/23, ASan/UBSan, no-allocation and available thread/install
checks. Use the unchanged static_capacity.cpp workload: 72 configurations,
48/96k, stereo, General/Transient, three formant policies, block32/64,
pitch.5/1/2, 1200 measured calls after delay+.5s warmup, three rotated repeats.
Run timing serially, CPU-affined, with immutable final binaries and no concurrent
build/render/test workloads. Keep every warmup, maximum, miss and fingerprint.
Capacity max_states(min_3 time)/period <=.8. Cost: median-of-three cell mean
against the ORIGINAL pre-repair implementation <=1.25 in every cell. Also report
cost against the corrected predecessor. No relaxed threshold, outlier deletion,
noise subtraction or rerun-until-pass. Any incomplete or failed gate stays visible.

This follows an already measured numerical defect; no new ratings are required
for exact-output cost reduction. It does not qualify general naturalness, train
OMOQ, claim native-zplane superiority or authorize a default backend change.
