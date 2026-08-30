# C++ streaming phase-vocoder research backend

This directory contains an **independent research prototype**, not the shipping boiled egg backend.

Architecture:

- C++20 DSP implementation;
- pure C opaque-handle ABI (`include/boiled_egg_pv_rt.h`);
- header-only C++ RAII wrapper (`include/boiled_egg_pv_rt.hpp`);
- linked multichannel analysis;
- classic, identity-phase-locked, and transient-reset modes;
- pitch shift by internal time stretch plus a 40-tap table-driven sinc resampler;
- explicit `off`, `harmonic`, and `monophonic` formant modes;
- linked-channel cepstral spectral-envelope correction for harmonic/polyphonic material;
- F0/cepstral harmonic-lobe gating for monophonic positive formant correction;
- magnitude-squared weighted log-gain centering plus residual power compensation, preventing the formant EQ from becoming an unintended broadband gain stage;
- fixed-capacity input/OLA/PV/output rings;
- no heap allocation in normal `push`/`pull`/parameter calls after construction;
- exact-duration flush contract;
- generated C consumer, deterministic-block, no-allocation, compiler-matrix, sanitizer, pitch/formant and callback-deadline tests.

Build:

```bash
cmake -S research/cpp_pv_rt -B build/cpp_pv_rt -G Ninja -DCMAKE_BUILD_TYPE=Release
cmake --build build/cpp_pv_rt --parallel 2
ctest --test-dir build/cpp_pv_rt --output-on-failure
```

Render a time stretch:

```bash
build/cpp_pv_rt/boiled_egg_pv_rt_cli input.wav output.wav \
  --time 1.25 --mode transient --fft 2048 --hop 256
```

Render a pitch shift with formant preservation:

```bash
build/cpp_pv_rt/boiled_egg_pv_rt_cli input.wav output.wav \
  --time 1 --pitch-semitones 7 --mode locked --formant harmonic
```

Use `--formant monophonic` for voice or a single pitched source. The formant implementation remains research-only until blind listening and the full realtime/product gates justify promotion.

The Roberts/Paliwal 20-reference test-set checkpoint and exact commands/metrics are recorded in `FORMANT_RESULTS.md`. Dataset audio is intentionally not committed.
