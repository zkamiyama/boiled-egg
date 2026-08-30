# C++ streaming phase-vocoder research backend

This directory contains an **independent research prototype**, not the shipping boiled egg backend.

Architecture:

- C++20 DSP implementation;
- pure C opaque-handle ABI (`include/boiled_egg_pv_rt.h`);
- header-only C++ RAII wrapper (`include/boiled_egg_pv_rt.hpp`);
- linked multichannel analysis;
- classic, identity-phase-locked, and transient-reset modes;
- fixed-capacity input/OLA/output rings;
- no heap allocation in normal `push`/`pull`/parameter calls after construction;
- exact-duration flush contract;
- generated C consumer, deterministic-block, no-allocation, compiler-matrix, and sanitizer tests.

Build:

```bash
cmake -S research/cpp_pv_rt -B build/cpp_pv_rt -G Ninja -DCMAKE_BUILD_TYPE=Release
cmake --build build/cpp_pv_rt --parallel 2
ctest --test-dir build/cpp_pv_rt --output-on-failure
```

Render:

```bash
build/cpp_pv_rt/boiled_egg_pv_rt_cli input.wav output.wav \
  --time 1.25 --mode transient --fft 2048 --hop 256
```

The dataset tuner lives at `research/tune_cpp_pv_rt.py`. Its proxy MOS is only an engineering triage signal. Promotion into the product core requires blind listening against the supplied references plus all realtime gates.
