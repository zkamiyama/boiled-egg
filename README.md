# boiled egg

Linux-first research scaffold for a real-time pitch-shift + time-stretch SDK, with the long-term target of commercial-quality polyphonic processing.

> **Status:** v0.1 research baseline. The API, realtime constraints, tests and evaluation harness are intentionally more mature than the current WSOLA-based DSP. This repository does **not** claim perceptual parity with zplane elastique yet.

Canonical names: repository slug **`boiled-egg`**, CMake target/package **`boiled_egg`**, C++ namespace **`boiled_egg`**, and public C ABI prefix **`boiledegg_`**.

## API architecture

- DSP core: **C++20**, continuously checked for **C++23** compatibility.
- Public ABI: **pure C** (`include/boiled_egg/boiled_egg.h`).
- C++ client API: **header-only RAII wrapper** (`include/boiled_egg/boiled_egg.hpp`).
- Public ABI uses an opaque handle plus versioned config (`struct_size`, `abi_version`).
- STL types, exceptions, templates and C++ implementation classes never cross the binary ABI.
- Processing API is streaming **push/pull**, because input/output block counts differ during time-scale modification.

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

## Realtime contract

After `boiledegg_create()`, the normal `push()` / `pull()` / parameter-setter path is designed to perform no heap allocation, locking, I/O, logging, exception propagation or thread creation. `boiled_egg_noalloc_test` checks C++ heap allocation after warm-up. ASan/UBSan and randomized dynamic automation are part of the test matrix.

### Threading model for DAWs

Distinct `boiledegg_handle` instances are independent and may be processed concurrently on separate DAW worker/audio threads. On one instance, the streaming state machine (`push`/`pull`/`flush`) remains single-owner and lock-free; do not call it concurrently from multiple audio threads. Control/UI threads may update time and pitch parameters concurrently with streaming through lock-free atomic mailboxes, with changes observed at the next streaming API boundary. `reset` and `destroy` remain lifecycle operations and must be serialized with streaming. This deliberately optimizes for DAW track-level parallelism without putting mutexes on the realtime path. ThreadSanitizer plus dedicated multi-instance/control-thread tests enforce this contract.

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

Measured in this development container on Debian 13, GCC 14.2 / Clang 17, AMD EPYC 9V74 virtual CPU allocation:

- 6/6 tests pass with GCC C++20.
- 6/6 tests pass with GCC C++23.
- 6/6 tests pass with Clang C++20.
- 6/6 tests pass under Clang ASan + UBSan.
- Synthetic duration error: **0 frames** for the current fixed-ratio matrix.
- 440 Hz pitch test: **220.0 Hz** at -12 st and **880.4 Hz** at +12 st (~0.79 cent error for the latter FFT measurement).
- +12 st anti-alias regression: 14 kHz stop-band fixture is **~54.4 dB** below the 10 kHz pass-band fixture.
- Stereo correlation error in the linked-channel fixture: about **-4.6e-7**.
- Callback microbenchmark: the committed run peaks at **0.83x p99/deadline** over the 44.1/48/96 kHz × 32/64/128/256/512-frame × -12/0/+12 st matrix; the latest five repeated runs peaked between **0.82x and 0.83x**. At <=48 kHz the committed-run worst is about **0.38x**. These figures are machine-specific and are not a portable realtime guarantee.

See `results/SUMMARY.md`, `results/realtime_bench.csv`, and `results/ENVIRONMENT.txt` after running `scripts/run_all.sh`.

## External evaluation material

Third-party audio is intentionally not committed. Put it under `data/external/` and run `python3 eval/inspect_corpus.py`.

Recommended evaluation sources include EBU SQAM and the Roberts/Paliwal TSM subjective-quality dataset. EBU SQAM's current download page explicitly describes the lossless assessment material and limits commercial use to use as an R&D tool. Keep licensed zplane material/output local unless its licence explicitly permits redistribution.

For external algorithm baselines, `scripts/fetch_optional_baselines.sh` fetches Signalsmith Stretch and Rubber Band into a gitignored evaluation-only directory. Signalsmith Stretch is MIT; Rubber Band is GPL-2.0-or-later unless separately commercially licensed. Neither is linked into the product library.

## Resume development later

Start with **`docs/RESUME.md`**. It records the current architecture, commands, constraints and the next algorithm milestones. The next major quality step is an STFT phase-vocoder backend with phase locking and transient-aware processing, followed by HPSS and formant preservation.

Other useful documents:

- `docs/EVALUATION.md` — quality/performance matrix and listening-test plan.
- `docs/BASELINES.md` — evaluation-only competitor integration rules.
- `docs/LICENSING.md` — current licensing checkpoint.

## Repository licence

No licence has been selected for boiled egg itself yet. Until the owner chooses one, treat the source as all rights reserved. See `docs/LICENSING.md`.
