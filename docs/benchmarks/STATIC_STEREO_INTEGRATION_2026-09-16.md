# Direct static-stereo SDK integration — 2026-09-16 JST

## Decision and resumption

Roadmap #15/#17/#18 and scoped integration review #25. The previous cost reduction
was already completed in #27 at 9ce32bb62c78674d0d66239854dc65c3c713137d when this
session resumed. It is inherited work, not a new optimization invented here.
This pass integrates the verified #26 repair and #27 optimization into the actual
opt-in PV sources, adds direct-checkout tests, and independently repeats the
correctness and practical capacity checks. Draft PR #28 is stacked on #27.

The branch now builds the corrected static stereo path without manually applying
a patch. Stable main remains da66001ea2381a938f227a36fe0319d0dc429945; no main merge
was performed. Spectral processing remains disabled by default and needs explicit
per-instance opt-in. This is scoped numerical integration, not general acoustic
promotion, a new MOS predictor, listening evidence or a native-zplane comparison.

## Changes and exact source

- 07ed691e: integration contract and unchanged acceptance criteria before tests.
- e04a1037: two actual runtime files with the previously verified patch chain.
- f3e84052: three ordinary opt-in CTests, including new public lifecycle checks.
- 318f55e8 / 1244716c: exact source/replay auditor and four negative calibrations.
- 1d1db3f7 / bddc2eca: direct-checkout CI and explicit ON argument for the installed
  consumer script. The workflow correction did not alter DSP or pass thresholds.

Validated code checkpoint: bddc2eca9f0a2c9a801914df75dd34b76bed83e9.
Validated tree: 52c7e01716452c309e3d5dfdbb23dfc5951999c0.
This final record is documentation only.

The integrated runtime is exactly the result of applying pooled_static_stereo.patch
then static_stereo_cost.patch to f8e5ef2cbce84f396597860a408b4a3084796115:

| File | Git blob |
|---|---|
| src/experimental/pv/pv_rt.cpp | 7233e4ef1ab4fd757632eea81419a7ed98b8ae6a |
| src/experimental/pv/pv_execution.inc | 83ddf8ef49d54bfaae86c48011378e6ce486b1b1 |

All 33 runtime/header files match the independent canonical patched tree, not
just those two files. Historical patch files remain unchanged for reproduction;
do not apply them again to this integrated checkout. Mono, ordinary WSOLA and
continuous-pitch/time arithmetic are unchanged. Public headers, ABI, state, IDs,
formant-policy interpretation, reported latency and plugin defaults are unchanged.
The static path's additional cache allocation occurs at construction only.

## Direct correctness and lifecycle evidence

The original spatial regression is now an ordinary CTest of the built SDK:
288 static configurations with exact block32/257 replay and the existing 1e-5
channel-relation limit, plus12 existing dynamic trajectories. The separate
cost_replay test covers144 static and12 dynamic whole-output histories, including
independent channels, silence and moving spectral peaks. All156 histories match
an independent same-toolchain build of the repaired predecessor exactly.
These are complete signal fingerprints, not extra independent perceptual cases.

The new lifecycle test covers24 configurations: rates44.1/48/88.2/96k, General/
Transient and Off/Harmonic/Monophonic, fixed pitch1.5. It checks zero startup at
the declared latency, finite nonzero output, proportional stereo, reset, in-place
processing, empty callbacks, state restore and exact block31/32/257 replay.
Invalid pitch events must leave output sentinels, state, latency and subsequent
DSP history unchanged. Compiling this same test against the original unpatched
SDK exits1 at the stereo invariant; the integrated SDK passes. Thus the added
regression actually exercises the formerly failing path.

The unchanged earlier stereo/time audit generates240 outputs across48/96k,
2qualities,3policies,5operations,4fixtures. All240 metadata checks pass;
proportional/silent controls120/120 and channel-exchange pairs60/60 pass.
Maximum proportional residual is6.443965913998014e-8 at the unchanged1e-5 limit.
The audit applies no fitted gain, latency shift, normalization or limiter.
This is a fresh integration rerun, not a new natural-music quality trial.

## Fresh local validation

| Check | Result |
|---|---|
| GCC14.2 C++20/23 and Clang17 C++20/23, spectral ON |26/26 each|
| Matched Clang ASan+UBSan, leak detection |26/26|
| Static spectral build |26/26|
| Default spectral OFF |13/13|
| Actual integrated TSan spectral/ramp thread tests |2/2|
| Installed shared ON/OFF and static ON C11/C++/ramp consumers |3/3 each|
| Objective metric/cost/integration Python calibrations |15/15|
| Separate original stereo/formant measurement calibrations |16/16|

The15 objective tests include four new auditor tests: missing cells, duplicate
cells, changed histories, invalid frames/columns and changed source cannot pass.
No suppressed sanitizer findings or relaxed thresholds. This is the stated local
scope, not every historical research experiment or a new manual DAW qualification.

## Fresh practical timing: cost and capacity both pass

