# Practical capacity and exact-output product optimization — 2026-09-14 JST

## Scope and decision

Adopt `docs/REALTIME_ACCEPTANCE.md`: finite, predeclared per-history capacity
measurements; independent nonblocking/correctness/ABI/host checks; raw tails and
actual continuous successes retained. A shared VM's unexplained single maximum
is not a permanent library merge blocker. This does not turn minima into WCET
bounds or authorize automatic research-backend promotion.

PR #5's previously verified audit tooling was merged into main as
`0ad662010c1e1b4ac0f9488c8f61475cc58ba851` after rechecking both its product and
audit workflows. The current follow-up is based on that main, not a merge of the
research branch. It changes the shipping WSOLA/resampler implementation only in
ways designed to preserve numerical output. Public ABI, installed headers,
profiles, coefficients, adapters, state, fixed delay and tail contracts remain
unchanged. No new listening or native-zplane claim is made.

## Policy fixed before measurement

Three repetitions; at least 1,200 steady calls per setting; single-instance budget
80% of period; same-functionality relative cost limit1.25. These are explicit
project choices, not universal standards. The matrix is stereo48/96k,32/64frames,
time1,static -12,-7,-3,0,+3,+7,+12st,28 settings. Saturated wall-only timing avoids
nesting a CPU clock around another observer. Warmup is delay+0.5s input and is
retained. Probe and linked-library hashes are bound in the plan/receipts.

For every corresponding input/history position, use its best of three times;
then take the worst over states and settings. Also report second-best costs,
raw misses/maxima, and actual trials with every measured call within period or
budget. The minimum for one state may come from a different trial than another
state; their combination is **not** reported as a continuous successful run.
The tested histories are not all possible input states or the whole API range.

## Implementation

1. Cache exactly computed channel means and previous-tail energy once per WSOLA
   candidate search. Candidate order, stride, double summation and normalization
   remain unchanged. Scratch is allocated during construction, not processing.
2. Use a bit mask only for existing power-of-two ring capacities; arbitrary
   capacities retain modulo indexing and their original capacity.
3. Borrow a checked contiguous40-sample span for the resampler when the entire
   readable range is present and does not wrap. Otherwise use the original
   checked getter, including startup/zero-padding and ring-wrap behavior. The
   ascending float tap accumulation and coefficients remain unchanged.

The two double scratch arrays cost10KiB for default48k and15KiB for default96k,
plus object/vector bookkeeping. There is no new wait, callback allocation,
lookahead or DSP approximation. The internal test friend is not an exported API.

A power-of-two indexing-only pilot and a subsequent correlation-cache pilot did
not meet the predeclared80% budget at the examined96k/32/-12st state. Their
records remain separate. Adding the checked contiguous resampler path produced
the final candidate; no policy was loosened after seeing a failure.

## Final same-product capacity comparison

GCC14.2 Release, Linux x86_64 shared VM, same CPU affinity, no builds/renders/tests
overlap the final timing experiment. Old and new use the same fixed-I/O API and
deterministic input.28 settings x3 repeats x1200 =100800 steady calls per version,
plus74970 retained warmup calls each. The numbers below are the **maximum over
pitch/history of each state's minimum across three repetitions**, divided by the
actual rounded period. They are not p99 or a portable execution-time upper bound.

| Stereo rate/block | Previous main | Optimized product |
|---|---:|---:|
|48k/32|0.603056|0.081264|
|48k/64|0.289753|0.050146|
|96k/32|1.233553|0.231318|
|96k/64|0.615267|0.100966|

