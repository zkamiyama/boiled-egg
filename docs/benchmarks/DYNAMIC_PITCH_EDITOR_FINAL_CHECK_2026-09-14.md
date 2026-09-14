# Dynamic pitch/editor final resume verification — 2026-09-14

## Scope and source identity

The requested Linux path is implemented: continuous input-clock pitch mapping,
fixed host delay, existing CLAP/VST3 events and state migration, and the original
ReaPitch-inspired X11 editor. The work remains opt-in and experimental. PR9 is
stacked on draft PR8; stable main is not changed or merged by this verification.
One voice, float32 stereo plugins, native X11 GUI only. Dynamic time-ratio control,
multiple shifters, Windows/macOS native GUI, manual commercial-DAW qualification
and native-zplane comparison are not claimed.

This resume started at 146bd9080b8a851e17ee50907d89141e1b6e2bea. It independently
downloaded the successful CI source, checked all170 tracked hashes and the tree
0acb8acb8d87f916af2e29755cd60ac521f27a28, then rebuilt and exercised real modules.
The inherited implementation is not presented as newly invented in this resume.

New code commit 0a0c7c86dffbb29f2071c453beeb206e5b0423d1 fixes metadata-only GUI
refresh. Its tree30fc56958b39269f46967b422db28e30add00ee3 matched the local tree.
A concurrent report-only commit f8fa2abe5cb197cd5cce575fb367c5aa2891ac7d was
preserved. The final CI source artifact10341464952 from run34830260175 has171
verified tracked files and tree724f879af755adb7aab6cc59323eac281fce6bdb; all known
files match this measured local source. Its synthetic PR merge commit is
339d2a981ce92cd43974b7a6d4a1ec1d1c01120b. This final-check record is documentation
only. See DYNAMIC_PITCH_EDITOR.md for the complete public contract and the earlier
validation record for implementation history; do not pool successive runs.

## Additional real UI bug fixed

A host reactivation can change latency and clear the pending-restart indicator
without changing any parameter values. Likewise, a rejected edit can change the
error message while preserving parameters. Previously the editor only dirtied its
surface on changed values/X events, so those labels could remain stale indefinitely.

The editor now checks latency, pending status and error text on its GUI timer and
repaints when those change. No audio-thread code, processing arithmetic, ABI,
parameter/state format, latency calculation or preset defaults changed.

A new regression reads actual X11 pixels, rather than a mocked draw count. With
unchanged values it changes the reported delay, sets and clears pending status,
and sets and clears an error. The unpatched test exits1 with
`metadata-only latency update must repaint`; the fixed test passes. Existing
hide/focus/relative-wheel/keyboard/resized-coordinate checks still pass, with eight
balanced host gestures. Both negative and passing logs are retained.

## Rebuilt validation in this resume

| Validation | Result |
|---|---|
| GCC14.2 C++20 and23, spectral ON |17/17 CTests each|
| Clang17 C++20 and23, spectral ON |17/17 each|
| Matched Clang C/C++, ASan+UBSan with leak detection |17/17|
| Default spectral OFF |12/12|
| Actual static-core CLAP/VST3 and native editor suite |25/25|
| Normal Steinberg validator |47 passed,0 failed|
| Python analytic/corpus/capacity calibration |12/12|
| Independently downloaded final CI CLAP module |32 dynamic/state/in-place cases plus GUI passed|
| Independently downloaded final CI VST3 module |32 dynamic/state/in-place cases plus GUI passed|

Loaded processing allocation interception passes for both formats. Tests cover
legacy state, new partial-stream state I/O, malformed event rejection, compensated
mix paths, parameter gestures, numeric editing, resizing and timer lifetime.
The actual plugins are not merely compiled. Their dependency tables contain no
libboiled_egg.so: the SDK is embedded, but X11/C++/standard system libraries remain
required. The same-source local CLAP module was used to capture the shipped UI
screenshot; no font files are bundled.

