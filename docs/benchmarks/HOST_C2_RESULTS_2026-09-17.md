# C2 host integration and live-configuration repair — 2026-09-17

## Decision and scope

PR #30 continues roadmap #15 / #18 after the merged C1 SDK. Main base is
c6cb312903006e3a1ca24c034c291ef0e8fc9d81. The C2 branch exposes the already
implemented one-voice CLAP/VST3 controls, state and Linux X11 editor on that SDK.
WSOLA remains the default. Spectral compilation remains OFF by default and the
explicit preview choice enables its per-instance flag. No src/include DSP or
public ABI changes, no new quality algorithm or trained perceptual model.

This record supports scoped Linux host integration, not universal DAW/platform
qualification. Existing plugin and original pitch IDs/range/normalization remain.
Version1 states load with WSOLA semantics; version2 stores the additional controls.
Preserve copies of old plugins/projects: saving v2 is not a promise that an older
v1-only binary can read it. No new listener ratings, native-zplane result or
acoustic-superiority claim is made.

## Inherited versus new work

At resumption, integration/main-host-preview already reached 9b430cf4 with
extracted adapters, latency-change notification, host/GUI regression tests and
successful CI. That implementation is inherited, not newly invented here.
The downloaded starting artifact10475673565 verified209 tracked file hashes.

This continuation adds:
- a380a553: live-configuration contract before implementation;
- 124669dc: CLAP live configuration, atomic rejection/cancellation tests, standard
  bypass/enum flags and explicit audio-thread opt-in in the shared processor;
- 70fe32d6: exact C2 adapter snapshot for the existing SDK compatibility audit;
- b845bae8: address/thread instrumentation of the actual loaded CLAP module;
- 4cd99407: standalone legacy pitch-only replay against the old C API call pattern.

Validated code is4cd99407f39db6319289a0aa91d6c8996a6d4b53. Its CI synthetic merge
b66427c3c24b500631d8a256df4735e28a04c062 has tree
b0874d9afa507820f0d5d11ebc7a3a67421dd015. Later result/README changes are documentation.

## Reproduced interoperability defect

The CLAP parameter contract allows live manual host edits even when a parameter
is not automatable. Those edits may arrive in process(), not only params.flush().
The inherited adapter parsed backend/quality/policy events but the common
processor rejected all nonautomatable controls, so a valid manual host operation
could return CLAP_PROCESS_ERROR during playback.

The new actual-module test fails the inherited binary with
"valid live configuration rejected by process". A separate metadata negative
also detects its missing configuration enum flags. These are preserved negative
results, not inferred bugs from a code inspection alone.

## Repair behavior

The common processor retains strict automation-only handling by default. CLAP
explicitly enables the live-configuration path; VST3 controller/restart behavior
and ordinary automation processing are not silently reinterpreted.

Every event group is validated in full before any sample is processed or target
published. Same-offset values are validated together. A valid configuration change
is a pending request: the active DSP, active controls and latency stay unchanged.
Controls arriving while the different configuration is pending are staged with
that configuration, not applied to an incompatible active engine. Returning to
the active configuration cancels the request and resumes compatible accumulated
controls at the stated event position.

The host is asked to schedule its main-thread callback/restart; the DSP is created
only during reactivation. This is not a guarantee of clickless engine switching
or a waveform crossfade across host stop/start. CLAP latency notifications remain
inside activate(), never in the audio process callback. No processing allocation,
lock, DSP construction or main-thread-only host call is introduced.

The existing bypass parameter now advertises CLAP_PARAM_IS_BYPASS. Backend,
quality and formant policy advertise CLAP_PARAM_IS_ENUM and remain nonautomatable.
Parameter IDs, ranges and state encoding are unchanged by this fix.

## Direct local verification

| Scope | Result |
|---|---|
| GCC14.2 C++20, spectral ON, both real plugins and X11 |37/37 CTests|
| GCC14.2 C++20, spectral OFF, both plugins and X11 |24/24 CTests|
| Clang17 ASan+UBSan/leaks, spectral ON, headless actual CLAP |33/33 CTests|
| New live-event module scenarios, ON |16/16; zero process allocations|
| Same scenarios, OFF |8/8; no unavailable-PV substitution|
| Legacy pitch-only direct API replay |72/72 exact output/latency histories|
| Normal Steinberg validator |47 passed,0 failed|

The16 live scenarios cover4 supported rates, blocks32/257, and initial WSOLA/PV.
They check active-output equality during pending changes, joint controls, cancel,
reactivation and latency notification. An invalid later event leaves in-place
output sentinels, saved state, restart requests and subsequent DSP history intact.
The expected active stream uses a separately controlled instance of the common
processor: integration evidence, not an independent acoustic oracle.

