# Continuous pitch, fixed delay and native editors — 2026-09-14

## Delivery and scope

Draft PR9 is stacked on the static spectral preview PR8, not on stable main.
Validated code: `146bd9080b8a851e17ee50907d89141e1b6e2bea`. The ordinary WSOLA
default remains; the spectral path still requires explicit build and instance
consent. Main remains `bfbb6fd0b8196a99a29f6fd4989a467deeeaf1af`. This record
changes documentation only. No blind-listening/native-zplane or cross-platform
promotion is claimed.

The resumed session found `eecea7d27169f980339e59d9acfdfbf7c893876b` already
containing the interrupted source-clock DSP, shared controls, actual adapters
and native editor. It restored that work rather than claiming it was newly
invented during resumption. Initial163 tracked hashes and artifact CRC/SHA256
were verified. This pass completed missing CI, fixed actual editor interaction
bugs, added raw-evidence validation and real-corpus replay, and built tested
self-contained plugin modules.

## Implemented contracts

One preallocated source history stores `V(u)=integral(T*p(u)du)`, effective pitch
and formant values. Synthesis frame centers and resampling use the same mapping.
Pitch targets ramp linearly in ratio over10ms of input time; new targets start
from the current effective ratio. Phase/read positions are not reset by events.
Caller partitioning does not govern the ramp. Time ratio stays constant: realtime
requires T=1, streaming permits fixed T in[.5,2], with p in[.5,2] and T*p<=2.
Dynamic time automation is rejected. Without CONTINUOUS_PITCH, the old static
preview path remains available.

Fixed latency uses the minimum supported pitch across the full range, not the
current knob value. Transient:2112samples at48k/4160at96k (44/43.333ms).
General:3648/7232 (76/75.333ms). Latency remains fixed under pitch/formant events
but differs by quality/rate. This does not claim another reduction relative to
static unity-pitch compact latency. Query runtime_info; it is distinct from the
streaming input-lookahead hint. Dry and bypass are delay compensated. Spectral
response has window spread despite precise input event timestamps.

The existing CLAP/VST3 IDs and original pitch parameter normalization remain.
New controls are fine pitch, formant/fine formant, Wet/Dry, wet-voice volume,
balance pan, bypass and explicit backend/quality/policy. Continuous controls are
automatable; backend/quality/policy require host reactivation outside process.
Malformed event batches are rejected transactionally. Coupled UI state uses
bounded atomic snapshots and retains a prior valid configuration without spinning.
Version2 uses64-byte little-endian state; old CLAP16/VST3 12-byte pitch-only states
migrate to default WSOLA controls. Existing IDs mean preview binaries should be
tested with project copies, not installed as a second supposedly separate plugin.

The shared editor is original X11/XEmbed code, inspired by ReaPitch's grouping
of pitch/fine, independent formants, Wet/Dry, volume and pan. It is **one shifter**,
not multiple voices or a pixel clone. Numeric editing, wheel, keyboard, resize,
timer lifetime and begin/value/end host gestures are implemented. Native UI is
verified on Linux X11 only, float32 stereo; no Windows/macOS/Wayland-native or
manual commercial-DAW session qualification. GUI operations stay off audio threads.
See `docs/DYNAMIC_PITCH_EDITOR.md` for API and build instructions.

## Resume fixes and retained failure evidence

| Commit | Change |
|---|---|
|4ccac8ab|Activate missing read-only dynamic/editor CI|
|a407717c|Close hide/focus gestures, relative Wet/Dry wheel, integral keyboard edits|
|172a65fb|Remove completed one-shot source-publication workflow|
|a736273c|Reject noncontiguous warmup/different state; capacity-gate calibration|
|8948516f|Instrument actual shared plugin processor and coupled state with ASan/TSan|
|362b0bc8,bbc3c534|Complete-grid natural dynamic replay and regression tests|
|c8ed7d32|Declare SoundFile test dependency in CI|
|ca794aa3,ae9ab277|New contracts, old-doc scope and original-import provenance|
|146bd908|Distributable static-core modules plus dependency checks|