An initial local sanitizer configuration mixed Clang C++ with GCC C and linked
incompatible ASan runtimes for two C-consumer executables. That failed log is
retained. A fresh matched-Clang C/C++ build using BOILED_EGG_SANITIZE=ON passes all
17 tests with leak detection and no suppression. This is a corrected local test
configuration, not a waived SDK test or a DSP workaround.

## Fresh objective and corpus replay

Re-executed36 paired analytic trajectories /72 renders and252 settled plateaus:
max absolute settled pitch error0.0388841619 cents; all predeclared5-cent and1e-5
stereo conditions pass. Output at block32 and257 is identical. The independent
25000-sample long-double input-map reference and40 dynamic delay/duration cases
remain part of CTest. This is not an instantaneous transition-accuracy claim;
trajectory and amplitude-ripple diagnostics are retained separately.

Re-executed the actual supplied20 test references xGeneral/Transient xthree
formant policies:120/120 paired dynamic streams are sample-identical at block32
and257,240 generated outputs. Prefix, exact compensated length, finite samples,
rates and input/library hashes are checked without fitted alignment or output
normalization. Both paths use the same kernel; this establishes integration,
not independent perceptual/native-vendor superiority. User source/rendered audio
and MOS are not redistributed.

Loaded library SHA256:
106f524edd536c29032d4635aab0faf4e86375db7a26ce985c04ac3a0c413476

Corpus comparisons SHA256:
dcbdc38521053bdc73881e08741c62ef5d67c2a761600cb72ccf5f51da613bcf

## Fresh practical timing, not a hard-RT guarantee

After builds/tests/renders completed, three CPU0-affined wall-only repetitions
cover48/96k, stereo, General/Transient, three policies and32/64-frame callbacks:
24 settings,86400 steady calls,67986 cold calls retained. Four pitch/formant events
per callback. Per-state output fingerprints match. The unchanged predeclared
criterion is maximum over states of best-of-three <=80% period, not p99 or WCET.

All24 settings pass; worst state-best ratio0.390039. Individual steady period
misses21/86400, maximum raw ratio7.4543295, and61/72 real steady runs below period
are all retained. Best samples from different runs are not called one successful
continuous run. No counter/empty-clock subtraction is performed.

The final CI runner separately passes24/24 settings: worst state-best0.310569,
zero steady misses and72/72 full steady runs below period. CI observations do not
replace the local21 misses. This measures the public SDK, not a complete DAW
processing graph, and does not establish the physical cause of rare tails.

## Final hosted status and distribution

All five workflows at f8fa2abe complete successfully:

- dynamic-pitch-editor34830260175: actual dynamic SDK, analytic/capacity tests,
  static-core CLAP/VST3 modules, real GUI and validator.
- dynamic-plugin-sanitizers34830260152: instrumented common plugin processor,
  coupled state and independent audio owners (address/undefined/thread).
- spectral-backend-preview34830260136: ON/OFF, installation, static and exports.
- existing product ci34830260133: compiler/ABI/sanitizer/host regression.
- rt-measurement-audit34830260130: unchanged performance/measurement checks.

Some preceding 0a0c7c86 runs were canceled; they are not counted as successful.
The source/GUI fix is included in the subsequent successful f8fa2abe runs.

Final core artifact10341464952 ZIP SHA256:
6709058625b3d93b5af8c09dc9fc031cf70636e4c869a6982c9f60d0e178fe22
Final plugin artifact10342141130 ZIP SHA256:
98b3e1cdfac4e99b8637df64a8ce2201ca6834671983c406966cc5126e2c2523

Both archives pass CRC and tracked-file checks. Distributed plugin binaries come
from this successful final Ubuntu24.04 CI build and were reloaded locally through
both actual host ABIs, as recorded above. The bundle includes third-party license
texts, not external SDK sources or font files. IDs match the existing plugins:
back up existing binaries and test copies of projects before replacing them.

No further spectral adoption is inferred from successful implementation tests.
ReaPitch was a control-grouping reference (official ReaEffects guide, section9),
not copied artwork or an assertion of multiple-voice feature parity.