Immutable copied GCC20 libraries identify original pre-repair, pooled numerical
repair, and optimized integrated source. All other local building/rendering/tests
finished before timing. CPU0 affinity, CLOCK_MONOTONIC_RAW-only brackets, three
rotated sequential repetitions; no empty-clock subtraction or outlier deletion.
Each pitch .5/1/2 covers48/96k stereo,2qualities,3policies,32/64frames:72 settings.
Each cell warms up through reported latency plus0.5s, then measures1200 calls.
Two formant events per callback and output fingerprints are retained.

Each version has259200 steady and199026 cold calls. All458226 corresponding
pooled/integrated output fingerprints agree. The predeclared criteria are
max_state(best_of_3)<=80% of period and per-cell median mean-time cost<=1.25x
original. Both pass72/72. No cost exception is needed in this measured range.

| Fresh local statistic | Value |
|---|---:|
| Worst integrated state-best / period |0.222090|
| Median per-cell mean-time ratio to pooled repair |0.729648|
| Median per-cell mean-time ratio to original pre-repair |0.881189|
| Largest per-cell mean-time ratio to original |0.979863|
| Integrated raw steady deadline misses |54/259200|
| Actually complete steady runs below period |183/216|
| Maximum single integrated duration / period |5.210058|

The integrated version is about27.04% cheaper than the pooled repair and11.88%
cheaper than original by the stated median-of-paired-cell statistic. This is not
a new numerical improvement beyond #27, a portable speed guarantee, or a claim
that the whole library/DAW is this much faster. Compare within this run; do not
compare absolute ratios with earlier VM sessions to infer additional optimization.

Capacity is not WCET, p99 or a successful continuous run stitched from minima.
Raw misses are not declared eliminated or attributed to a specific physical
cause. Independent CI results are72/72 cost and capacity, worst capacity0.290193,
median original-cost ratio0.892999, median pooled ratio0.759307, zero steady
misses and216/216 full steady runs. Those results do not erase the local54 misses.

## Hosted validation and reproducible source

All nine PR workflows at bddc2eca succeeded:
- integrated-static-stereo35053412642:6/6 jobs; direct GCC/Clang20/23, installed
  consumers, exact canonical comparison, strict240-output audit, full72-cell
  capacity/cost and direct address/undefined/thread instrumentation.
- ci35053412654: existing product/ABI/host checks.
- dynamic-pitch-editor35053412645.
- dynamic-plugin-sanitizers35053412676.
- automation-ramps35053412659.
- spectral-backend-preview35053412715.
- objective-stereo-coherence35053412585.
- static-stereo-cost35053412660.
- rt-measurement-audit35053412618.

The older patch workflows still validate their pinned dependencies. The NEW
workflow separately builds the actual current source, without patching it, so
those dependency successes are not substituted for direct integration evidence.
Actual plugin/editor checks are hosted automated checks, not manual DAW sessions.

Downloaded final GCC20 artifact10429663639 has SHA256
8d7b709d72ba714d19b8fb61c287c08e89d0c0dbeea12c358e2f5e7572f407e4.
ZIP CRC and all223 tracked source hashes verify. All219 locally present files
match; four initially absent local files were the new remote protocol/workflow/
auditor and its test. The downloaded auditor and all15 tests were then executed
locally. Synthetic merge66da1509718bbb1ca706e85e8a61a95e7ac0b6ce has the same
52c7e017 tree as the code checkpoint.

A fresh full build from the downloaded source passes26/26, reproduces all156
local replay histories exactly and produces the SAME library SHA256 as the
measured integrated binary:
218abecb11273524ad41e42c97d93a7b88889c2a536ab6c74dee1a65ffb63cb8.

## Use and roadmap boundary

```sh
# Checkout feature/integrated-static-stereo; do NOT reapply historical patches.
cmake -S . -B build -G Ninja -DCMAKE_BUILD_TYPE=Release \
  -DBOILED_EGG_ENABLE_EXPERIMENTAL_SPECTRAL=ON
cmake --build build -j2
ctest --test-dir build --output-on-failure
```

Per-instance BOILEDEGG_BACKEND_ALLOW_EXPERIMENTAL remains required. SDK callers
now obtain the integrated static-stereo repair through the usual opt-in backend;
no new public API is needed. Continuous-pitch plugin behavior is not silently
replaced. Main remains unchanged pending staged integration review.

The numerical repair, cost budget and direct integration are now objectively
verified without listener ratings. Remaining work is review/dependency handling
for the preview PR stack and independent validation of any frozen TSM perceptual
predictor on source-and-engine held-out data. No model was trained or executed
in this pass; no new listener scores or native-zplane outputs exist. Those wider
claims are not prerequisites for establishing this exact integration result.

Delivery retains verified source, both preserved patches, local/CI raw timing,
strict audit receipts/hashes, calibration and compiler logs, source audit and
commands. Test audio outputs, user recordings, external SDKs and fonts are not
redistributed. Inherited #27 artifacts remain labeled inherited; fresh results
are not pooled with prior repeated measurements as independent evidence.
