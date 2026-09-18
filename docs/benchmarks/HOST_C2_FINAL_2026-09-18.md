# C2 host integration: final qualification — 2026-09-18

## Scope and decision

Roadmap #15 / integration #18, PR #30. C1 main is
c6cb312903006e3a1ca24c034c291ef0e8fc9d81. The C2 branch was already at
2d84a940b017dd1268b634fa38cdac910339110e when resumed. The shared one-voice
processor, CLAP/VST3 controls, version2 state, X11 editor, CLAP activation-time
latency notification and live manual configuration handling are inherited work.
This continuation fixes a newly reproduced VST3 named-choice contract, adds
independent state and actual old-plugin comparisons, and verifies the complete
C2 build before the main integration decision.

No DSP or public SDK-header change: all33 files under src/include are byte-identical
to C1 main. No new phase algorithm, audio-quality predictor, natural-audio quality
score, listening response, native-zplane run, manual commercial-DAW session or
cross-platform qualification. This is host feature integration and compatibility,
not promotion of experimental audio processing as perceptually superior.

The spectral build option remains OFF by default; selecting PV explicitly is
required when built. Existing WSOLA semantics, plugin IDs and original normalized
pitch parameter are retained. New plugin saves use version2. New code reads the
old pitch-only state, but old binaries are not promised to read the new state.
Back up plugin binaries and projects before testing an upgraded preview.

## New commits

- 497b931c: independent loaded-VST3 string/state contract reproducer.
- b1c194e7: StringListParameter for structural choices and CTest registration.
- 26a81831 / c85a367c: standalone actual old/new VST3 module replay and build target.
- 42a94342: explicitly pin the reviewed adapter snapshot for source equality.
- af15ef23: CI actual old/new CLAP and VST3 replay and contract evidence.
- 16a759f4: update stale README descriptions of controls, GUI and roadmap.

Validated code af15ef232ced78b8bff5c66a08c79f3e47c91d5c, tree
5205a97cdf175dc8f7f00cfea7d8511fdd6e5393. README and this result are documentation
only. Merge status is checked separately after final PR checks; this record does
not claim a merge had happened before it was written.

## VST3 defect and repair

C2 displayed eight labels across Backend, Quality and Formant Policy but registered
those controls as RangeParameter. Inverse host string conversion failed for all
8 labels and the3 list metadata flags were absent. This was a real public-interface
inconsistency, not an audio-quality finding. The new test loads the actual module
using only Steinberg interfaces, with literal expected labels and state bytes;
it does not call the shared boiled-egg Processor as an oracle.

Use the SDK's StringListParameter for these3 non-automatable structural controls.
IDs, step counts, normalized/plain mappings and initial values remain unchanged.
Other controls still use RangeParameter. The original display implementation and
all DSP/process/state routines are unchanged by this fix.

Same executable against preserved pre-fix and corrected modules:

| Check | Pre-fix C2 | Corrected C2 |
|---|---:|---:|
| Named label round trips |0/8|8/8|
| Correct list flags |0/3|3/3|
| Rejected malformed/truncated states |71/71|71/71|
| v1 migration and partial stream read/write |pass|pass|
| Contract executable exit status |2|0|

The71 negatives are all64 prefixes of the64-byte state plus7 corrupted-field
cases, including nonfinite values. During activation, each rejection leaves the
saved state, control values and reported latency unchanged. The test separately
exercises successful3-byte chunked stream reads and writes. It does not claim an
exhaustive state fuzzer or audio-history equality for every malformed input.

Primary API basis: StringListParameter provides both toString/fromString and list
metadata, https://steinbergmedia.github.io/vst3_doc/vstsdk/classSteinberg_1_1Vst_1_1StringListParameter.html .

## Actual legacy-plugin comparisons

Build the previous C1 CLAP and VST3 modules and current C2 modules with the same
GCC14.2/toolchain and pinned dependencies. The host probes include no boiled-egg
headers, do not link its library and do not use the new shared Processor as a
reference. Feed literal old state, then deterministic audio and original pitch
parameter events through each public plugin ABI.

For EACH format:4 rates44.1/48/88.2/96k x blocks32/257 x initial pitches-12/0/+12
x static/dynamic histories =48 conditions. Input is24001 frames followed by the
declared delay; dynamic offsets777,4101,12289 request+7,-5,0st. Preserve exact
complete output fingerprints, frame count, latency, tail and final saved pitch.

Both CLAP and VST3 pass48/48 old/new comparisons and24/24 block-partition pairs.
All four local CSVs, and corresponding CI comparisons, have SHA256:
5e9cc578dcc636918c26314fb5132d3a2779e6dba7b3b5e931ef42947a71773e.
Identical CSVs here are matched-engine legacy compatibility evidence, not a claim
of cross-compiler bit identity or96 independent quality samples. The new v2 state
bytes are intentionally not identical to old v1 bytes; decoded legacy semantics
are compared. This strengthens the earlier shared-Processor/C-API tests with
actual independently loaded old plugin modules.

## Complete local host/GUI validation

