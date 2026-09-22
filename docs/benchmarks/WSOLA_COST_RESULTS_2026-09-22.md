# WSOLA same-output cost reduction — 2026-09-22 JST

PR64, Issues62/63 and parent15. Base main7b256119baee9793ba32982b3b14e04ed03c94be.
This continues the small duration/progress correction, not the paused iterative
or multiview quality research. No vendor engine or Google Drive is used.

## Change and acceptance boundary

Cache the original float overlap expression once at construction, then reuse its
weights across channels and frames. Return before resampler bank/cutoff preparation
when no output capacity or earned input-time budget exists. No approximate cosine,
fast-math, tap/score/accumulation reordering, new filter, preset or backend switch.
The cache contains overlap floats; reset does not recalculate it.

Keep the restored correction's output credit and FIFO progress behavior. The
remaining first-search lower bound is clipped by the original candidate selector;
inputs earlier than the next possible search are released even while waiting for
future input. Final output rounding is unchanged. This fixes small-FIFO progress
rather than generating silence, truncating completed files, or releasing samples
before their duration is earned.

Public declarations, ABI/state/IDs, default WSOLA, spectral opt-in, latency/tail,
plugins and GUI are unchanged. Only engine.cpp/engine.hpp runtime contents differ.
Unlike the earlier duration-only checkpoint, this version intentionally adds one
construction-time cache allocation and overlap*4 bytes plus vector/allocator
bookkeeping. Default cache payload is2048 bytes at48k and3072 at96k, independent of
channel count. Processing still allocates nothing in the tested paths. The old
WSOLA_DURATION_RESULTS report describes its own earlier checkpoint, not this cache.

## Baselines and provenance

Two different corrected baselines existed at restart, and are not interchangeable:
1. Prior conversation attachment841b1b1, tree af76441d: output limit at resampling,
   plus initial-bound/FIFO progress. This is the primary same-output cost baseline.
2. Actual open PR64 checkpoint d510acc, tree1dc76116: budget integer updated on push,
   initial-bound correction but no additional FIFO reclamation. Its CI artifact
   10674920698 was downloaded and SHA/source/tree verified. This is a supplemental
   baseline, not another name for841b1b1. PR64 is continued, not duplicated.

Protocol2deac409e6c85497cd11613a966b6f6948ccb4fd precedes timing. Three full runs:
- Initial:51fee707a03854d6768f491c47109e184b993e6abd58ce250828c1ce9b14f2ed,
  registered in Issue62 comment5776308262.
- Final primary:81f4ffd88b5459e84d2f47fe757ef6a0e94c096bfa0679f6581951328bd6c8aa,
  registered in PR64 comment5776486337 after the assessor correction below.
- Supplemental PR64 baseline:53b8e2b767c512bd89250be40ea3a97111f7fd272dc4cec34f777d2b7ed97ca3,
  registered in comment5776538995. Same candidate and grid; different baseline.

Each run binds actual source/executable/library/dependency/input rules and settings.
Build commands/compiler flags are retained with their identities in the evidence.
Candidate DSP source and ELF did not change between runs. New documentation and
integration audit copies are not represented as the original measured source tree.

## Fixed-work measurements

Each complete run contains32 streaming and16 fixed-I/O settings, each3 repetitions
for both libraries:288 executions/144 paired outputs. Rates48/96k,blocks32/64,
streaming mono/stereo and(time,pitch)=(1,1),(.25,1),(1,.25),(1.25,1.3348398);
fixed-I/O stereo pitches.5/1/2/4,time1. Input is2seconds of deterministic nonzero PCM.
Order alternates by case/repeat, CPU affinity is fixed, and the actual dynamically
loaded SDK path is checked. No build/test runs compete during these measurements.

Primary metric is median native service time per identical input block, then the
median ratio across settings. Native processing includes EOF, but not file IO or
hashing. Full host wall time, API count, per-call mean/p99/max, per-block services,
construction times and runtime metadata are separate. The two libraries produce
identical PCM and call-count metadata for all144 pairs in each of the three runs.

|Run/baseline|Stream ratio median|max|Faster settings|Fixed-I/O ratio median|max|Faster settings|
|---|---:|---:|---:|---:|---:|---:|
|Initial /841b1b1|0.860782|1.039774|31/32|0.811817|0.975512|16/16|
|Final primary /841b1b1|0.885295|1.210896|30/32|0.808849|1.034612|15/16|
|Supplemental /d510acc|0.854615|1.043035|30/32|0.808624|0.960230|16/16|

All48 settings per run meet the<=1.25 relative cost gate. The final primary medians
represent approximately11.5% less streaming cost and19.1% less fixed-I/O cost; they
are not a promise of universal speedup. The worst primary streaming setting is21.1%
slower. Retain it rather than substituting a better repeat or a different baseline.
Primary wall-time ratio medians are0.887942/0.814053, maxima1.236314/1.035193.

Primary cold-create medians are40.9878/40.9502ms baseline/candidate; warm-create
medians2.41868/2.41726ms. These include all engine initialization and do not isolate
the cache's construction cost. Small differences are not claimed as a create-speed
improvement. No same-output shortcut is claimed outside the same compiler and fixed
normal floating-point environment; changing rounding modes between construction
and processing has not been qualified.

## Deadline diagnostics and assessor correction

