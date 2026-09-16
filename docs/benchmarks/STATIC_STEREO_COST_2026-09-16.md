# Static-stereo repair: exact-output cost reduction — 2026-09-16

## Roadmap decision

Roadmap #15/#17, cost follow-up to #25/#26. The numerical stereo repair no longer
requires the previously measured CPU-cost exception in the tested matrix. Preserve
the corrected output while removing unused work; do not replace the phase estimator
or request listener scores to decide an exact-output optimization.

PR #27 is stacked on #26. It stores an explicit follow-up patch, not an enabled
backend or a main merge. Apply pooled_static_stereo.patch and THEN
static_stereo_cost.patch to f8e5ef2cbce84f396597860a408b4a3084796115. Do not apply
the rejected static_stereo.patch. Mono, dynamic timeline, Fuzzy, WSOLA, public ABI,
state, latency and plugin defaults retain their audio behavior. General perceptual
qualification and frozen TSM-predictor validation remain separate roadmap work.

Protocol4ebadd8b fixed the plan and thresholds before optimization. Commits436e2644,
9e854e63,dbb1dbb5,464ba653 and9f6bbea4 add respectively the optimization, matched
output replay, cost auditor, auditor tests and CI. Validated code checkpoint:
9f6bbea494d4ea3c55f38a54e32b7c3bcf3bf706. This record is documentation only.

## Implementation

The corrected locked-phase path consumes predictions only for selected peak owners.
Peak regions partition around ordered distinct peaks, and each selected peak owns
itself. Compute those predictions only; Classic still computes every bin. Complete
the prediction pass before expanding owner rotations. When the original expression
would unconditionally return zero at initialization/transient reset, skip its unused
trigonometry. Active prediction expressions and peak selection are unchanged.

The static path directly multiplies each original complex channel coefficient by
one common correction. Cache that correction once per bin instead of recomputing
std::polar per channel. Do not reconstruct/copy unused per-channel output phases.
Keep cooperative-loop yield locations, finite step budgets and all existing
processing contracts. No approximation, fast-math, FFT/hop/filter change, new
lookahead, fitted gain, alignment or post-render stereo correction.

One bins-sized complex<float> cache is allocated during construction. Added element
storage is4104/8200 bytes for Transient/General at48k,8200/16392 bytes at96k, plus
vector/allocator overhead. It is fully overwritten before static use. There is no
new processing/reset allocation. The non-Fuzzy stereo constructor also reserves
this cache before an optional dynamic timeline is enabled; dynamic audio is
unchanged, but do not claim zero extra construction memory on that path.

## Exact-output and spatial verification

- Public same-toolchain replay:144 static cases plus12 dynamic histories, using
  independent channels, noise, silence, moving tones and impulses. Each executable
  checks block32/257 equality; complete-output fingerprints match between corrected
  predecessor and optimized implementation in156/156 cases. CI repeats this across
  GCC/Clang C++20/23. Hash equality is not new perceptual evidence.
- The unchanged original stereo audit:240/240 raw metadata,120/120 proportional/
  silent-channel controls and60/60 exchanged-channel pairs pass. Threshold1e-5.
- Four seeded/gain/length configurations across the earlier240-condition matrix:
  both implementations240/240 pass, and240/240 entire WAV SHA256s match. Worst
  relative residual remains1.0941928e-7 for BOTH; no scalar metric was retuned.
- Actual supplied20 mono references x2 qualities x3 policies at+7st:120/120 whole
  WAV SHA256s match. Input fingerprints retained; this is not a six-pitch or
  natural-stereo listening study.
- Existing compiled spatial regression:288/288 static cases pass; twelve dynamic
  cases retain fingerprint18071795476616882226 in the matched local GCC build.

Standalone render studies produce960 files:240 original-audit outputs,480 paired
seeded outputs and240 paired mono outputs. These repeat existing fixtures and are
not960 independent sources. C++ and benchmark histories are counted separately.

## Practical performance: both gates pass without relaxation

Three separately built roles: original pre-repair, corrected pooled predecessor,
and optimized pooled. Same GCC14.2 Release SDK, same benchmark executable bytes,
separate same-directory immutable libraries with recorded loader paths/hashes.
CPU0-affined CLOCK_MONOTONIC_RAW, three rotated sequential repetitions. No local
builds, renders or tests overlapped timing. Each pitch.5/1/2 covers24 configurations:
48/96k,stereo,General/Transient,three policies,block32/64. Each cell includes its
reported delay+.5s warmup followed by1200 steady calls and two formant events/call.

Capacity remains max_states(best_of_three)/period<=.8. Cost remains the ratio of
median-of-three cell mean times, optimized/original<=1.25 for EVERY cell. The cost
score is not a selected fastest run or the ratio of two unrelated minima.

