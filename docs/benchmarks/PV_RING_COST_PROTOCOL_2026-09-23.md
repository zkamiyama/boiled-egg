# PV ring-address cost protocol — 2026-09-23 JST

Issue69, parent67/15. Base main b972e0355ae656a74fb3fb1b1a99429f1668a5e4,
tree d0259667dd826a7255a858cdfb508af5d4504680. PR64 and PR68 are already
integrated. This unit adds no formant preset, range, buffer, FFT, float arithmetic,
latency, scheduler quantum or public ABI/state/ID change. No vendor/Drive work.

## Hypothesis and scope

All four PV ring capacities are rounded by next_capacity to positive powers of
two. For an unsigned position, x % C equals x & (C-1). Replace only these ring
addresses in the immediate and cooperative implementations, including the checked
resampler tap reader. Keep negative/out-of-range checks, sample order, rounding,
allocation, scalar/SIMD choice and yield locations unchanged. Do not apply this
identity to arbitrary capacities or signed negative values.

Acceptance requires exact PCM/length/metadata versus this base, not approximate
similarity. Test powers through the uint64 boundary, exhaustive small wraps,
seeded positions and actual construction-capacity formulas. Existing public
formant controls cover reset, partition, formant events, C11, invalid selections,
nonfinite input, allocation observation and independent-instance concurrency.
Existing SDK/automation/static-stereo regressions remain active.

## Fixed experiment

Reuse quality/formant_detail fixture and public renderer without modification.
Known vowel120/vowel220/check83/check173,48/96k,mono,block64,+/-12st,detail0/1,
three repeats on each library:192 quality outputs. These are known regressions,
not independent natural-voice confirmation. Exact PCM and acoustic values between
libraries are required, not a new quality-improvement assertion.

Cost uses the same two-second vowel120 and stereo R=-0.5L:48/96k x mono/stereo x
32/64 x +/-12st x streaming/fixed-I/O x detail0/1 =64 settings. Alternate old/new
order between three repetitions, fixed CPU affinity, same executable and input.
There are384 cost renders. Record actual loaded library, all output/receipt hashes,
construction, service sums, EOF, each service duration, p99/max and overrun counts.
Bind source/input/runner/ELFs/dynamic dependencies/environment in a plan hash before
execution. Rebuilt binaries require new identities and new measurement evidence.

Use each run's service time per input block, take the median of three paired
settings, then summarize ratios candidate/base. Fixed objectives: median<=1.0 and
all settings<=1.25. Report per-I/O/rate strata, regressions and full-path cost.
Separately evaluate the maximum over states of the best-of-three maximum callback
against80% of its period; retain actual per-run all-callback completion and missed
period counts. Streaming bursts are not audio callback deadline certification.
Shared-VM outliers are not automatically dismissed as interrupts.

## Verification and release

GCC/Clang C++20/23, ASan/UBSan, applicable TSan, SDK ON26/OFF13 and installed C11/C++
checks are required in the measured scope. Zero tests, skips, incomplete and
fabricated receipts must fail. Keep predecessor strict source scopes; add a pinned
scope for this exact runtime edit without removing old-client/export/PCM checks.
Commit implementation, controls, runner and evidence separately. Review exact
final HEAD/CI/diff before any merge, without bypassing protection or required
review. Unmet96k deadlines remain open even when average cost improves. No general
hard-realtime, naturalness, Soloist parity or expanded time/pitch claim.