The pre-fix native interaction test failed: hiding while dragging left an accepted
host gesture open. The repaired test closes all8 accepted gestures and also checks
focus loss, wheel independence from pointer height, binary key steps and resized
coordinates. A first overly broad FocusOut handler canceled numeric editing when
X11 acquired explicit focus (NotifyPointer); it was corrected to distinguish
that event from genuine focus loss. The failed log is retained. No GUI test sleep
or X call is present in the audio callback.

The original imported private-source manifest remains historical; it has not
been rewritten to misrepresent edited timeline files as an unchanged import.
Same-kernel private/public routing tests are not an independent acoustic oracle.

## Objective dynamic tests

Analytic tones55/220/6200Hz,48/96k,General/Transient,Off/Harmonic/Monophonic:
36 paired trajectories at block32 versus257,72 renders and252 settled plateaus.
Pitch changes traverse -12,-7,-3,+3,+7,+12,0st. No fitted alignment or normalization;
only the declared API delay is removed. Independent long-double integration is
also tested in C++ over25000 inputs.

Local max settled pitch error **0.0388842cent**, stereo relation error
**7.6087e-8**; all252 plateaus pass predeclared5cent/1e-5 controls. Frequency is
estimated independently via zero-padded Hann interpolation. This is settled-tone
accuracy, not an assertion of instantaneous transition or all-material accuracy.
The worst trajectory p95 is23.6754cents at48k/Transient/Monophonic/55Hz using
20ms median Hilbert estimates; the diagnostic spans transitions and is not gated.
Max plateau ripple is1.35337dB at96k/Transient/Monophonic/55Hz/+7st. The6200Hz
plateau maximum is0.092267dB. Ripple is reported, not retrofitted with a pass limit.

Additional C++ tests cover40 dynamic fixed-delay/partition/duration cases across
all four declared rates, in-place/reset, constant nonunit stretch, zero/short input,
malformed batches and state. The public .5..2 pitch map is not a variable-time
map; unsupported changes remain errors.

### Supplied natural audio

Twenty original mono44.1k test references x2 qualities x3 formant policies gives
**120 paired streams /240 renders**. Seven pitch targets at fixed source fractions,
with independent formant events where enabled. Blocks32 and257 produce identical
float sample arrays, including the complete fixed-delay prefix, in120/120 cases.
The output after delay has exactly the source frame count. Source/loaded-library/
analysis hashes and the complete grid are verified. No audio is redistributed.

This is same-kernel integration evidence, not native-vendor or perceptual quality.
The maximum raw sample peak is1.900475;61/120 conditions exceed unity. Float samples
above unity are not silently limited or presented as confirmed audible defects.
No new MOS, onset ranking or native-zplane pitch results are produced by this task.

## Practical capacity: preserve tails instead of moving the goalposts

Same local VM,CPU0,wall-only,24 configurations:48/96k xGeneral/Transient x3formant
policies x32/64frames, stereo. Two pitch and two formant events per callback.
Three repeats with1200 steady states each; warmup consumes the declared latency
plus0.5seconds and is retained. No build/evaluation workload overlaps these repeats.
Total86400 steady calls plus67986 cold calls. Per-state output fingerprints must
match across repetitions. No external-clock subtraction or discarded outliers.

The pre-existing rule is maximum over states of best-of-three time <=80% period.
**24/24 pass; worst state-best ratio0.378564**. This is empirical processing
capacity, not a synthesized uninterrupted run, p99, WCET or hard-RT guarantee.

| Rate / block | General worst-policy state-best ratio | Transient |
|---|---:|---:|
|48k /32|0.124911|0.066504|
|48k /64|0.091922|0.059000|
|96k /32|0.378564|0.193098|
|96k /64|0.254435|0.145251|

Local raw period misses98/86400, maximum wall/period28.148163;53/72 actual full
steady runs stay below period. All raw samples and second-best statistics remain.
This benchmark measures the public dynamic SDK, not the whole plugin mixer/editor
or a DAW audio graph. It does not prove the physical cause of the remaining tails.
Final parser calibration rejects modified fingerprints, misplaced warmup, missing
states and repeated runs, and preserves a synthetic raw miss despite a capacity pass.

