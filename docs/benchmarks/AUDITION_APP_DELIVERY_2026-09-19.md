# Standalone audition delivery — 2026-09-19 JST

Issue #31 / Draft PR #32, branch app/pyside6-audition-lab. Main remains
 d8e835d60e364f11dabbe9a23a531cdb29016b29. This is a separate experimental file
transport and PySide6 application, not a replacement for the existing plugin ABI.

## Resumption and newly completed work

Resumed at 3e12834e655982efe93ea45c237bed1d02c3fd30. Native transport, PySide6
worker/player, original SDK comparison, device-error handling, packaging and
26 Python tests already existed after previous interruptions. Their CI artifact
10553929453 was downloaded, CRC/SHA256 verified and 244 source files matched.
These implementations are inherited work, not claimed newly invented here.

New small commits add native_batch.py, four numerical/file tests, worker ownership
and cancellation, GUI comparison/progress controls, three real GUI/worker tests,
a quick-start guide and packaging that includes it. Code/packaging checkpoint:
946f73aac3e2d0aa0f5cc9ed6cbf1238e373d27e.
Its tree is d3740561e8849f90fad3e871fb1b90de1dfa5b5e.
This result record is documentation only. No C++ DSP source changed in this pass.

## What the application actually supports

Native playback: six explicitly named new transport modes: PV Classic, Locked,
Transient, and time-domain WSOLA, Transient, Efficient. Speed 0..4; pitch is
-24..24 semitones, with 0 meaning unchanged pitch, not a zero frequency ratio.
Speed0 holds the source anchor while C++ synthesis and output-time controls
continue. Pause is separate. Changing pitch during hold does not advance source
position. PV uses local spectrum/frequency estimates and continuing phase;
time-domain modes synthesize aligned local grains. There is no common finished-WAV
loop substituted behind the six algorithm names.

PV formant policies Off/Harmonic/Monophonic and independent +/-12st formant shift
remain distinct. Time-domain policies unsupported by the implementation are
rejected, not silently converted to Off. Transport lives in sdk/transport with
pure C interface and C++ RAII wrapper, copies prepared source at create and has
one rendering owner. GUI communicates through a worker with two-block PCM queue.
Existing finite push/pull contracts, main SDK and CLAP/VST3 files are untouched.

The separate comparison tab executes all five CURRENT MAIN SDK modes through
the actual SDK CLI: WSOLA General/Transient/Efficient and PV General/Transient.
Their original ranges are retained: WSOLA speed.25..4, +/-24st, formants Off;
PV speed.5..2, +/-12st. Old SDK speed0 is rejected, not relabeled native freeze.
New transport modes are NOT bit-identical implementations of those SDK modes.

Historical multi-resolution, phase-gradient, HPSS, variable-window and other
research branches are NOT all ported to native freeze. Pre-rendered research files
can be opened for comparison but the application does not claim to execute those
algorithms. External native zplane/R3/Signalsmith engines are not bundled/run.
Thus the request for every historical algorithm is not fully completed here.

## New same-anchor comparison operation

The native tab now offers a six-mode comparison from current source position,
speed, pitch, policy, formant setting and finite output duration (.1..120s).
The worker snapshots the currently loaded PCM once, not its possibly changed
pathname, then independently constructs each native mode at the same anchor.
Source/output clocks, length, rate, channel count, finite float32 samples and
constant native owned storage are checked. Hashes identify the PCM, library,
comparison code and each output. No gain normalization, limiter, lag fitting or
reuse of one algorithm's rendered output. It starts fresh synthesis histories,
not an exact recording of the just-heard device queue.

Results move to the comparison tab for selection/playback and raw WAV+JSON save.
Unsupported, failed and cancelled rows remain. Partial WAV/receipt files created
by a cancelled mode are removed; preexisting files are not overwritten. A separate
threading.Event allows cancelling work while its owner is busy; no competing
thread calls that native handle. Finite single-WAV export is also cancellable.
The actual GUI regression deletes the original source pathname AFTER loading,
then successfully compares the loaded PCM at the prescribed held anchor.

## Fresh local verification