Fresh GCC14.2 C++20 static-core build, spectral ON, CLAP+VST3+X11:38/38 CTests pass.
The inherited pre-fix snapshot passed37/37; the new38th test is the named-choice/
state contract. Normal Steinberg validator passes47 tests with0 failures.
Existing loaded tests each exercise32 dynamic/state/in-place cases and verify
zero audio-processing allocations. Actual X11/XEmbed keyboard/numeric entry,
sliders, host gestures, resize and timer lifetime tests pass for both formats.
The displayed editor image is a screenshot of the loaded CLAP, not a mock-up.

The inherited CLAP lifecycle/live-configuration checks remain active: structural
changes are staged while the current DSP remains in use, cancellation and invalid
batches do not rebuild/mutate the active engine, and latency changes are notified
in activation. Backend/quality/formant-policy changes still require reactivation;
ordinary pitch, fine/formant and mix parameters are automatable.

Two independent CSV/grid-auditor tests pass; they reject missing, duplicate,
changed and block-dependent histories. Source identity independently confirms
all33 runtime/header files unchanged from main.

## Instrumentation boundary, including the unsuccessful extra attempt

Hosted address/undefined and thread instrumentation of the actual shared C2
processor and core passes its declared4-test scopes; SDK CI separately exercises
the core's ASan/UBSan and thread tests. These scopes are not described as every
GUI/third-party SDK test under every sanitizer.

An extra local full CMake VST3 ASan/UBSan build with leak detection did NOT finish:
the instrumented external Steinberg validator -selftest completed43 checks but
reported5082 bytes in79 leaked allocations in its test-registration paths, before
loading the boiled-egg module. Both unsuccessful logs are retained. No leak
suppression, test threshold change or disabled hosted gate was introduced.

To isolate our new interface path, build the instrumented libraries/contract host
and compile/link the exact VST3 target objects with the generated compiler/link
commands, separately from the external validator selftest. With
ASAN_OPTIONS=detect_leaks=1:halt_on_error=1 and UBSAN_OPTIONS=halt_on_error=1,
the actual instrumented headless VST3 and instrumented contract host pass all8
labels/71 rejection cases and partial-stream checks. This is a direct module
diagnostic, not a successful complete sanitized CMake/validator build. Its
commands and result are retained. Normal uninstrumented validator remains47/0.

## CI and exact-source check

All four workflows at af15ef23 completed successfully:
- host-preview-c2 35302394248: GCC/Clang20/23 spectral ON, GCC20 OFF, X11 tests,
  actual old/new comparisons, and separate address/thread instrumentation.
- sdk-preview-integration 35302394239: legacy SDK clients, runtime/header and
  protected source equality, preview matrices, install/static/sanitizer checks.
- clap-live-controls 35302394249: dedicated active-configuration contract.
- ci 35302394295: existing product/ABI/host validation.

An earlier SDK audit correctly failed at b1c194e7 with 'protected adapters tree
changed' because its expected C2 snapshot predated the reviewed VST3 change.
Commit42a94342 pins c85a367c as the explicit expected adapter tree. The equality
check, old SDK source protection, replay grids and thresholds remain intact.

Downloaded artifact10529924492 ZIP SHA256:
4bcf9b988257a1cf2d0d832efd924ebdc75efa57ce5338969f03a5416364c241.
CRC and all216 tracked source hashes verify and match local validated code.
Its synthetic merge0ce02bb83f2ff5ab23081d5fd73d3f11e7830926 has the same
5205a97c code tree. CI independently records48/48 comparisons per format and
8/8 label round trips with71 state rejections. Documentation-only later commits
must not be reported as new numerical or performance experiments.

## Usage and limits

```sh
cmake -S . -B build -G Ninja -DCMAKE_BUILD_TYPE=Release \
  -DBOILED_EGG_BUILD_SHARED=OFF \
  -DBOILED_EGG_ENABLE_EXPERIMENTAL_SPECTRAL=ON \
  -DBOILED_EGG_BUILD_CLAP=ON -DBOILED_EGG_BUILD_VST3=ON \
  -DBOILED_EGG_PLUGIN_UI=ON
cmake --build build -j2
ctest --test-dir build --output-on-failure
```

Output CLAP:build/adapters/clap/boiled_egg.clap. VST3 bundle:
build/VST3/Release/boiled egg.vst3. Select Spectral PV explicitly; structural
changes require host reactivation. The Transient spectral delay at48k is2112
samples (44ms); the GUI reports it. Dry/bypass have matching delay. This is
one voice, float32 stereo, Linux X11. No native Windows/macOS/Wayland editor,
multi-voice feature, dynamic-time insert contract or new live-monitoring latency
qualification. Old projects use WSOLA semantics; retain backups because plugin
IDs are intentionally preserved and new saves use v2.

No new CPU-time, natural-music acoustic, native-zplane, predictor or human-rating
experiment was performed. Existing DSP cost evidence is inherited, not relabeled.
The next independent roadmap work remains natural-audio objective-model validation
and declared host/platform coverage, not another reconstruction of C1/C2.