The72 legacy histories cover4 rates, blocks32/64/257, initial pitch-7/0/+12st,
and with/without two nonzero automation changes. The comparison calls the public
C API in the old pitch-only pattern and independently splits audio at the event
positions. It is not a new execution of an old compiled plugin binary. This
standalone probe is committed and passed locally; it is not registered as a CTest
or claimed as an additional hosted CI gate.

The inherited loaded tests still pass32 CLAP and32 VST3 dynamic/state/in-place
cases, including version1 restoration. Actual X11 tests exercise numeric editing,
sliders, resize, host gestures, restart display and timer cleanup in both formats.
The delivered screenshot is captured from the newly built loaded CLAP module,
not an image mockup. Repeating those tests to capture it is not new audio evidence.

An earlier full local test invocation was interrupted by the execution time limit;
its partial log is retained. The subsequent full run completed37/37 and is the
reported result. No failure was suppressed or threshold relaxed.

## Hosted verification

At4cd99407 all four workflows complete successfully:
- host-preview-c2,35218505250: GCC/Clang C++20/23 spectral ON, GCC20 OFF, actual
  CLAP/VST3/X11 tests and common-processor address/thread checks;
- clap-live-controls,35218505220: actual loaded CLAP module under address and
  thread instrumentation,6/6 targeted tests for each instrumentation;
- sdk-preview-integration,35218505290: SDK ON/OFF/static, installed consumers,
  old-client/ABI and exact donor-runtime replay;
- ci,35218505150: existing product checks.

The host matrix tests the current checkout. The SDK audit still checks exact
src/include equality and unchanged eval/research; its adapter reference is an
explicit reviewed snapshot124669dc, not a wildcard waiver. Inherited CI success
is not substituted for these fresh checks.

Downloaded final artifact10495926777 ZIP SHA256:
be566492a4298ddfdaa4fe6527709be95b69e53543078da46833505b6688f367.
CRC and213 tracked source hashes verify. All computational local files match.
One local workflow had the prior pointer and two protocol/workflow files were
initially remote-only; they are not DSP/test-source discrepancies. The verified
archive is the authoritative delivery source.

Against the separately downloaded C1 main source, all33 src/include files and
45 eval/research files remain byte-identical. The build uses pinned CLAP1.2.10
and VST3 dependency sources. They were obtained for the independent build but
are not redistributed in the delivery. No fonts are included.

## Delivery, use and remaining boundaries

The Linux x86_64 binaries are locally built from code matching the verified
checkout, not binaries downloaded from CI. Both formats embed the SDK and have
no libboiled_egg shared-library dependency. Normal system C/C++ and X11 libraries
are still required. This is not a portable Linux ABI guarantee for every distro.

Build both plugins and enable the explicit spectral option with:

```sh
cmake -S . -B build -G Ninja -DCMAKE_BUILD_TYPE=Release \
  -DBOILED_EGG_BUILD_SHARED=OFF \
  -DBOILED_EGG_ENABLE_EXPERIMENTAL_SPECTRAL=ON \
  -DBOILED_EGG_BUILD_CLAP=ON -DBOILED_EGG_BUILD_VST3=ON \
  -DBOILED_EGG_PLUGIN_UI=ON
cmake --build build -j2
ctest --test-dir build --output-on-failure
```

The spectral fixed-I/O path keeps time ratio1 and total pitch within+/-12st;
WSOLA retains+/-24st. Backend/quality/policy changes need host reactivation.
Dry and bypass are delay compensated. At48k the spectral Transient path reports
2112 samples/44ms; General and other rates have their declared, different delays.
Do not equate small callback sizes with low monitoring latency.

Native GUI scope remains Linux X11/XEmbed, one shifter, float32 stereo. No
Windows/macOS/native-Wayland UI, multivoice Add, live variable-time insertion,
manual commercial-DAW project test or new full-plugin CPU benchmark was completed
in this pass. The numerical DSP/performance evidence from C1 is inherited and
not relabeled as a new timing experiment. General natural-audio quality selection
and frozen objective-predictor validation remain independent roadmap work.

Final merge state and post-merge CI must be checked after this record is committed;
this document alone does not assert that main already advanced.

Primary protocol references:
https://github.com/free-audio/clap/blob/main/include/clap/ext/params.h
https://github.com/free-audio/clap/blob/main/include/clap/ext/latency.h
The same relevant contract is present in the pinned local1.2.10 headers.
