# boiled egg

Linux-first research scaffold for a real-time pitch-shift + time-stretch SDK, with the long-term target of commercial-quality polyphonic processing.

> **Status:** C1/C2 opt-in SDK and one-voice host preview. WSOLA remains the default. The formant-preserving spectral SDK, continuous pitch and explicit ramps are available behind an experimental build option. CLAP/VST3 expose extended controls and a Linux X11 editor. This repository does **not** claim perceptual parity with zplane elastique.

Canonical names: repository slug **`boiled-egg`**, CMake target/package **`boiled_egg`**, C++ namespace **`boiled_egg`**, and public C ABI prefix **`boiledegg_`**.

## API architecture

- DSP core: **C++20**, continuously checked for **C++23** compatibility.
- Public ABI: **pure C** (`include/boiled_egg/boiled_egg.h`).
- C++ client API: **header-only RAII wrapper** (`include/boiled_egg/boiled_egg.hpp`).
- Public ABI uses an opaque handle plus versioned config (`struct_size`, `abi_version`).
- STL types, exceptions, templates and C++ implementation classes never cross the binary ABI.
- Two processing contracts are exposed: fixed-I/O **`boiledegg_process_realtime()`** for DAW insert/pitch-shift use, and variable-rate **push/pull** for clip/source time stretching.
- `boiledegg_get_runtime_info()` reports fixed realtime latency, tail, parameter quantum and capability flags for host adapters.
- Backend-independent `boiledegg_parameter_state` keeps project/preset parameters separate from ephemeral DSP history.

## Current DSP baseline

```text
planar float input
      |
linked multi-channel WSOLA
      |
40-tap table-driven windowed-sinc resampler
      |
fixed-capacity output FIFO
```

Pitch shift is decomposed into pitch-preserving time stretch plus resampling. The WSOLA timing decision is linked across channels. Its similarity search is coarse-to-fine to reduce periodic callback spikes. The resampler has 1024 fractional phases and 32 conservative cutoff tables for dynamic anti-alias filtering.

At 48 kHz the default input-side lookahead is 1152 frames (~24 ms). At 88.2/96 kHz the baseline uses a 1536-frame WSOLA window and 192-frame search radius (1728-frame / ~18 ms lookahead at 96 kHz) to keep short host blocks viable.

## Realtime and DAW contract

After `boiledegg_create()`, the streaming/realtime hot path, parameter-only flush and reset path are designed to perform no heap allocation, locking, I/O, logging, exception propagation or thread creation. `boiled_egg_noalloc_test`, ASan/UBSan and ThreadSanitizer cover these contracts.

`boiledegg_process_realtime()` always writes exactly the host block size and introduces a fixed, block-size-independent delay reported by `boiledegg_get_runtime_info()`. The current backend treats this as a pitch-shift insert mode and requires `time_ratio == 1`; actual timeline time stretching uses the variable-rate push/pull API. Startup delay is deterministic zero padding and the reported tail equals the delay for the current finite-memory backend. Exact per-channel in-place processing is supported.

Distinct `boiledegg_handle` instances are independent and may be processed concurrently on separate DAW workers. A single handle has one symbolic audio owner: processing calls must not overlap, but that owner may migrate between operating-system worker threads between calls. One control/UI thread may update parameters concurrently through lock-free atomic mailboxes. `boiledegg_reset()` is realtime-safe when serialized with processing and preserves requested parameters; `destroy` still requires lifecycle synchronization.

Fixed realtime processing accepts sorted, sample-offset parameter events. Zero-frame calls are supported as parameter-only host flushes, and an invalid batch is rejected before any value is published. The current WSOLA backend deliberately **does not** advertise `BOILEDEGG_CAP_SAMPLE_ACCURATE_AUTOMATION`; it reports a conservative `parameter_quantum_frames` instead. See [`docs/HOST_INTEGRATION.md`](docs/HOST_INTEGRATION.md).

## CLAP and VST3 adapters

The adapters are optional and keep third-party SDK headers out of the installed boiled egg SDK.

