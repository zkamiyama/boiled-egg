# Resume boiled egg development

## Current checkpoint

- Core language: C++20; C++23 is a CI compatibility target.
- Public ABI: pure C (`boiledegg_*`), opaque handle + versioned config.
- C++ client: header-only RAII wrapper.
- Baseline DSP: linked multi-channel WSOLA -> 40-tap table-driven windowed-sinc resampler -> fixed-capacity FIFO.
- Realtime contract: no heap allocation/locks/I/O/logging/thread creation in the normal processing path after construction.
- Tests: C ABI, core duration, host-block determinism, hot-path allocation, randomized automation, anti-alias regression.
- Evaluation: deterministic synthetic corpus, objective diagnostics, callback deadline benchmark, external baseline hooks.

## Resume commands

```bash
./scripts/doctor.sh
cmake --preset release
cmake --build --preset release
ctest --preset release
./scripts/run_all.sh
```

For the compiler/static/sanitizer matrix:

```bash
./scripts/run_matrix.sh
```

## Next DSP milestones

1. Add a backend abstraction so WSOLA remains available as a low-compute/reference backend.
2. Implement an STFT phase-vocoder backend.
3. First PV variant: instantaneous-frequency propagation + identity/adaptive phase locking.
4. Second PV research variant: full time/frequency phase-gradient estimation and real-time integration inspired by Prusa & Holighaus, *Phase Vocoder Done Right* (2022).
5. Add transient/percussion tests before adding transient-specific processing.
6. Evaluate explicit transient phase reset and harmonic/percussive hybrid processing.
7. Research nonstationary-Gabor/adaptive-window processing inspired by SELEBI (Akaishi, Holighaus, Yatabe, 2026).
8. Add formant/spectral-envelope preservation.
9. Add explicit automation-time mapping and improved latency reporting.
10. SIMD/profile only after quality variants are compared under the same test harness.

## Quality gates for every backend

- No NaN/Inf under randomized time/pitch automation.
- Deterministic output independent of host callback size for fixed automation.
- No C++ heap allocation after warm-up in the audio hot path.
- p99 callback work must remain below the configured deadline on the reference benchmark machine.
- Anti-alias regression remains >=40 dB for the current +12 st fixture.
- Stereo/mono-compatibility tests must not regress.
- Listening tests include harmonic, transient/percussive, speech, full-mix, noise/texture and hard-stereo material.

## External material

Third-party source audio and licensed competitor output stay out of git. Put them below `data/external/` locally. Useful comparison systems are Signalsmith Stretch, Rubber Band R3/current, and a licensed zplane elastique render.

## Research references to revisit

- Prusa, Holighaus (2022), *Phase Vocoder Done Right*: https://arxiv.org/abs/2202.07382
- Akaishi, Holighaus, Yatabe (2026), *SELEBI: Percussion-aware Time Stretching via Selective Magnitude Spectrogram Compression by Nonstationary Gabor Transform*: https://arxiv.org/abs/2602.16421
- Driedger, Müller, Ewert (2014), harmonic-percussive TSM: https://www.audiolabs-erlangen.de/resources/2014-SPL-HPTSM/
- Driedger, Müller (2016), TSM review: https://www.mdpi.com/2076-3417/6/2/57
- Rubber Band technical notes: https://www.breakfastquay.com/rubberband/technical.html
- Signalsmith Stretch design notes: https://signalsmith-audio.co.uk/writing/2023/stretch-design/