| Metric, same local experiment | Corrected predecessor | Optimized |
|---|---:|---:|
|Median cell mean-time ratio to original|1.206182|0.890760|
|Worst cell mean-time ratio to original|1.396176|0.965315|
|Cells meeting <=1.25 original mean-cost budget|57/72|72/72|
|Optimized capacity gate|not compared in this table|72/72|

Optimized/predecessor median cell ratio is0.744428: about25.56% less measured work.
The optimized code is also about10.92% below the ORIGINAL pre-repair mean in the
median cell. Different cells can attain the table maxima; these are not a speedup
at one identical worst sample. Earlier-session15/6/etc. failure counts must not be
pooled: this table is one newly completed experiment, all rows retained.

Optimized worst state-best/period:48k/32=.095933,48k/64=.091981,
96k/32=.168489,96k/64=.174123. Empirical capacity is not p99, WCET, a stitched
continuous successful run, or whole-DAW scheduling qualification.

Each role has259200 steady plus199026 cold calls. All458226 predecessor/optimized
output fingerprints match at corresponding input/event states, including warmup.
Optimized raw steady deadline misses59/259200, actual complete steady runs181/216,
raw maximum13.346214 periods. Those outliers are neither deleted nor ascribed to
a proven interrupt mechanism. No noise subtraction or rerun-until-pass occurred.

## Software checks and hosted independence

Local optimized GCC14.2/Clang17 xC++20/23:23/23 CTests each. Matched Clang
ASan+UBSan with leak detection:23/23. TSan spectral/ramp thread tests:2/2, no
suppression. Existing spatial executable passes. Eleven objective metric/cost
auditor tests pass (eight inherited, three new). Legacy installed C/C++ smoke
passes; explicit installed spectral/ramp consumers3/3 pass with EXPECT_SPECTRAL=1.

An initial installed-consumer invocation omitted EXPECT_SPECTRAL=1, so the C
consumer expected an unavailable backend while testing an enabled build and
failed1/3. The correctly specified ON configuration passes3/3. The original log
is retained; no consumer assertion, DSP or quality threshold was changed.

At9f6bbea4 all three triggered PR workflows succeed:
- static-stereo-cost35050769820:five jobs; GCC/Clang20/23 matched full-SDK replay,
  strict complete72-cell cost/capacity gate on GCC20, and ASan/UBSan.
- objective-stereo-coherence35050769851:prior strict original stereo audit.
- existing product ci35050769773.

Independent CI:72/72 capacity AND72/72 cost, worst capacity.301041; median cost
ratio to original.895195, worst.943145; median ratio to predecessor.759445.
CI has0 steady misses and216/216 actual complete runs. This does not replace the
59 local misses or imply a portable machine-independent performance number.

CI artifact10428693692 was downloaded. ZIP CRC and SHA256
b9163ca7777a6446e0b342fd981693dc4dcafd58354497ce8dbf5376a228680f verify. All217
tracked branch files verify, and all198 optimized-source hashes match the actual
local source used by the measurements. New local patch/replay/auditor/test files
are byte-identical to the downloaded committed files. CI synthetic merge
1c84b5676e850bc91f38b7ce6d7798c4432c66d3 has tree
6ea1267f6ba1ffda4eee60605c595845df9762e6. No cross-compiler waveform equality is
asserted; comparisons always use matched builds in one environment.

## Reproduction and next roadmap boundary

In a disposable worktree of the pinned PV source:

```sh
git apply /absolute/quality/objective_audio/pooled_static_stereo.patch
git apply /absolute/quality/objective_audio/static_stereo_cost.patch
cmake -S . -B build -G Ninja -DCMAKE_BUILD_TYPE=Release \
  -DBOILED_EGG_ENABLE_EXPERIMENTAL_SPECTRAL=ON
cmake --build build -j2
ctest --test-dir build --output-on-failure
```

The committed workflow is the executable recipe for three separate implementations,
exact replay and the full rotated cost matrix. cost_audit.py validates complete
histories and uses the existing declared capacity summarizer. Supply a new output
path; mismatched fingerprints, missing samples or failed gates are not suppressed.

The measured cost exception blocking the scoped repair is resolved in this matrix.
Review/integration of the opt-in correction can proceed on numerical evidence;
new listening submissions are not a prerequisite for this exact-output change.
Main and plugin defaults were not merged/changed in this pass. Overall roadmap B
is still open: frozen TSM-predictor validation on disjoint source/engine groups,
formant/natural-stereo applicability and product-use-case decisions are not claimed
completed. No new MOS, human rating, native-zplane run or new DSP algorithm.
