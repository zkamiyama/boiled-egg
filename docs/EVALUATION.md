# Evaluation plan

## Gates already automated

1. Pure-C ABI compiles from a C translation unit.
2. C++ wrapper compiles and owns the opaque handle with RAII.
3. Fixed-ratio output duration is sample-exact in the synthetic matrix.
4. Identity path is near-bit-transparent at time=1, pitch=0.
5. +/-12 semitone sine tests verify pitch direction and cents error.
6. High-frequency +12 semitone test checks anti-alias attenuation.
7. Stereo test checks that linked processing retains the input L/R relationship.
8. Dynamic random time/pitch automation runs without NaN/Inf.
9. Hot-path allocation test checks that push/pull/setters allocate no C++ heap memory after warm-up.
10. ASan/UBSan test the library and stress path.
11. Callback-style benchmark records mean/p50/p95/p99/max work versus the nominal audio deadline.
12. Export check ensures the shared-library symbol surface stays C-only.
13. Installed-package smoke test verifies a clean `find_package` consumer in both C and C++.
14. Optional external-corpus runner renders matched boiled egg / Rubber Band files for blinded listening.

## External material

Do not commit third-party audio unless redistribution is clearly permitted. Put local corpora under `data/external/`.

Recommended sources:

- EBU SQAM: https://qc.ebu.io/testmaterials/523/ — lossless audio intended for sound-quality assessment. The EBU page states that downloading accepts a restriction against commercial use other than as an R&D tool.
- Roberts & Paliwal TSM dataset: see https://arxiv.org/abs/2006.00848 and the dataset link in that paper. It contains speech, solo harmonic/percussive instruments, effects and music with subjective TSM labels.
- A private licensed production corpus covering vocals, full mixes, bass, drums, noisy speech, stereo ambience and hard-panned material.

## Listening tests

Objective metrics are diagnostics, not the final quality criterion. For each milestone, blind-test matched outputs from boiled egg, Signalsmith, Rubber Band (current local/reference build) and licensed elastique on the same source/ratio matrix. Keep randomized trial manifests and listener scores under `results/listening/`, not the source audio if its licence forbids redistribution.

Suggested matrix:

- time: 0.5, 0.75, 0.9, 1.1, 1.5, 2.0
- pitch: -12, -7, -3, +3, +7, +12 semitones
- combinations: 0.75/+7, 1.25/-5, 1.5/+4
- automation: ramps and abrupt steps every 0.25-2 s
- sample rates: 44.1, 48, 96 kHz
- callback blocks: 32, 64, 128, 256, 512
