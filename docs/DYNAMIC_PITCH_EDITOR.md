# Continuous pitch and the native pitch editor (preview)

This opt-in change extends the spectral preview through the **existing** product
C/C++ handles and CLAP/VST3 adapters. WSOLA remains the default; `main` is not
replaced by a research backend. This is one shifter, not a complete ReaPitch clone.
Fuzzy, multi-resolution and phase-guard experiments are not included.

## Input-clock pitch mapping

Add `BOILEDEGG_BACKEND_CONTINUOUS_PITCH` together with
`BOILEDEGG_BACKEND_ALLOW_EXPERIMENTAL` when constructing a spectral handle.
The new preallocated history stores the monotonically increasing map
`V(u) = integral(T * p(u) du)` and the effective pitch/formant values. Analysis
frame centers, synthesis positions and output resampling use that **same** map.
A new target ramps the pitch ratio linearly over 10 ms of input samples from its
current effective value. It is not a linear-in-semitones ramp. Events arriving
during a ramp start the next ramp from that current value. Controls do not reset
phase or jump the resampling read pointer. Caller block size does not set timing.

Time ratio T is still fixed at construction. The streaming API allows constant
T in [0.5,2] and pitch p in [0.5,2], subject to T*p<=2. The realtime interface
requires T=1. Unsupported dynamic time changes fail explicitly. Without the new
flag, the prior static-pitch preview remains available with its old contract.

Supported spectral rates are exactly 44100,48000,88200,96000 Hz; mono/stereo;
SDK call blocks1..1024. General and Transient quality are independent of Off,
Harmonic/polyphonic and Monophonic formant policy. No automatic source classifier
selects a mode. Formant targets remain frame-latched with 10-ms smoothing, not an
instantaneous samplewise warp. The pitch response also has STFT window spreading;
a precise input event timestamp is not zero-latency or instantaneous audio response.

## Fixed latency and tail

The continuous path reserves a construction-time delay for the whole supported
pitch range, using the .5 minimum slope, rather than changing delay as pitch moves.
The positive cumulative-map increments bound availability between any two source
positions; the same conservative lookahead, scheduling and resampler-support
allowances used by the static .5-pitch bound are retained. The claim is conditional
on no algorithmic scheduler/FIFO overrun, not a bound on OS execution time.

| Quality | 48 kHz | 96 kHz |
|---|---:|---:|
| Transient | 2112 samples / 44.000 ms | 4160 / 43.333 ms |
| General | 3648 samples / 76.000 ms | 7232 / 75.333 ms |

Query `boiledegg_get_runtime_info()` for actual latency and tail. The delay is
independent of automated pitch/formants and caller block partition, but not of
rate or quality. This is not a claim of lower latency than the old compact static
unity-pitch configuration. Initial output is a zero prefix; feed silence to drain
the realtime tail. Offline `flush()` is not used from host processing callbacks.
The dry and bypass paths in the plugins have the same delay as the wet path.

```c
#include <boiled_egg/backend.h>
boiledegg_config c = boiledegg_default_config(48000, 2);
c.max_block_size = 64;
boiledegg_backend_config b = boiledegg_default_backend_config();
b.backend_id = BOILEDEGG_BACKEND_PHASE_VOCODER;
b.quality_mode = BOILEDEGG_QUALITY_TRANSIENT;
b.formant_policy = BOILEDEGG_FORMANT_POLICY_HARMONIC;
b.io_contract = BOILEDEGG_IO_REALTIME;
b.flags = BOILEDEGG_BACKEND_ALLOW_EXPERIMENTAL |
          BOILEDEGG_BACKEND_CONTINUOUS_PITCH;
boiledegg_result status;
boiledegg_handle *h = boiledegg_create_backend(&c, &b, &status);
/* Check h/status; construction/destruction are outside the audio callback.
   Submit existing PITCH_RATIO/PITCH_SEMITONES and new FORMANT events to
   boiledegg_process_realtime. Offsets refer to this input block. */
```

## Existing plugin controls and state

