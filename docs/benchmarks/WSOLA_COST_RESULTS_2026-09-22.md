# WSOLA exact-output cost reduction — 2026-09-22 JST

Related #65/#62/#63, preceding PR64; parent #60/#15. Base main
7b256119baee9793ba32982b3b14e04ed03c94be. This is bounded correctness and
same-output maintenance, not renewed high-cost DSP research or formant/pitch
range expansion. No vendor execution or Google Drive write.

## References and implementation

Remote PR64/d510accfa5f5eaed0b68a30f95be7db7dd6e0a10 already contained the
accepted-input duration cap, initial-bound progress fix and strict compatibility
machinery; it was open at restart. Its branch is not overwritten. New commits
reuse its history and tests. The supplied source archive additionally contained
local841b1b185be57a4979f7188f2789b1b1b1351848, tree
af76441ded933f9fc85ac4d1a263fe00559c46f1: this computes the same cumulative
budget at resampler entry and reclaims unusable old input before waiting for a
long hop, avoiding small-FIFO stalls. That exact corrected source is the primary
before reference. Original main is a separately built historical reference.
Neither unmerged reference is misrepresented as current main.

Runtime changes are only src/engine.cpp and src/engine.hpp:
1. Precompute the identical float cosine fade once at construction, independent
   of channel count. Reuse it without changing multiply/add order or rounding
   expressions. Reset does not change the immutable weights.
2. Use the existing checked contiguous ring-span accessor for overlap synthesis
   and tail copy, retaining the exact checked/zero-padded path at boundaries and
   wraps. No tap, correlation stride, candidate order or window change.
3. Return before resampler bank/cutoff setup when the existing output budget or
   output space already prevents emission.

This retains the corrected source's duration/progress behavior. No public ABI,
state, parameter/plugin ID, default, latency/tail, PV, GUI or transport change.
There is one new vector with overlap float coefficients: typical payload2048bytes
at48k and3072bytes at96k, plus vector/object/allocator overhead. Allocation and
cosine work occur at construction, not processing. This is a time/memory tradeoff,
not a zero-memory-cost optimization. Bit-level tests use FE_TONEAREST; changing
the floating-point environment between construction and processing is unqualified.

## Preregistered experiment and actual output equality

Issue65 records the hypothesis before implementation/measurement. Full performance
plan SHA2564ce7e323ca63e9e0210175c7d5980f65eb36c21200850da617b49710d3a115d7
was posted in comment5774733453 before running it. Inputs, executable, source,
three newly built SDKs, linked dependencies, CPU affinity and order are bound.

The direct scalar control checked3,062,800 cached-weight/output comparisons,
including1/2/8/32channels, irregular windows, non-power-of-two rings, zero padding,
wraps, reset and budget-blocked state. All were bit-identical.

The attached corrected before and optimized after were both actually run through
all2650 public ABI budget trials. All2650 lengths/PCM match exactly;2290 outputs
are nonempty,360 are empty-input or rounded-zero cases and are not acoustic
successes. Output-prefix budget, EOF, invalid controls, mono/stereo, dynamic time,
reset, backpressure and processing-allocation checks pass. This turn did not rerun
all2650 on uncorrected main; its old114 overlong/111 stalled outcomes are historical.

## Same-work cost, not successful-pull normalization

56 settings x3 repetitions x3 versions =504 sequential child runs. For each
setting/repetition rotate original/before/after order and pin the child to one
CPU. No compilation or other validation workloads ran concurrently. Each input
is2seconds. The32 streaming settings cover48/96k x32/64frames xmono/stereo and
(T,p)=(1,1),(.25,1),(1,.25),(1.25,1.3348398). The24 fixed-I/O settings cover48/96k,
32/64frames,3 existing qualities andp1/2,stereo. RT drain includes reported
latency/tail and full-block rounding. This is not physical audio-device pacing.

Before168/168 and after168/168 succeed, with PCM/repeat equality for all56settings.
Original main has48 failures (16 streaming settings x3) from its duration defect;
those failures stay in the504 denominator and have no speed ratio. All40 original
complete settings have identical PCM to after. The comparison client is identical
across versions. No failed or silence output is counted as a speed improvement.

