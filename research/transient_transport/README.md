# Complementary transient transport — isolated research

This directory investigates constant time stretching by separating linked harmonic
and percussive components, processing the harmonic branch with long-window phase
vocoder synthesis, and transporting short percussive waveform grains. It is not
an enabled product backend, a realtime renderer or a new formant method. Product
DSP, public SDK ABI, explicit pitch/time ramps, plugins, state and main are unchanged.

## Implemented alternatives

`transport.py` exposes eight fixed modes: `locked`, `heap`, `split_heap_long`,
`split_locked_ola`, `split_heap_ola`, `split_heap_anchor`, `split_heap_power` and
`split_heap_anchor_power`. The first two call the inherited renderer unchanged.
The long/long split is a decomposition-only control. Anchored variants use a
piecewise-monotone output-to-input map with unit local slope around detected
percussive events. Power variants use a duplicate-source-index covariance model
for synthesis weights, not measured output/reference gain matching.

All methods are offline constant TSM, ratio0.5..2, pitch1, at44.1/48/96k, with
linked channels. The full Python renderer allocates and needs whole-signal data.
Only the C++ anchor interpolation helper and inherited heap kernel are tested
allocation-free. The helper's binary search has bounded O(log K) lookup; it does
not establish a full callback deadline. There is no new auto-selected product mode.

The methods improve some isolated attack fixtures but worsen the real-corpus
spectral/envelope descriptors. The anchor detector also merges staggered stereo
events because of its40ms minimum spacing. Correct known landmarks repair that
specific fixture in a post-hoc diagnostic; they are not available to the actual
algorithm. The implementation is retained as negative/diagnostic research, not
promoted. See the dated results under docs/research.

## Checkout-only build and CI

```sh
cmake -S research/transient_transport -B build-transport -G Ninja \
  -DCMAKE_BUILD_TYPE=Release -DCMAKE_CXX_STANDARD=20
cmake --build build-transport -j2
ctest --test-dir build-transport --output-on-failure
```

This builds the independent C++ map/heap checks and `libtransient_map.so` /
`libphase_heap.so`. The dedicated workflow runs these kernels under GCC/Clang,
C++20/23 and ASan/UBSan/leak detection. It does not run the full Python study.

## Publication limitation — explicit

The GitHub connector safety-blocked one create-tree request containing
`fixtures.py`, `metrics.py` and `study.py`. That request was not retried through
another API or tool. These three evaluation files are therefore **not committed**.
They are retained in the downloadable research delivery as clearly labeled local
analysis files, with their measured hashes and all results.

The committed `test_transport.py` imports those local fixture/metric files. It is
**not a self-contained checkout-only Python test suite**. Its16 successful tests
were executed locally with the supplied analysis overlay, not by hosted CI.
`transport.py` and `native.py` themselves are committed and use the existing
`research/phase_gradient` renderer. No missing-import failure is relabeled as a
skip or a successful full-suite CI run. The bundle also includes local-only
summary/diagnosis scripts and the failed supplementary control-replay attempt.

To reproduce the full Python experiment, use the delivery's documented local
analysis overlay and the two kernel libraries above. No user recording or MOS
file is redistributed. Natural studies require the exact provided20-reference
folder, not a substituted corpus. Protocol and POWER_ADDENDUM record the actual
pilot sequence; do not treat the historically reused corpus as a pristine holdout.

## Literature and scope

The long-PV/short-OLA split is independently adapted from Driedger, Mueller and
Ewert's harmonic-percussive TSM work. The anchor and synthesis-weight variants
are project ablations. SELEBI motivates joint magnitude/phase time localization
but its nonstationary-Gabor construction is not reproduced by this code.

- https://www.audiolabs-erlangen.de/resources/2014-SPL-HPTSM/
- https://arxiv.org/html/2602.16421v1
