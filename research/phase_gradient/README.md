# Independent phase-gradient integration study

Issue #1 includes phase-gradient integration as a separate quality candidate.
This directory implements that experiment independently, based on the equations
and Algorithm 1 in Z. Prusa and N. Holighaus, *Phase Vocoder Done Right*
(EUSIPCO 2017; arXiv posting 2022): https://arxiv.org/abs/2202.07382 .
No competing plugin or copyleft reference implementation is copied into the SDK.
This experiment is not selected by a product backend flag.

## Components

`heap_integrator.hpp` is an independently implemented C++20 kernel. A preallocated
max heap prioritizes high-magnitude known phase values in the preceding/current
frames. Integration uses a temporal trapezoidal step or a frequency-neighbor
trapezoidal step. The heap storage is bounded by twice the number of bins.
The standalone tests compare 513,000 affine-field phases, bound heap removals,
intercept processing allocation and cover silence/invalid dimensions. Python
also compares heap traversal with an independent exhaustive-priority oracle.

`bridge.cpp` exposes the kernel to the offline Python experiment. No C++/Python
binding library is needed. `experiment.py` supplies STFT analysis, centered phase
gradients and overlap-add. All three study modes use the same input/window/hop,
normalization and Fourier resampler:

- `locked`: conventional instantaneous-frequency propagation with peak locking.
- `trapezoid`: temporal trapezoidal integration, without frequency-neighbor steps.
- `heap`: magnitude-prioritized time/frequency integration.

Centered temporal gradients require one future analysis frame. The renderer is
OFFLINE and allocates its arrays. The C++ kernel's no-allocation property is NOT
claimed for the entire Python pipeline. Rate-scaled Hann windows, full-file
reference-channel choice, a unity bypass and retaining input phase in very weak
bins are explicit adaptation choices. Formant preservation, dynamic automation,
streaming latency, host integration and a real-time callback budget are not
implemented for this experimental renderer.

## Build and reproduce

```sh
c++ -O2 -std=c++20 research/phase_gradient/test_kernel.cpp -o phase-test
./phase-test
c++ -O3 -std=c++20 -shared -fPIC research/phase_gradient/bridge.cpp -o phase_heap.so
BOILED_EGG_PHASE_HEAP_LIBRARY="$PWD/phase_heap.so" \
  python -m unittest discover -s research/phase_gradient -p 'test_*.py' -v
OPENBLAS_NUM_THREADS=1 python research/phase_gradient/study.py \
  --kernel "$PWD/phase_heap.so" --output phase-results --workers 2
# Add --refs /absolute/path/to/the/20/reference/wavs for the natural-source study.
```

Analytical pitch tests use an eight-partial bank and four short gated attacks,
48/96 kHz, and six shifts (-12,-7,-3,+3,+7,+12 semitones). These are only two
synthetic families, not a comprehensive music-quality dataset.

Natural TSM uses ratios 0.5,1.5,2.0. Metrics are explicitly source-relative:
5-ms power-envelope shape after the prescribed time map, positive RMS-flux
correlation, and normalized whole-signal Welch PSD shape. No fitted time alignment
or DTW is used. A whole-signal PSD can improve while local timing gets worse.
These metrics are not interchangeable with earlier cepstral-envelope, STFT
spectral-distance or onset descriptors in other research scripts. They are not
errors against an available ideal time-stretched recording.

## Result interpretation

In the September 15 replay, heap integration improves the synthetic partial
balance and attack widths and the natural global PSD descriptor. It worsens
natural RMS-envelope shape relative to the matched locked control, and its mean
onset correlation is slightly lower. Temporal trapezoidal integration alone is
particularly poor on the attack fixture. Therefore this is a retained research
candidate, not an adopted production improvement or a verdict on every faithful
implementation of the original paper.

See `docs/benchmarks/AUTOMATION_RAMPS_PHASE_STUDY_2026-09-15.md` for exact counts,
values, input/executable provenance, counterexamples and limits. User source
recordings, native zplane output and human ratings are not distributed here.