### CLAP

```bash
cmake -S . -B build-clap -G Ninja \
  -DCMAKE_BUILD_TYPE=Release \
  -DBOILED_EGG_BUILD_SHARED=OFF \
  -DBOILED_EGG_BUILD_CLAP=ON
cmake --build build-clap
ctest --test-dir build-clap -R boiled_egg_clap_smoke --output-on-failure
```

The build pins the official **CLAP 1.2.10** headers. CI loads the generated `.clap` through the CLAP ABI and exercises factory/create/activate, stereo processing, timestamped automation, audio-thread reset, `params.flush`, latency/tail and state save/load. The plugin statically embeds the boiled egg core and CI rejects an external `libboiled_egg` dependency.

### VST3

```bash
cmake -S . -B build-vst3 -G Ninja \
  -DCMAKE_BUILD_TYPE=Release \
  -DBOILED_EGG_BUILD_SHARED=OFF \
  -DBOILED_EGG_BUILD_VST3=ON \
  -DBOILED_EGG_BUILD_TESTS=OFF
cmake --build build-vst3 --target boiled_egg_vst3
```

The build pins the official **Steinberg VST3 SDK 3.8.0** commit used by CI. The SDK's `moduleinfotool` and official **VST3 validator** run during the plugin build. CI also checks that the VST3 bundle is self-contained and does not depend on an external `libboiled_egg`.

Both adapters expose pitch/fine, formant/fine, wet/dry, voice volume/pan, bypass, backend, quality and formant policy. The one-voice Linux X11/XEmbed editor is built when X11 is available and `BOILED_EGG_PLUGIN_UI=ON`. There is no multi-voice Add operation or Windows/macOS native editor in this checkpoint.

The original plugin IDs, pitch IDs and normalized ±24-semitone range are retained. Old pitch-only state loads with WSOLA semantics; new saves use version 2 and are not promised readable by old binaries. Back up existing plugins and use a project copy when testing the preview.

WSOLA remains selected by default. Spectral processing requires `-DBOILED_EGG_ENABLE_EXPERIMENTAL_SPECTRAL=ON` and explicit selection of `Spectral PV (preview)`. Its combined pitch range is ±12 semitones. Structural backend/quality/policy changes request host reactivation rather than rebuilding DSP in the audio callback. Wet/dry and bypass use the reported delay; at 48 kHz the Transient spectral configuration reports 2,112 samples (44 ms). Small callback support is not a claim of low-latency live monitoring.

See [`docs/HOST_PREVIEW_C2.md`](docs/HOST_PREVIEW_C2.md) for scope and [`docs/benchmarks/HOST_C2_FINAL_2026-09-18.md`](docs/benchmarks/HOST_C2_FINAL_2026-09-18.md) for actual-module compatibility, state and GUI checks. Automated host harnesses are not a manual qualification of every DAW.

## Build

```bash
cmake --preset release
cmake --build --preset release
ctest --preset release
```

Or without presets:

```bash
cmake -S . -B build -G Ninja -DCMAKE_BUILD_TYPE=Release
cmake --build build
ctest --test-dir build --output-on-failure
```

Compiler/sanitizer checkpoints:

```bash
cmake --preset clang && cmake --build --preset clang && ctest --preset clang
cmake --preset cxx23 && cmake --build --preset cxx23 && ctest --preset cxx23
cmake --preset asan && cmake --build --preset asan && ctest --preset asan
```

For a clean Debian workstation:

```bash
./scripts/bootstrap_debian.sh
source .venv/bin/activate
./scripts/run_all.sh
```

A `Dockerfile.dev` and `.devcontainer/` are also included.

Environment and install checks:

```bash
./scripts/doctor.sh
./scripts/test_install_consumer.sh build/release
```

The second command installs to a temporary prefix and builds both a pure-C consumer and a C++ wrapper consumer with `find_package(boiled_egg CONFIG REQUIRED)`.