Each setting uses its median of3 measurements; the table summarizes those paired
ratios (after/before), not a ratio of unrelated aggregate medians or best runs.
Native time is the sum of actual API service times divided by the same number of
input blocks. Streaming native sum excludes the explicit flush call; full wall
and thread-CPU cover the entire streaming/EOF path and host checks. Cold
fixture+create includes source/buffer setup and is recorded separately.

|Scope|Median native/input-block ratio|Maximum ratio|Reduced settings|
|---|---:|---:|---:|
|streaming32|0.875625|1.095645|28/32|
|fixed-I/O24|0.682926|0.895807|24/24|
|all56|0.772621|1.095645|52/56|

Full-path wall median ratios: streaming0.879719, fixed-I/O0.690309.
Full-path thread-CPU ratios: streaming0.892477, fixed-I/O0.690167.
The preregistered median<=1.0 and every setting<=1.25 native-cost gate passes.
Four streaming settings still increase, by up to9.56%; do not call this a
universal speedup. Compared only with original main's healthy subset, median
native ratios are0.812013 for16streaming and0.687300 for24fixed-I/O settings.
Those restricted numbers do not include original failures.

Deadline diagnostics remain separate. Across72 fixed-I/O runs per version,
249348calls each, the80%-period exceedance count is17 before and12 after. Maximum
service time is1.930714ms before and1.916263ms after. Median per-run p99 is
19.764us before and12.8395us after. The32 streaming settings' corresponding raw
threshold counts are14/17 and are not callback-deadline measurements. Neither
outliers nor speedups establish hard realtime, device continuity or scheduling
causes. The full504 receipts and call-time arrays remain available.

## Tests, validation repair and integration boundary

Local GCC20 used the initial root26tests plus the new exact control (27/27).
GCC23/Clang20/Clang23 and ClangASan/UBSan/leaks each completed the scoped5controls:
exact overlap, existing noalloc,C ABI,threading andDAW-owner tests. Final layout
moves the exact control to an independent1-CTest target and preserves original
root counts26ON/13OFF; this changes build metadata, not measured runtime source.
The final local OFF13, direct1, relocated shared-OFF consumer5 and GCC TSan
threading/DAW-owner2 all passed with checked counts/skip0. The final CI performs
full2650 budget trials plus direct comparison on each of4compiler/standard
combinations andASan/UBSan. Other existing workflows retain ABI/state/export,
old-client and installed-package checks. Actual final CI results are recorded in
the PR/latest comments, not assumed from this workflow definition.

Comparator8 and benchmark6 negative tests pass. After timing, benchmark assessment
was strengthened to reject missing/nonfinite timing/PCM receipts, preserve an
all-failed summary, and explicitly require the preregistered cost gate rather
than only PCM equality. The original measured script/summary are preserved. Raw
measurements and numeric summaries did not change; the new validated summary
adds honest success criteria. The timer/client, inputs, source/ELFs and any
quality thresholds were not changed or rerun under another binary's name.

The original compatibility functions are unchanged. The named duration scope
first validates the fixed pre-fix reference against the existing package/donor
contract, then allows only the exact two reviewed runtime hashes below. It
requires unchanged adapters/eval/research and retains all old-executable and
complete-grid PCM comparisons. It is not a whole-DSP exclusion or hash waiver.

## Identities and remaining work

New engine.cpp SHA25611424ebdd51e05eed0f727ea86dc7573a9f58b0afa11e67141bc94f04dc6aef8.
New engine.hpp SHA256eb76fd256ab270fe80aa68199788f67be630ebe0a46508cbf376bf6c16b8f445.
Measured original SDK SHA256218abecb11273524ad41e42c97d93a7b88889c2a536ab6c74dee1a65ffb63cb8.
Measured corrected-before SDK SHA25675285739239b14dc0e57c514e78a6b7efba170b764f2699c56689d89429b4c80.
Measured optimized SDK SHA256876351bb41a0e9a1c3afa37833a4cfc96bcba23a43b7d35b06f2651cde11dd83.

See quality/wsola_cost/README.md for reproduction. Final source/HEAD/CI/merge and
artifact readback are recorded separately. CPU results apply to this environment
and declared grid; no vendor quality win, formant input-range presets, PV extreme
capability, resolution of low-tone defect41, physical DAW/OS/device support or
naturalness qualification is implied. High-cost research stays paused.