The initial summary reported the state-wise best-of-three MEAN; that is not the
required state-wise best-of-three per-pass MAXIMUM. Preserve both quantities in
final reports, add a negative showing that a good mean does not rescue an excessive
max, and reject a single nonfinite timing instead of letting a median hide it.
The whole288 primary run was repeated after those assessor changes. No DSP/input/
threshold tuning accompanied the correction, and initial records remain separate.

Final primary worst-across-states best-of-three callback maxima satisfy80% of the
block period for each of the four rate/block configurations. Nevertheless candidate
actual period overruns are5 callbacks and only43/48 entire fixed-I/O passes have no
overrun; baseline has7 and43/48. Supplemental run has19 candidate overruns and38/48
clean passes (baseline23 and35/48). All API underrun counters are zero, which is a
different property from a wall-clock overrun. Do not claim hard realtime, combine
state bests into a real uninterrupted session, or attribute every spike to IRQs.

One progress comment incorrectly added the primary clean-pass count as45/48. The
immediate corrective comment5776544345 and the source JSON give43/48. No timing or
PCM was changed to make this correction.

## Fresh correctness checks

The primary corrected baseline and optimized library were newly run through all
2650 public-ABI trials;2650/2650 output bytes, length and required budget invariants
match.2290 are finite nonempty/nonzero outputs;360 are empty or round-to-zero
mathematical cases, not acoustic-quality successes. The seven groups include
allthree WSOLA profiles,48/96k,mono/stereo,32/64/257 blocks, dynamic setters/reset,
short/empty/noninteger lengths, FIFO saturation, invalid input and no allocation.
Stored raw files are independently reread. The old buggy-main comparison in the
prior artifact is historical, not another2650 fresh runs this turn.

The cache has278784 bit-exact overlap sample/weight checks against the original
float formula, including legal window sizes, ring wraps and resets. Existing
1485567 ring/span and19692 correlation-score checks remain. No original test is
replaced by a silent-input test or a successful subset.

Local fresh results: SDK ON26/OFF13, zero skips; installed C11/C++ consumers5 each;
existing PR64 duration groups5 (396cases); public budget groups7; Python cost/raw
comparison18 and legacy scope14; GCC/Clang20/23 cache controls and public groups7
for each; Clang ASan/UBSan/leaks7; GCC TSan threading/DAW-owner checks2. Compiler
artifacts are separate builds and not reused as the timed GCC library. JUnit
inventory/unique executed names/skip0 are checked. Existing public old-executable,
preview and export regression in CI is retained under the exact runtime allowlist.

The original audit.py and its compare/export functions remain unchanged. The
named duration scope accepts only the reviewed engine.cpp/engine.hpp hashes and
requires the same immutable reference/protected trees. Added scope documentation
explains the cache; it does not exempt other DSP or header changes. Exact final
HEAD/CI/merge and artifact verification are recorded in PR64 and Issue62/63.

## Identities and reproduction

Primary corrected ELF SHA256:
75285739239b14dc0e57c514e78a6b7efba170b764f2699c56689d89429b4c80
Supplemental PR64 ELF:
9a8a8dcd0f2a6ad0d5929261f9aafb91c231a37b41d64df62899b5b72c17e32f
Optimized timed ELF:
e68dd3440a3e15f4d59f80db3ae04b0f9cb0cc7f3df94b7e46ad4a74fc22b2fe
Final engine.cpp:
7dce37ab64b3cf53c96458683e94f28bd82920199c944beeffc4c39461b3256f
Final engine.hpp:
eb459ae0c9caf0d4cfd1b9f5583b22131afb03576a7cc3cba1263683e299475f

```sh
# Build both identified sources with identical Release/compiler options, outside source.
cmake -S . -B /tmp/be-opt -DCMAKE_BUILD_TYPE=Release -DBOILED_EGG_ENABLE_EXPERIMENTAL_SPECTRAL=ON
cmake --build /tmp/be-opt -j2
cmake --install /tmp/be-opt --prefix /tmp/be-install
cmake -S quality/streaming_budget -B /tmp/be-budget -DCMAKE_BUILD_TYPE=Release -DCMAKE_PREFIX_PATH=/tmp/be-install
cmake --build /tmp/be-budget -j2
python quality/audition/run_ctest.py --build /tmp/be-budget --expected 7
# Build one cost client; the runner verifies each selected library with ldd.
g++ -O3 -std=c++20 quality/streaming_budget/cost.cpp -Iinclude -L/tmp/be-opt -Wl,-rpath,/tmp/be-opt -lboiled_egg -o /tmp/be-cost
python quality/streaming_budget/cost.py prepare --root . --client /tmp/be-cost --baseline /tmp/be-baseline/libboiled_egg.so --candidate /tmp/be-opt/libboiled_egg.so --output /tmp/be-plan
# Register the printed SHA before executing a new measurement. Never reuse old timing.
python quality/streaming_budget/cost.py run --plan /tmp/be-plan/plan.json --sha256 REGISTERED_SHA --output /tmp/be-results
```

This unit does not fix WSOLA's low-tone pitch quality(#41), add input-range formant
presets, extend PV capabilities, or certify naturalness/elastique parity. It reduces
repeated work while preserving the corrected waveform in the tested conditions.
Physical devices, real DAW sessions and every OS/rounding environment remain
separate qualifications. No new proprietary output or learned score is produced.
