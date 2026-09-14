# Explicit backends and the formant preview

> This document describes the original static-pitch preview. For the additional
> explicit continuous-pitch flag and existing-plugin editor/state integration,
> see [DYNAMIC_PITCH_EDITOR.md](DYNAMIC_PITCH_EDITOR.md). Without that flag,
> the static-control contract below is retained.

## Status and compatibility

The stable/default backend remains WSOLA. Its existing General, Transient and
Efficient profiles, C ABI structures, enum values and plugin state are unchanged.
Legacy `FORMANT_PRESERVE` is still unsupported; it is not silently mapped to a
new algorithm. No signal classifier chooses a backend for the caller.

The new `boiled_egg/backend.h` adds versioned configuration, allocation-free
capability queries and an explicit constructor using the ordinary opaque handle.
The backend, processing quality, formant policy and I/O contract are independent.
A backend inventory is a build-level list, not a real-time or perceptual quality
certificate. Always validate the entire configuration: endpoints of a range do
not imply every sample rate or combination in between is supported.

The single-resolution phase-vocoder is a **disabled-by-default preview**, not a
promoted product profile. Both the build flag and the per-instance experimental
consent flag are necessary. It imports the private research kernel as present
in spectral branch checkpoint `67e997a497bff9b35732c4ae8ad2d43ca4e8e9e4`.
It selects ordinary phase locking, not Fuzzy, Multi-resolution, or an experimental
guard patch. Private headers and research symbols are not part of the installed
public ABI. The same private kernel is compiled separately for routing tests;
that reference is not an independent audio-quality implementation.

## Explicit preview contract

| Item | Supported in this preview |
|---|---|
| Rates | Exactly 44,100 / 48,000 / 88,200 / 96,000 Hz |
| Channels | Mono or stereo |
| Caller block limit | 1 to 1,024 frames |
| Processing quality | General (long window), Transient (short window) |
| Formant policy | Off, Harmonic, Monophonic; independent of quality |
| Initial pitch and time ratios | Each 0.5 to 2.0; time times pitch must be at most 2.0 |
| Streaming contract | Explicit push/pull, exact final duration, bounded backpressure |
| Fixed-I/O contract | Time = 1; declared constant delay; planar in-place supported |
| Automation | Formant target only, 0.5 to 2.0; Off permits only 1.0 |
| Pitch/time after construction | Frozen; incompatible setters, events and state return UNSUPPORTED_MODE |

Reset keeps the selected backend, policies, frozen pitch/time and requested
formant target. It does not unlock another processing mode. Recreate the handle
outside the audio callback to change those immutable settings. This is a visible
limitation, not a silently ignored pitch knob. The inventory intentionally does
not advertise dynamic pitch/time for the preview.

The realtime entry accepts at most 256 sorted events per call. The last duplicate
offset wins; malformed or unsupported events are rejected before processing.
A target is submitted before its input-sample offset, then latched by the first
eligible STFT frame and smoothed with a 10-ms time constant. This is not an
instantaneous sample-resolution spectral-envelope warp. Each handle has one
processing owner; different handles can run concurrently. Control setters and
state access use the existing atomic mailbox contract. State snapshots are
per-field, not atomic multi-parameter transactions with concurrent UI changes.

Fixed-I/O delay depends on the construction-time pitch and quality but does not
change with formant automation. Query `boiledegg_get_runtime_info()` rather than
using `boiledegg_input_latency_frames()` (a different streaming lookahead hint).
The preview clears the hard-realtime capability bit. It provides bounded,
allocation-free processing, not a universal DAW deadline guarantee.

## Build and CLI

```sh
cmake -S . -B build-preview -G Ninja -DCMAKE_BUILD_TYPE=Release \
  -DBOILED_EGG_ENABLE_EXPERIMENTAL_SPECTRAL=ON
cmake --build build-preview -j 2
ctest --test-dir build-preview --output-on-failure
build-preview/boiled_egg_backend_cli --list-backends
build-preview/boiled_egg_backend_cli input.wav output.wav \
  --backend pv --allow-experimental --quality transient \
  --time 1 --pitch-semitones -7 \
  --formant harmonic --formant-semitones 3 --block 32
scripts/test_backend_install.sh build-preview ON
```

Without the CMake flag, PV queries return `UNAVAILABLE`, and attempts to select
it fail rather than falling back to WSOLA. The new CLI refuses existing output
paths (including symlink aliases) and conflicting ratio/semitone options. Source
WAVs and rendered datasets must remain local; do not commit them.

## C and C++ usage

```c
#include <boiled_egg/backend.h>
boiledegg_config c = boiledegg_default_config(48000, 2);
c.max_block_size = 64;
boiledegg_backend_config b = boiledegg_default_backend_config();
b.backend_id = BOILEDEGG_BACKEND_PHASE_VOCODER;
b.quality_mode = BOILEDEGG_QUALITY_TRANSIENT;
b.formant_policy = BOILEDEGG_FORMANT_POLICY_HARMONIC;
b.io_contract = BOILEDEGG_IO_REALTIME;
b.flags = BOILEDEGG_BACKEND_ALLOW_EXPERIMENTAL;
boiledegg_result status = boiledegg_validate_backend_config(&c, &b);
/* Check status before constructing; creation/destruction stay off the callback. */
```

`boiledegg_create_backend()` returns the normal handle. The header-only C++
wrapper adds `engine(config, backend)`, `set_formant_ratio()`,
`set_formant_semitones()`, formant event factories and extension-state access.
In callbacks use the nothrow processing entry or the pure-C API. Installed C11
and C++ tests under `tests/backend_install` are complete compilable examples.

Use the new `boiledegg_backend_parameter_state` for time/pitch/formant values. Its
backend and policy must match the handle; restore cannot silently change them.
Legacy parameter state remains time/pitch only and does not clear formants.
This in-memory extension record is not a new CLAP/VST3 serialized state format.
The existing product adapters still select WSOLA: wiring the new controls into
those UIs/state formats is a separate step, as is dynamic-pitch timeline work.

## Reproducible integration checks

`quality/backend_preview/replay_corpus.py` compares public SDK renders with a
direct private API executable using the same kernel, quality and formant policy.
The public caller uses 32-frame input and the reference uses 256; output files,
samples, duration, sample rates and channels must agree. It publishes only a
complete grid and records source, executable, script and result hashes. This is
routing and compatibility evidence, not a new MOS or native-zplane comparison.
The CLI-only tests use no external dataset. Shared/static installation, spectral
ON/OFF, compiler, address/undefined/thread sanitizer tests run separately in CI.

Remaining before general-purpose product use: dynamic pitch with a validated
fixed-delay mapping, product adapter event/state integration, declared-scope
performance measurement, comparative listening and platform qualification.
