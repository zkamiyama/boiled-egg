# Practical real-time acceptance for the library

## Responsibility and merge scope

The library must perform bounded work on the supported audio-owner path without
introducing allocation, blocking locks, filesystem/network access or waits for
other threads. Construction and excluded lifecycle operations are separate.
The host selects an appropriate audio thread and divides its processing budget
among the library, other plugins and mixing. Device/OS scheduling and whole-DAW
reliability are integration concerns, not a promise made by a library benchmark.

An unexplained maximum on a shared VM is **not by itself a permanent merge
blocker**. Conversely, one fast easy call is not proof for a heavy processing
state. Preserve the measured tails; do not subtract a control's time or label
all slow calls interrupts. No universal hard-real-time claim is made here.

A change that demonstrably preserves the current product's output and contracts
can merge after the engineering gates below. This does not promote experimental
research backends, relax separate listening/quality gates for algorithms that
change audio, or claim native-vendor parity. Retain explicit manual modes.

## Three separate outcomes

**Observed computational capacity:** replay the same deterministic input, event
history and settings exactly three times. For each corresponding steady-state
call, take its best time; then take the maximum of these minima across all calls
and configurations. Require this value to fit the predeclared per-instance
budget. A successful result means every *tested* state has a deadline-compatible
observation. It is not a worst-case execution-time upper bound.

**Actual continuous-run evidence:** separately count trials in which every
measured steady-state call fits the budget and trials in which every call fits
the period. Never combine minima from different trials into an invented complete
success. Saturated-loop success is not a measured audio-device xrun test.

**Environment/host stability:** retain every raw maximum, deadline exceedance,
warmup row, second-best state cost and the number of states with only one
successful repetition. Periodic release/wake/response measurements stay separate.
Unqualified shared-host tails remain an integration caveat, not hidden evidence
and not automatically a DSP computation defect.

## Predeclared capacity policy

`bench/rt_audit/capacity-policy.json` records these project engineering choices:

- Exactly three repetitions, at least 1,200 steady calls per setting.
- A per-instance budget of 80% of the audio period (20% nominal slack).
- Relative capacity cost at most 1.25 times a comparable baseline in the same
  experiment; investigate a regression rather than silently changing the limit.

These numbers are not an industry standard or a multi-plugin DAW guarantee.
Fix any different policy **before** measurement and keep it in the plan. Do not
retry indefinitely until every state has one fast sample. An incomplete or
unbound run is invalid evidence, not a passing or failing performance result.

The implemented capacity matrix is 48/96 kHz, stereo, 32/64 frames, time ratio1,
and static pitch -12,-7,-3,0,+3,+7,+12 semitones: 28 settings. It measures the
real fixed-I/O callback path using wall-only timing in saturated runs. Warmup is
at least the declared delay plus 0.5 seconds of input and is retained separately.
Input/history fingerprints must agree across repetitions. The scope is finite,
not every possible signal or the complete public configuration range. Additional
channel counts, automation paths, signal families and offline TSM are checked by
functional tests and must be timed separately for expanded performance claims.

The plan is written before execution. It records binaries, linked dependencies,
policy and order. Receipts bind output CSV/metadata hashes; complete-grid and
nonnegative-clock checks remain mandatory. The reporter includes second-best
costs and actual success counts, not just a favorable minimum.

## Mandatory engineering gates

Keep compiler C++20/23 builds under GCC and Clang, ASan/UBSan, processing
no-allocation checks, pure C/export/install consumers, deterministic output,
reset/partition/stereo/parameter contracts, and the existing TSan, CLAP and VST3
validator jobs. New internal shortcuts need boundary/overflow/alias tests and
independent reference comparisons. Do not bypass branch protections or failed
correctness tests to achieve performance acceptance.

For behavior-preserving DSP optimization, demonstrate the same numerical result
and whole-output equality on the declared replay suite; preserve latency, ABI,
profiles, state and tails. For audio-changing algorithms, separate objective
and listening review still applies. Lack of a current native vendor baseline
must limit comparison claims, not block a verified exact-output optimization.

CI validates the protocol, receipts, regression/calibration tests and functional
execution. Shared-runner absolute timings are retained as diagnostics. A local,
predeclared same-machine capacity result is reviewed with its raw evidence; it
is not replaced with the most favorable hosted run. Environment failures do not
turn into false functional passes, and all test pipelines use `bash`/`pipefail`.

## Reproduction

Build the ordinary product and independent audit; no research worktree is needed:

```sh
cmake -S . -B build-sdk -G Ninja -DCMAKE_BUILD_TYPE=Release
cmake --build build-sdk -j2
ctest --test-dir build-sdk --output-on-failure
cmake -S bench/rt_audit -B build-audit -G Ninja -DCMAKE_BUILD_TYPE=Release
cmake --build build-audit -j2
python -m unittest discover -v -s bench/rt_audit -p 'test_*.py'
python bench/rt_audit/run_matrix.py --matrix capacity --count 1200 \
  --probe product="$PWD/build-audit/rt_audit_probe" \
  --dependency "$PWD/build-audit/backend/libboiled_egg.so" \
  --policy bench/rt_audit/capacity-policy.json --output results/capacity
python bench/rt_audit/capacity.py results/capacity \
  --output results/capacity-report.json --envelopes results/capacity-states.csv \
  --require-capacity
```

For a paired baseline/candidate run, pass both `--probe` and all linked libraries.
`--reference-label before` reports same-functionality relative regressions.
`--require-capacity` applies to all labels, including the reference; omit it when
retaining a known failing old baseline and explicitly review the candidate and
relative results. Never compare relative costs as interchangeable functionality
when profiles, algorithms or formant policies differ.
