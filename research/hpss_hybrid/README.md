# Linked harmonic/percussive hybrid — isolated research

This is an independently implemented HPSS experiment, not a production backend.
No product DSP/ABI/plugin/state/automation/formant policy is changed. The explicit
modes and primary/supplementary hypotheses are recorded in PROTOCOL.md and
POWER_ADDENDUM.md. Preliminary natural results reject the naive hybrid; the
variance correction fixes a white-noise level model but does not remove the
periodic correlation caused by reusing waveform grains. Keep both findings.

## Build and independent tests

```sh
cmake -S research/hpss_hybrid -B build-hpss -G Ninja -DCMAKE_BUILD_TYPE=Release
cmake --build build-hpss -j2
ctest --test-dir build-hpss --output-on-failure
export BOILED_EGG_HPSS_LIBRARY="$PWD/build-hpss/libhpss_kernels.so"
export BOILED_EGG_PHASE_HEAP_LIBRARY="$PWD/build-hpss/libphase_heap.so"
export BOILED_EGG_HPSS_POWER_LIBRARY="$PWD/build-hpss/libhpss_power.so"
OPENBLAS_NUM_THREADS=1 python -W error::ResourceWarning -m unittest discover \
  -s research/hpss_hybrid -p 'test_*.py' -v
```

Three CTests verify the masks/waveform kernel, inherited heap, and grouped-power
kernel. Twenty-one Python tests check reconstruction, linked channels, oracle
metrics, invalid input and independent coefficient references. The periodic-noise
correlation test deliberately confirms a known FAILURE mode of the model; its
passing status is not a sound-quality acceptance certificate.

Kernels use caller-owned buffers and allocate no memory during processing.
The Python separator and full renderer allocate full-signal arrays and use
centered median windows. They are offline and do not establish fixed-delay,
formant-preserving or real-time host operation. The supplementary grouped-power
scratch also scales with output length in this renderer.

For a single offline experiment, import render.py and call render with explicit
phase_kernel and hps_kernel paths. The six declared modes are available in
render.MODES. Supplemental dense/sparse and amplitude/power variants live in
power_render.py. Use the same inputs and fixed modes; do not select per-file
winners from the measured output.

## Measurements and publication limitation

The complete primary study.py upload was blocked by the connector. It was not
retried via another GitHub action. That actual evaluated harness, the supplementary
runner, journals, all CSV/JSON and source hashes are retained in the downloadable
research bundle as explicitly LOCAL-ONLY analysis. They are not represented as
committed or CI-executed. The independent kernels, renderer and numerical/metric
tests are committed and runnable with the commands above.

Raw source-relative spectral descriptors are not native-zplane results or MOS.
Attack width is compared to an analytical gated-carrier oracle, never treated as
universally better merely because it is narrower. Keep gain, raw peaks, temporal
errors, noise coloration and failed controls beside spectrum metrics.

The kernel-only benchmark can be built separately with
`c++ -O3 -std=c++20 research/hpss_hybrid/bench_kernel.cpp -o build-hpss/kernel-bench`.
It includes no separator/FFT/full-host timing and makes no32/64-frame capacity claim.