On the independent final CI runner the same24 capacity settings pass, worst
state-best0.451665,zero raw misses and72/72 steady runs below period. Local98 misses
are not replaced with those favorable CI results. No portable guarantee is inferred.

## Software and host validation

| Scope | Result |
|---|---|
|GCC14.2 /Clang17 x C++20/23, spectral ON|17/17 each|
|Clang ASan+UBSan, leak detection, spectral ON|17/17|
|Default spectral OFF|12/12|
|Actual loaded CLAP/VST3 plus editor, shared core|25/25|
|Distributable static-core plugins plus editor|25/25|
|Actual plugin processor/state tests, ASan+UBSan/leaks|3/3|
|Actual plugin processor/state tests, TSan|3/3|
|Python analytic/capacity/replay calibration|12/12|
|Steinberg normal validator|47passed,0failed|

Loaded CLAP and VST3 tests each cover32 dynamic/state/in-place cases, plus native
editor interactions. They exercise actual module ABIs, not merely compile the
adapters. Processing allocations are intercepted and tested. The instrumented
plugin processor has two simultaneous audio owners on separate instances and a
concurrent coupled-state UI writer. GUI/window operations themselves were not
run under a full commercial DAW/thread sanitizer session.

Pinned CLAP195b42a004144fab0b3cf95e9c067187d15365b7; VST3 SDK
9fad9770f2ae8542ab1a548a68c1ad1ac690abe0 with recorded submodules. Self-contained
means no separate libboiled_egg.so; X11, C/C++ runtime and standard system libraries
are still required. The distributed modules are from the successful Ubuntu24.04
CI static-core build. No external SDK source or font files are in the plugin ZIP.
The screenshot is captured from an actually loaded local build of the same source.

## Hosted CI and exact source identity

At code146bd908, all five PR workflows succeeded:

- dynamic-pitch-editor34829116982: dynamic checks/capacity and actual static-core editor modules.
- dynamic-plugin-sanitizers34829116973: actual shared processor address/undefined/thread instrumentation.
- spectral-backend-preview34829117031: explicit ON/OFF, install/static/exports and sanitizers.
- existing product ci34829117024: compiler/sanitizers, ABI, CLAP/VST3 and installed consumers.
- rt-measurement-audit34829117041: existing measurement/regression controls.

Artifact10341316916 has outer SHA256
48c3ed675f710ff2c25b900495952e2dab54ab3e47ff684e1abba54cc8c1c91d.
All170 source hashes match the measured local source after adding the two
connector-published workflow files. Its synthetic PR merge commit is
5c777d99b9d90b4e6de1c03d4ea1665c8c7237d5; tree
0acb8acb8d87f916af2e29755cd60ac521f27a28 matches the validated head's file tree.
Exact-source local rebuild again passes17/17 and retains the loaded-library hash
106f524edd536c29032d4635aab0faf4e86375db7a26ce985c04ac3a0c413476 used for local
analytic/corpus/capacity work. CI numbers are kept separate from local numbers.
CI settled-tone max error0.0388947cent also passes the unchanged controls.

Artifact10341213277 provides the validated distributable modules and loaded-test
logs; outer SHA2563983dacbd962af53a63bef1d17bbe67f4559bc883efbfb86d12a42dcd5eb6c4d.
Both ZIPs pass CRC. Local exact source, logs, failed GUI regression, CSV/JSON and
checksums are delivered; source audio/MOS and third-party SDK sources are excluded.

## Remaining adoption work

The requested Linux implementation path is connected and tested. Native Windows/
macOS editors, multiple voices, variable time-ratio automation, physical low-latency
DAW sessions and comparative listening are not implemented or qualified here.
Keep the preview flag, manual mode selection and draft promotion boundary until
those applicable adoption gates are deliberately evaluated.

Primary UI/host references: official ReaEffects Guide (ReaPitch),
https://www.reaper.fm/guides/ReaEffectsGuide.pdf ; CLAP gui/params/timer-support
headers at the pinned revision; VST3 IPlugView, IEditController and Linux::IRunLoop
interfaces at the pinned SDK revision. No third-party plugin artwork was copied.
