# Roadmap C1: main-based SDK preview qualification — 2026-09-16 JST

## Decision and boundary

PR29 on integration/main-sdk-preview extracts the validated SDK from the stacked
preview chain onto stable main. Base da66001ea2381a938f227a36fe0319d0dc429945;
donor bddc2eca9f0a2c9a801914df75dd34b76bed83e9 (PR28). This is not another phase
algorithm or blanket research promotion. The source selection/compatibility gates
permit SDK-only integration with compile-time OFF and per-instance opt-in intact.

Existing main adapters, IDs, state and UI remain unchanged, including WSOLA as
their processing path. PR9's ReaPitch-inspired GUI and adapter feature/state
migration are deferred to C2. Existing main evaluation and research trees are
preserved, not replaced by the accumulated research branch. No new HPSS, edge,
phase-gradient or transient-transport experiment is included. The private kernel
support needed by the qualified preview remains private and is not installed.

General natural-audio quality selection, frozen perceptual-model validation,
manual DAW sessions and native-zplane comparisons are separate unfinished work.
No listener ratings, model inference or subjective score is produced here. This
qualification concerns backwards compatibility and availability of an opt-in SDK.

## Commits and source identity

- 4ad89466: main-based C1 scope and acceptance before integration testing.
- df58e2af: exact donor SDK/header/test extraction, excluding donor adapters and
  unrelated research. The root CMake retains main's adapter wiring.
- ccd2d126: previous-header C/C++ binary probes and fail-closed extraction audit.
- 0ea14ed6: direct preview matrix, legacy binary compatibility and existing-host CI.
- 91a49b7f: SDK preview usage guide; documentation only.

Validated code checkpoint 0ea14ed682b781047743891ab12a628a4ec7731e has tree
2c96219a05b6b3cac0a17e09d0afa92defe33e86. Later guide/this report are documentation.

The downloaded baseline artifact10403299493 verifies132 tracked files and tree
6a3f2a6204a0a74d9175893360fdf36252d4851d. The prior PR28 source bundle verifies223
files and tree52c7e01716452c309e3d5dfdbb23dfc5951999c0. The new source audit compares
all33 src/include files against that donor and protects54 main files (complete
adapters/eval/research trees plus the legacy header/WSOLA/profile sources).
No public legacy struct/enum in boiled_egg.h changed; backend.h adds extension
names and functions without reinterpreting the legacy formant enum.

The extracted and independently built donor shared libraries are byte-identical
in the local GCC14.2 Release build:
218abecb11273524ad41e42c97d93a7b88889c2a536ab6c74dee1a65ffb63cb8.
This also matches the earlier measured PR28 library in the delivered record.
It is exact reuse, not evidence of a further speed or acoustic improvement.

## New old-binary compatibility evidence

Compile legacy_client.c with the actual previous C11 headers and previous shared
library. Compile legacy_wrapper.cpp once with the previous C++20 wrapper/library.
Run those unchanged executables with original, new preview-OFF, and new preview-ON
libraries. Check ldd resolution before each run, so accidentally using the old
rpath cannot masquerade as successful new-library compatibility.

The C probe covers4 rates, mono/stereo, all3 legacy qualities, streaming/realtime,
3 operation scenarios and blocks32/257:288 rows. It retains complete output hashes,
frame counts, state/runtime/latency/capability hashes and invalid-batch behavior.
Dynamic point events and state/reset behavior are included. Every144 paired
block partition gives the same output/contract. C++12 cases exercise the old
RAII layout, move construction/assignment, parameter state, realtime events and
error translation. There are no new headers used by these two old clients.

| Comparison | Complete exact history pairs |
|---|---:|
| Previous C executable: original vs candidate OFF |288/288|
| Previous C executable: original vs candidate ON |288/288|
| Previous C++ executable: original vs candidate OFF |12/12|
| Previous C++ executable: original vs candidate ON |12/12|
| Donor vs current preview histories |156/156|

The preview replay is the inherited144-static/12-dynamic full-history test, with
same-toolchain builds and no output fitting. Nine hundred total legacy executions
across three libraries are not900 independent quality fixtures. No broad natural
stereo claim is inferred from binary or finite-grid equivalence.

All31 previous dynamic symbols remain. Exactly8 declared C extension functions
are added; private research/C++ symbols do not leak. Five new Python calibration
tests reject missing/duplicate grids, changed histories, invalid frame metadata,
changed protected sources, removed symbols and private/unexpected exports.

## Local and hosted verification

Local GCC14.2 C++20 and C++23 preview ON:26/26 CTests each. Preview OFF:13/13.
Installed ON/OFF C11/C++/ramp consumers:3/3 each. New auditor tests:5/5. Complete
compatibility and donor replay above were run locally and repeated independently
in CI. The unchanged runtime carries the existing no-allocation, exact duration,
stereo, low-tone/alias and automation regressions; thresholds were not lowered.

The local C++23 combined build/test command hit the tool's execution time limit
partway through CTest. Its partial log remains; the already-built test suite was
then run to completion,26/26. A supplementary attempt to rerun the old240-output
standalone stereo/time audit hit the same tool time limit after196 measurement
files. That partial directory is retained and is NOT reported as a completed
240-case result or used for eligibility. C1 uses the complete direct stereo tests,
156-history replay and identical donor binary, not a fabricated completion count.
No new CPU timing matrix or new natural-corpus render trial was claimed/required
for this byte-identical runtime extraction. Earlier cost evidence remains inherited.

Code checkpoint workflows:
- sdk-preview-integration35080535918:9/9 jobs successful.
  Four GCC/Clang20/23 direct ON builds; old-binary/source/export replay; OFF and
  installed consumers; full ASan+UBSan; four TSan legacy/spectral/ramp tests;
  static ON; unchanged CLAP and VST3 adapters built with preview ON.
- Existing product ci35080536170:successful, including original adapter/default,
  ABI/export/install and instrumentation gates.
- Existing rt-measurement-audit35080535924:successful.

The unchanged VST3 adapter with preview ON passes the official validator:
47 tests passed,0 failed. Unsupported-rate rejection messages in its log belong
to the validator's negative checks, not hidden failures. No new graphical editor
or manual commercial-DAW session is claimed by these automated adapter checks.

Downloaded GCC20 artifact10440341140 has SHA256
3fc9eaf0142f34a270451a0a1a36bbe9d9f37f9cdf41df0ae78f0c0d01cdd5e2.
ZIP CRC and all188 tracked source hashes verify;186 initially present local files
match, with only the remote protocol/workflow initially absent. Those two were
then restored from the artifact. Synthetic PR merge bc6402518916f58968a47b01671945e93a0acea3
has the same2c96219a tree. The artifact independently confirms the exact old-client
counts and156 preview pairs. The VST3 log artifact10440350916 also verifies CRC
and its recorded SHA256. Compiler-dependent audio hashes are not compared across
local/CI environments; each comparison is within its own toolchain.

## Adoption and remaining roadmap

This permits main-facing availability of the experimental SDK, not switching the
default DSP or declaring commercial-quality parity. Merge status is recorded in
PR29 and roadmap #18, rather than guessed in this pre-merge validation document.
Use docs/SDK_PREVIEW.md for build/configuration and unsupported combinations.
Do not apply the historical stereo patches again.

C1 covers the SDK portions of #8/#9/#10 and the qualified static repair from#28.
It does not close Issue1/2 or all earlier research/GUI PRs. C2 should move the
existing plugin processor/editor/events/state onto the new main API as a separate
change with old preset/parameter/ID and host tests. The objective-quality model
work in B remains independent; no new listening response is a prerequisite for
this exact numerical/ABI integration.
