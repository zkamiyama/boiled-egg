# C++ streaming phase-vocoder research backend

This directory contains an **independent research prototype**, not the shipping boiled egg backend.

Architecture:

- C++20 DSP implementation;
- pure C opaque-handle ABI (`include/boiled_egg_pv_rt.h`);
- header-only C++ RAII wrapper (`include/boiled_egg_pv_rt.hpp`);
- linked multichannel analysis;
- classic, identity-phase-locked, and transient-reset low-level PV modes;
- fixed-capacity input/OLA/output rings;
- no heap allocation in normal `push`/`pull`/parameter calls after construction;
- exact-duration flush contract;
- generated C consumer, deterministic-block, no-allocation, compiler-matrix, and sanitizer tests.

## Validated manual quality profiles

The research API exposes a separate **quality profile** concept so a user-facing `Transient` choice is not confused with the older low-level frame-phase-reset mode.

- **General**: 2048 FFT / 256 hop / phase locked.
- **Transient**: 1024 FFT / 128 hop / phase locked.

Use `boiledegg_research_pv_rt_configure_quality_profile()` in C, or `pv_rt_quality_profile` / `pv_rt_profile_config()` in the C++ wrapper. Applying a quality profile only changes FFT size, analysis hop and low-level PV mode; formant strategy and pitch/time parameters remain independent.

The Transient profile was promoted inside the research backend only after the 20-reference derived-Elastique comparison, the 55–440 Hz sustained-tone safety gate, and same-VM realtime comparison. See `ELASTIQUE_PITCH_RESULTS.md` and `FORMANT_RESULTS.md`.

Build:

```bash
cmake -S research/cpp_pv_rt -B build/cpp_pv_rt -G Ninja -DCMAKE_BUILD_TYPE=Release
cmake --build build/cpp_pv_rt --parallel 2
ctest --test-dir build/cpp_pv_rt --output-on-failure
```

Render:

```bash
build/cpp_pv_rt/boiled_egg_pv_rt_cli input.wav output.wav \
  --time 1.25 --mode locked --fft 1024 --hop 128
```

The dataset tuner lives at `research/tune_cpp_pv_rt.py`. Its proxy MOS is only an engineering triage signal. Promotion into the product core requires blind listening against the supplied references plus all realtime gates.
