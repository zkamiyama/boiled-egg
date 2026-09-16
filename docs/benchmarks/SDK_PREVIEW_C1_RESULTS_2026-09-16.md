# Roadmap C1: SDK-only preview integration decision — 2026-09-16

## Decision and exact boundary

PR #29 extracts the validated opt-in spectral SDK onto stable main without
merging the research branch chain. The scoped integration is cleared by the
objective compatibility checks below. The actual merge status and commit are
recorded by the PR merge event, not assumed in this pre-merge document.

Original main: da66001ea2381a938f227a36fe0319d0dc429945.
SDK donor: bddc2eca9f0a2c9a801914df75dd34b76bed83e9 (PR #28).
Validated implementation: 64253b15b57bdf9833197e584850ceca81b14143.
Implementation tree: 89d81c406c09616ac435110474fa3c7302b89c1a.
This commit only adds the result record; it does not alter the tested code.

The implementation and initial CI were already present when this continuation
resumed. This pass reviewed the extraction, downloaded CI artifacts, rebuilt
original/OFF/ON and donor libraries, re-executed old clients, and completed the
integration decision. Inherited implementation is not a new DSP invention.

## What becomes available

The SDK includes explicit PV backend configuration, independent Off/Harmonic/
Monophonic formant policies, continuous pitch with fixed reported latency, and
explicit pitch/time ramps with input-sample durations. Time-varying stretch stays
in variable-rate push/pull; fixed-I/O time remains 1. See docs/SDK_PREVIEW.md for
supported rates, channels, ratio coupling, flags and build commands.

BOILED_EGG_ENABLE_EXPERIMENTAL_SPECTRAL remains OFF by default. An ON build still
requires BOILEDEGG_BACKEND_ALLOW_EXPERIMENTAL per instance. Availability reports
UNAVAILABLE when not built and EXPERIMENTAL when built. Ordinary create/create_ex
calls keep WSOLA and do not reinterpret legacy FORMANT_PRESERVE as implemented.

Existing main CLAP/VST3 adapter sources, IDs, state and UI are unchanged. They
continue using WSOLA even when this expanded SDK is compiled with preview ON.
The ReaPitch-inspired editor and adapter feature migration from PR #9 are a
separate C2 task, not part of this merge. No phase-gradient, HPSS, edge or transient
research directories, new automatic classifier, historical experimental patch
chain, trained quality model or competitor library is imported into the product.
Private PV support remains private and is not installed or dynamically exported.

## Source and binary review

The complete main tree was restored from the prior audit archive, excluding its
added evaluation files and generated caches. Its reconstructed Git tree equals
6a3f2a6204a0a74d9175893360fdf36252d4851d (132 tracked files), the actual main tree.
This equality includes file modes and contents; it is not an inferred filename
match. The CI source archive for #29 contains 190 tracked files. Its complete
Git tree matches the validated implementation tree above.

The existing extraction auditor verifies all 33 src/include files against the
independent PR #28 donor. All 54 protected main files also match: complete
adapter, evaluation and existing research trees, original boiled_egg.h, WSOLA
engine sources and profile implementation. CMake/test additions are reviewed
separately. The implementation adds 58 files and modifies 7 relative to main;
this documentation adds one further file.

The old exported C surface has 31 symbols. Both OFF and ON libraries retain
all of them and add exactly 8 declared formant/state/ramp/info functions. No
private research or C++ symbol is exported. Original public structures/enums
remain; old clients are not recompiled against new headers to hide ABI changes.

## Fresh local replay in this continuation

Linux GCC 14.2, C++20, Release; the current archive was rebuilt rather than using
CI executables as local evidence.

| Check | Result |
|---|---:|
| Current direct preview ON | 26/26 CTests |
| Current direct preview OFF | 13/13 CTests |
| Original main | 12/12 CTests |
| Installed ON C11/C++/ramp consumers | 3/3 |
| Installed OFF C11/C++/ramp consumers | 3/3 |
| Extraction/ABI/grid negative calibrations | 5/5 |
| Old C executable: original vs OFF | 288/288 histories identical |
| Same old C executable: original vs ON | 288/288 histories identical |
| Old C++ executable: original vs OFF/ON | 12/12 each identical |
| Legacy block32/257 pairs | 144/144 identical |
| Donor vs extracted preview | 156/156 histories identical |

The C and C++ probes are compiled once against the old headers and old library.
The exact executables are then run against original/OFF/ON using an explicitly
checked dynamic-loader resolution. Histories include audio, runtime/latency,
state, invalid-batch behavior and default-backend information. Finite/nonzero
output and complete grids are enforced. Missing, duplicate, changed and leaked
export/source negatives are tested. These counts are compatibility cases, not
independent listening trials or a new objective quality ranking.

The freshly built ON and donor libraries are byte-identical, with SHA256:
218abecb11273524ad41e42c97d93a7b88889c2a536ab6c74dee1a65ffb63cb8.
This is also the measured runtime from the prior integration checkpoint. Its
72-setting cost/capacity qualification is inherited, not mislabeled as another
fresh benchmark in this pass. No timing threshold or DSP arithmetic changed.

## Hosted matrix and downloaded evidence

At implementation checkpoint64253b15 all three triggered workflows succeed:
- sdk-preview-integration35081579720: 9/9 jobs, direct GCC/Clang C++20/23,
  ASan/UBSan, TSan, static install, unchanged CLAP and VST3 with preview ON.
- product ci35081579580: existing default product/ABI/host checks.
- rt-measurement-audit35081579536: existing measurement verification.

The GCC20 job runs the complete old-binary comparison and donor replay; other
compiler jobs run direct preview tests and installed consumers, not a falsely
claimed cross-compiler waveform-identity comparison. Sanitizer and host results
are hosted evidence, not fresh local reruns in this continuation. The normal
VST3 validator log reports47 passed/0 failed; unsupported64-bit processing is
reported as unsupported by the validator, not added functionality.

Downloaded artifact10440317020 has ZIP SHA256
615ca673fd753ddfa9d75ce8613ff626b7e55a64aeff618e5a48ff07207c5860.
Its CRC, all190 tracked source hashes and source Git tree verify. The VST3
artifact10440675757 has ZIP SHA256
be0c3bf71f58c9472ded48b33717dc96260d021c77df2071a4382acab2137499;
its CRC and validator log were also checked. Fresh local logs and immutable
compatibility plans/CSVs retain binary, source and executable fingerprints.

## Roadmap consequence

C1 makes already qualified SDK functionality available without requiring a
research checkout. It does not close broad quality qualification #17, integration
#18, phase research #1, or the original automation issue merely by association.
The old default adapters deliberately stay unchanged. C2 is a separate migration
of the existing, tested host/UI feature set onto this SDK, with old plugin IDs,
state migrations, latency notification and restart behavior checked explicitly.

Natural-audio quality-model validation remains independent. No model is trained
or executed, no new listener scores are invented, no native-zplane output is
created, and no Windows/macOS/manual-DAW or portable realtime guarantee follows
from these tests. The fixed numerical repair and exact integration need not wait
for new listener responses; broader quality claims are not implied by that.