Old main has three settings not demonstrating80% capacity:96k/32 at-12,-7,-3st.
The candidate meets the unchanged budget in **28/28 settings**. At96k/32/-12st,
the most expensive repeated-best state changes411185ns to67160ns (the worst
state's index need not be the same after optimization). Across28 matched setting
statistics, median relative cost is0.174219; maximum is0.824394, below1.25. This
is a reduction of the declared capacity statistic, not a claim of83% lower CPU
usage in every DAW.

Candidate second-best worst-state ratio is0.893743; one of33600 tested steady
states has only one of three observations below80%. Raw period exceedances are
**148 -> 8 per100800 calls**. Actual all-period steady trials are57/84 ->79/84;
actual all-budget trials46/84 ->74/84. Largest raw ratio remains2.312696 for the
candidate, versus9.393600 before. The eight slow calls are retained; their cause
is not declared to be an interrupt and real audio-device reliability is not
certified. Capacity acceptance is not equivalent to a zero-miss continuous run.

All84 corresponding complete output-fingerprint sequences match old/new,
including175770 history rows per version. The same low-level deterministic
fingerprint is used as a replay guard, not as a cryptographic waveform proof.
Whole-WAV SHA256 evidence is separate below.

An earlier declared matrix also evaluated the inherited innovation research
candidate, without modifying it:28/28 observed capacity, worst ratio0.477162.
Its functionality/formant policy differs from main, so no relative speed ranking
or promotion is inferred. Experimental listening and feature gates remain
independent; the research tree is not imported by this follow-up.

## Whole-output equality and correctness

The supplied20 mono44.1k reference WAVs were rendered at time ratios0.5,1,2 and
seven pitch shifts including unity. Old CLI block256 and candidate CLI block32:
**420/420 complete WAV pairs have identical SHA256**,840 renders total. Every
output has the expected frames, rate, channels and finite samples. Inputs and
both linked libraries are fingerprinted. This is same-toolchain equivalence,
not cross-architecture identity or evidence of new perceptual superiority.

The first attempt was interrupted by the execution time limit after17 source
progress messages and published no final result. A complete fresh run finished
all20 sources. Only that complete420-pair run is counted; the interrupted log is
retained. No generated audio or user dataset is committed.

New internal calibration covers **1485567 ring/span cases** and **19692 exact
correlation scores**, with powers-of-two/odd capacities, wraps, mono/stereo/eight
channels, several window sizes, reset, silence and antiphase cases. Cached
candidate selection agrees with the original numerical oracle. Dynamic exports
of the old and optimized shared libraries are identical.

Local full product CTest:10/10 for each GCC14.2 C++20/23 and Clang17 C++20/23;
Clang ASan+UBSan with leak detection10/10. Tests include existing pure C,
no-allocation, stress, resampler, block consistency, threading, fixed-I/O host
and profile contracts. Audit protocol36023 deterministic comparisons and22
Python receipt/calibration/shell/capacity tests pass. The new capacity tests
explicitly reject a fictitious stitched run, a hidden heavy state, bad clocks,
changed fingerprints, inadequate counts and tampered receipts.

Hosted product TSan, actual CLAP/VST3 validator, exports and install consumers
remain required before the follow-up merge. CI additionally records a complete
capacity matrix as a diagnostic without demanding zero shared-runner tails.
Actual workflow conclusions and merge commit are recorded in the PR; this report
does not predeclare pending checks successful.

## Evidence and reproduction

Whole-WAV comparison CSV SHA256:
`0bc6c79e2d3ecaa8841adf26031c9e9ea4de4b35e0e6112813520b66799104e7`.
Capacity policy and each input/probe/library identity are in the delivered plans.
The source and applicable patches are recorded independently of run timing.

See `docs/REALTIME_ACCEPTANCE.md` for commands. To compare original and optimized
CLI output, separately build both source versions, then run:

```sh
python bench/rt_audit/replay_product.py --references data/ref_test \
  --baseline /absolute/old/boiled_egg_cli --candidate /absolute/new/boiled_egg_cli \
  --dependency /absolute/old/libboiled_egg.so \
  --dependency /absolute/new/libboiled_egg.so --workers 4 --output results/replay
```

`replay_product.py` uses development NumPy/SoundFile; the timing reporter remains
standard-library-only. Do not overwrite evidence or retune the acceptance budget
based on the outcome. This change improves current product cost, not research
Fuzzy quality, native-vendor results or OS interrupt suppression.