For the complete GCC/Clang/C++20/C++23/static/sanitizer checkpoint, run `./scripts/run_matrix.sh`.

## CLI

```bash
./build/release/boiled_egg_cli input.wav output.wav --time 1.25 --pitch 5
```

Input WAV: PCM16 or float32. Output WAV: float32.

## Evaluation

```bash
python3 eval/generate_corpus.py
python3 eval/run_synthetic.py --cli build/release/boiled_egg_cli
python3 eval/run_bench.py --bench build/release/boiled_egg_bench
python3 eval/summarize.py
```

The committed evaluation harness covers exact duration, identity behavior, pitch accuracy, anti-alias regression, stereo relationship, host block-size determinism, randomized automation, hot-path allocation and callback deadline measurements.

For a local speech-like fixture and an optional Rubber Band comparison using FFmpeg:

```bash
python3 eval/generate_voice_corpus.py
python3 eval/run_external.py --corpus data/generated --limit 1
python3 eval/make_blind_manifest.py results/external/systems
```

`run_external.py` also accepts a real corpus under `data/external/`; it leaves source audio untracked and writes matched renders/manifests under `results/external/`.

### Current Linux checkpoint

The inherited DAW-foundation CI gate covers:

- GCC and Clang, C++20 and C++23.
- shared and static SDK consumer builds.
- ASan + UBSan.
- ThreadSanitizer across parallel plugin instances, concurrent control/audio parameter updates, serial DAW worker migration and realtime reset.
- fixed-I/O DAW tests across 44.1/48/96 kHz and 32/64/128/257-frame blocks at -12/0/+12 semitones.
- allocation-free realtime process, reset, parameter flush and state snapshot paths.
- CLAP 1.2.10 ABI load/process/state smoke test.
- Steinberg VST3 SDK 3.8.0 official validator.
- self-contained CLAP/VST3 packages with the core statically embedded.

Previous DSP baseline measurements in the development Linux VM include zero duration error for the fixed-ratio synthetic matrix, ~0.79 cent FFT pitch error for the +12-semitone 440 Hz fixture, ~54.4 dB +12-semitone anti-alias rejection in the committed synthetic test, and a worst repeated callback p99/deadline around 0.82–0.83x for the earlier 44.1/48/96 kHz × 32–512-frame matrix. These are machine-specific research checkpoints, not portable realtime guarantees.

## External evaluation material

Third-party audio is intentionally not committed. Put it under `data/external/` and run `python3 eval/inspect_corpus.py`.

The Roberts/Paliwal TSM subjective-quality dataset is supported as a local evaluation corpus. The test set supplied during development contains 20 reference files and 240 processed files, including Elastique, FuzzyTSM and NMFTSM outputs with MOS labels. Licensed/reference audio remains outside git.

For external algorithm baselines, `scripts/fetch_optional_baselines.sh` fetches Signalsmith Stretch and Rubber Band into a gitignored evaluation-only directory. Signalsmith Stretch is MIT; Rubber Band is GPL-2.0-or-later unless separately commercially licensed. Neither is linked into the product library.

## Resume development later

Start with roadmap **Issue #15**, integration **Issue #18**, `docs/SDK_PREVIEW.md` and `docs/HOST_PREVIEW_C2.md`. The earlier `docs/RESUME.md` retains historical research milestones, not an instruction to repeat them. Objective defect correction and API/host compatibility are separate from general natural-audio quality selection. Further algorithm research should address a demonstrated use-case deficiency; frozen perceptual predictors require independent validation before driving adoption.

Other useful documents:

- `docs/HOST_INTEGRATION.md` — DAW lifecycle, PDC/tail, automation, state and VST3/CLAP mapping.
- `docs/EVALUATION.md` — quality/performance matrix and listening-test plan.
- `docs/BASELINES.md` — evaluation-only competitor integration rules.
- `docs/LICENSING.md` — current licensing checkpoint.

## Repository licence

No licence has been selected for boiled egg itself yet. Until the owner chooses one, treat the source as all rights reserved. See `docs/LICENSING.md`.