| Test | Result |
|---|---:|
| Python GUI/worker/SDK/native/comparison tests |33/33|
| Native GCC C++20/23 and Clang C++20/23 |2/2 CTests each|
| Native Clang ASan+UBSan, leak detection enabled |2/2|
| Native executable output |96 trajectory/freeze assertions; zero processing allocations|
| Existing opted-in SDK full regression |26/26|
| Relocated packaged application |33/33 and successful CLI smoke|
| Missing native library negative smoke |exit1 as required|

Of the33 Python tests, seven are newly added in this pass. Actual SDK output
comparison is exercised by the existing five-mode tests; native modes are checked
against fresh direct C++ calls with a different block partition. No changed
thresholds, silent skips or human ratings. After packaging, original build-sdk
and build-transport directories were temporarily hidden; all33 package tests and
startup still pass. ldd with the application's library search resolves the SDK
from the package, not the old build directory. Both build directories were restored.

The combined first SDK build/test tool call hit its execution-time limit during
test22. A fresh complete CTest invocation then passed26/26 without code changes.
Likewise an initial combined assessment call left a partial range directory; the
complete range run uses a separate directory. Partial logs are retained and are
not reported as completed tests.

## Repeated objective audio diagnostics

Unchanged held-tone assessor:6 modes x48/96k x223/997Hz x-7/0/+7st =72 outputs.
All72 pass pitch<5cents, 95% envelope ripple<1dB, stereo relative error<1e-5,
fixed source clock and native owned-storage invariants.

- Worst absolute pitch error:0.4117877599 cents.
- Worst envelope ripple:0.09929932654 dB.
- Worst stereo residual:6.0810180003e-8.
- Six longer holds:528000 output frames each (11s at48k), fixed source position
  24000, constant reported native owned storage. Frequency continues to sound.

Unchanged range assessor:6 modes x48/96k x speeds0/.001/.25/1/4 x pitches-24/0/+24
=180 outputs. All180 pass; worst pitch error2.1226051380 cents, maximum source
position error0. Existing independent tests additionally cover1e-6speed, exact
linear-ramp area, hold/pitch-ramp/resume, silence/DC/EOF, short files, seek,
block partition and invalid events preserving subsequent output history.

These252 diagnostic outputs are regenerated synthetic steady-tone evidence, not
new natural-music quality trials or a score for transients/formants/all material.
Range scoring is after0.6s and hold scoring after0.35s; it does not prove perfect
transition quality. No portable realtime or WCET qualification was added.
Measured native library SHA256:
c770573bcedee4834b80ed42c5ca63c1f6ee5f4e34eaee9fe8089cc6ca41eef7.

## CI and source identity

At checkpoint946f73aa all three workflows succeed:
- audition-app35392595076:33 tests, GUI smoke,72+180 diagnostics, relocated33 tests,
  missing-library negative and package manifest.
- native-transport35392594965:compiler20/23 matrix and ASan/UBSan.
- existing product ci35392594966.

Downloaded artifact10566535650 SHA256:
06931d604aa30486d75e0f0792eccea451894fad56eb94131faaab3674b69ec1.
ZIP CRC and all248 tracked source SHA256s verify. Every one of those248 files
matches the local source used to build/test/package. The downloaded CI logs show
33/33 original and relocated tests;72/72 and180/180 diagnostic passes are retained
separately from local results. Repetition is not counted as independent evidence.

## Deliverable and remaining boundaries

The Linux x86_64 folder contains Python sources, compiled native transport,
compiled actual SDK+CLI, start-audition.sh, pinned requirements, README and
QUICKSTART_JA. Python3.11+ and the listed runtime/system dependencies must be
installed separately; this is not a self-contained Windows/macOS executable.
PySide6==6.9.3, NumPy==2.3.5 and SoundFile==0.13.1 were exercised here.
Qt wheels, fonts, external SDKs and user recordings are not redistributed.

Screenshot is captured from the real packaged GUI after a six-mode .5s freeze
comparison at source2.4s and +7st. The GUI explicitly reports no audio output
device in this environment. Real DAC/speaker playback was NOT verified. Device
failure, partial Qt writes and unavailable devices have automated tests, not a
substitute claim of hardware success. Audio export remains usable without a device.

Main remains unchanged; Draft PR32 is not production promotion. Remaining work
includes physically verified playback/platform distribution, broader perceptual
and transient validation, and native ports of the historical research modes.
The design does not promise arbitrary live-input freeze plus all-input retention
at fixed latency. Pitch0 means no pitch displacement, not a bypass guarantee.
