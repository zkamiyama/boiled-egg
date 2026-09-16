# Opt-in spectral SDK preview

This is the SDK-only C1 integration from roadmap #18. It makes the already
validated preview available without checking out the research PR chain. It does
not change the existing CLAP/VST3 adapters or enable new processing by default.
The existing plugins still use WSOLA; the ReaPitch-inspired editor and adapter
parameter/state migration remain a separate C2 integration task.

## Build and identify availability

```sh
cmake -S . -B build-preview -G Ninja -DCMAKE_BUILD_TYPE=Release \
  -DBOILED_EGG_ENABLE_EXPERIMENTAL_SPECTRAL=ON
cmake --build build-preview -j2
ctest --test-dir build-preview --output-on-failure
build-preview/boiled_egg_backend_cli --list-backends
```

The build option defaults to OFF. A known but uncompiled backend is reported as
UNAVAILABLE; an enabled PV is EXPERIMENTAL, never silently used instead of WSOLA.
Every instance must also set BOILEDEGG_BACKEND_ALLOW_EXPERIMENTAL. Ordinary
boiledegg_create/create_ex calls keep their legacy WSOLA behavior, including the
legacy FORMANT_PRESERVE unsupported result. New formant policies are selected in
boiledegg_backend_config, not by reinterpreting that legacy enum.

## Fixed-ratio file example

Use an output path that does not already exist:

```sh
build-preview/boiled_egg_backend_cli input.wav output.wav \
  --backend pv --allow-experimental --quality transient \
  --formant harmonic --time 1 --pitch-semitones -7 --block 32
```

The CLI is a fixed-ratio streaming example. It is not a new graphical editor or
an interface for changing ramps during file processing. Output is FLOAT WAV,
with validated metadata and the requested rounded duration.

## Public C/C++ interface

Include boiled_egg/backend.h for configuration/formant controls and
boiled_egg/automation.h for explicit ramps. The existing header-only engine
wrapper accepts the extended configuration and still uses the opaque C handle.

A C setup for a fixed-I/O, dynamically pitched voice is:

```c
#include <boiled_egg/backend.h>
#include <boiled_egg/automation.h>

boiledegg_config config = boiledegg_default_config(48000, 2);
config.max_block_size = 64;
boiledegg_backend_config backend = boiledegg_default_backend_config();
backend.backend_id = BOILEDEGG_BACKEND_PHASE_VOCODER;
backend.flags = BOILEDEGG_BACKEND_ALLOW_EXPERIMENTAL
              | BOILEDEGG_BACKEND_CONTINUOUS_PITCH;
backend.quality_mode = BOILEDEGG_QUALITY_TRANSIENT;
backend.formant_policy = BOILEDEGG_FORMANT_POLICY_HARMONIC;
backend.io_contract = BOILEDEGG_IO_REALTIME;
boiledegg_result status = BOILEDEGG_OK;
boiledegg_handle *handle = boiledegg_create_backend(&config, &backend, &status);
/* Check handle/status; process with the ordinary realtime API or the explicit
   ramp API. Destroy the handle only after processing/lifecycle synchronization. */
```

Old point events retain their 10-ms behavior in continuous-pitch handles. Explicit
ramp events add step, linear-ratio and log-ratio transitions with a duration in
accepted input samples. A log pitch-ratio ramp is linear in semitones. Interrupted
ramps restart from the current effective value. In variable-time streaming,
CONTINUOUS_TIME selects audio-owner ramp control; do not mix it with independent
UI pitch/time setters. Handle accepted-prefix backpressure by draining output
and rebasing only the remaining input/events. Pull alone does not advance ramps.
Read automation.h for endpoint, ordering and validation contracts.

## Deliberate supported scope

| Dimension | Preview |
|---|---|
| Sample rates | 44.1, 48, 88.2, 96 kHz |
| Channels | Mono or stereo |
| Caller block | 1 through 1024 samples |
| Quality | General or Transient, explicit selection |
| Formant policy | Off, Harmonic, Monophonic, independent of quality |
| Pitch/time ratios | Each 0.5 through 2.0, with coupled bounds enforced by validation |
| Fixed-I/O | Time ratio is 1; query the actual fixed latency/tail |
| Variable time | Streaming push/pull with explicit input-clock trajectories |

Do not infer that every pitch/time combination inside the individual ranges is
valid; boiledegg_validate_backend_config and ramp-batch validation are authoritative.
Latency does not change when a supported pitch trajectory changes, but it depends
on rate, quality and the chosen contract. Query runtime_info; a small callback is
not a claim of negligible monitoring latency. This preview is not a blanket live
monitoring, host/platform, subjective-quality or native-zplane parity guarantee.

## Integration evidence and provenance

quality/sdk_preview/audit.py checks all runtime/header files against the qualified
PR28 donor and protects the main adapter/evaluation/research trees. It runs the
SAME C11 and C++ executables, compiled against previous headers and the previous
library, with original/OFF/ON libraries. It verifies loader resolution, complete
output grids, state/runtime metadata, additive exports and preview replay. The
negative tests reject incomplete grids, changed hashes, export leaks and scope
changes. ABI additions do not require old callers to recompile.

Private src/experimental/pv contains historical research-derived support needed
by the qualified kernel. Its old SOURCE_SHA256SUMS is a provenance snapshot, not
a manifest for the now-modified complete source tree. No private headers or
research symbols are installed/exported. Whole-checkout CI manifests identify the
actual integrated version. Do not reapply the old stereo patches to this SDK.

Wider natural-audio quality selection and frozen-model validation remain roadmap
B work. No new listener ratings, perceptual-model predictions or native vendor
outputs are produced by this integration.