The existing plugin identifiers and original pitch parameter IDs/normalization
are retained. New controls: pitch fine (cents), independent formant semitones and
cents, Wet, Dry, voice volume, stereo balance pan, bypass, backend, quality and
formant policy. Coarse and fine pitch sum; their combined value must be in range.
PV permits +/-12 semitones; WSOLA preserves +/-24. Invalid combinations do not
silently fall back to a different algorithm. Volume/pan apply to the wet voice;
Wet/Dry are independent gains, not a fixed-power crossfade. Gain/bypass changes
have a 5-ms linear ramp. There is only one voice and no Add shifter operation.

Backend/quality/formant-policy changes require host restart/deactivate-reactivate
and are not sample-offset automation parameters. The editor shows pending changes
until the host reactivates; it never allocates a new DSP from `process()`. Pitch,
fine pitch, formant, mix, volume, pan and bypass are automatable. At most256 sorted
events are accepted; same-offset coupled values are validated together. Malformed
batches fail before processing. UI publication uses bounded atomic snapshots;
the audio owner retains the last valid compatible snapshot rather than spinning
on a concurrently published coupled state.

Version2 state is an explicit64-byte little-endian record. Old16-byte CLAP and
12-byte VST3 version1 pitch-only state migrates to WSOLA with the same pitch and
default new controls. Unsupported/broken state fails rather than being interpreted
as another version. Test with copies of projects: the preview uses existing plugin
IDs and can replace the installed reference plugin. Restore the old binary to
return to the stable plugin; do not install both copies as different products.

## ReaPitch-inspired native UI

The editor uses ReaPitch's useful grouping of pitch/fine adjustment, separate
formants, independent Wet/Dry and per-voice volume/pan as a reference. Graphics
and code are original. It does not imply algorithm/feature parity or a copied
ReaPitch skin. See the official ReaEffects guide, ReaPitch section:
https://www.reaper.fm/guides/ReaEffectsGuide.pdf

Linux X11/XEmbed is implemented for both plugin formats, float32 stereo. Mouse
sliders, numeric editing (Ctrl+A, Enter/Escape), relative wheel changes, Tab and
arrow/Home keys, resizing, lifecycle and host gestures are tested. CLAP uses a
host timer and begin/value/end events; VST3 uses the host runloop and
beginEdit/performEdit/endEdit. Hiding the editor or losing genuine keyboard focus
closes an active host gesture. A temporary X11 focus grab does not cancel editing.
X11 window handling and drawing are not performed by the audio callback.

No native Windows/macOS editor, Wayland-only integration, multiple voices,
perceptual-quality certification or manual commercial-DAW project validation is
claimed. Other supported host environments can use their generic parameter view;
that is not equivalent to a tested native editor. Unsupported GUI APIs are refused.

## Build and validation

Build Release for the VST3 package layout and use a static core for distributable
self-contained plugin modules (system X11/C++ runtime dependencies still apply):

```sh
cmake -S . -B build-pitch -G Ninja -DCMAKE_BUILD_TYPE=Release \
  -DBOILED_EGG_BUILD_SHARED=OFF \
  -DBOILED_EGG_ENABLE_EXPERIMENTAL_SPECTRAL=ON \
  -DBOILED_EGG_BUILD_CLAP=ON -DBOILED_EGG_BUILD_VST3=ON
cmake --build build-pitch -j2
ctest --test-dir build-pitch --output-on-failure
```

CLAP SDK1.2.10 and VST3 SDK9fad9770f2ae8542ab1a548a68c1ad1ac690abe0 are
pinned by the host configuration/workflow. X11 development packages and xvfb-run
are needed to build/exercise the native editor on headless Linux. No font files
are embedded or redistributed; the system provides X11 fonts.

`quality/dynamic_pitch/evaluate.py` checks independent analytic settled pitches
and reports, separately, transition diagnostics. `replay_corpus.py` verifies
block32/257 equality with dynamic controls on actual input files; that is
same-kernel integration evidence, not native-vendor comparison. The benchmark
uses the previously declared80% statewise best-of-three policy and retains raw
misses/maxima and genuine full-run successes. It is not a WCET bound or a claimed
noise-free continuous run. See the dated validation record for measured outcomes.
