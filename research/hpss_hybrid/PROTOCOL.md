# Linked harmonic/percussive hybrid study — 2026-09-15

Base: research/phase-edge-integration at58f1c6b7. Product source, public ABI,
plugins, state, formant policy, automation and main are unchanged.

## Hypothesis

The earlier phase-only/projection studies did not jointly preserve natural
onsets and spectral shape. Separate harmonic/percussive components first, then
use long-window phase processing for H and short-window waveform overlap-add
for P. This changes both local magnitude support and phase treatment rather
than correcting output envelopes. Evaluate whether that reduces the inherited
heap's temporal regression without losing all its sustained-spectrum benefit.

Conceptual basis: Driedger/Mueller/Ewert, Improving Time-Scale Modification of
Music Signals Using Harmonic-Percussive Separation (SPL2014), author page
https://www.audiolabs-erlangen.de/resources/2014-SPL-HPTSM/ .
SELEBI (Akaishi/Holighaus/Yatabe2026, https://arxiv.org/abs/2602.16421) motivates
joint magnitude/phase localization but explicitly avoids separation. This is
an independent HPSS adaptation, NOT a SELEBI reproduction or a new-paper claim.
No external implementation is copied. Imperfect separation is an expected risk.

## Frozen construction and comparators

Shared-channel RMS-magnitude STFT, Hann2048 samples at48k, hop256, FFT4096.
At96k lengths double. Seventeen-frame and seventeen-bin centered medians,
complementary soft masks H^2/(H^2+P^2), same mask for every channel. Zero-energy
bins use1/2. Synthesize H, set P=input-H to retain exact complementary residual
up to floating roundoff. No mixture gain fitting, raw output normalization or
limiter. This centered separation is offline, not realtime-qualified.

Six predeclared modes:
- locked and heap: the inherited unmodified full-signal renderers;
- hps_locked_ola and hps_heap_ola: long H plus short P overlap-add;
- hps_locked_pv and hps_heap_pv: same separation but short phase-locked P.
H uses inherited window2048; P uses256 at48k (double at96k). The short-PV
branch is a control for waveform versus phase processing, not a selected winner.
Pitch is TSM(time*pitch) followed by the same Fourier resampling prescription;
individual branches share the requested time/pitch/rounding conventions.
The chosen processing mode is explicit; the decomposition does not select a
product profile. No new formant preservation or dynamic host processing.

## Evaluation fixed before outputs

Primary natural set: supplied20 test WAVs, ratios0.5/1.5/2.0, all six modes.
Five diagnostic pilot names are Ardour_2,Female_4,Male_6,Rock_4,Triangle_02;
the other15 are within-iteration confirmation only, not pristine holdout.
No parameter tuning is planned after either subset. Record all comparisons.

Synthetic: inherited partial bank/2ms gated attacks/band noise/correlated stereo,
plus low55Hz tone and harmonic+percussive mixture;48/96k,six pitch shifts plus
unity,all six modes. Mixture references explicitly preserve the gate width and
shift its carrier, not a claim of a unique ideal musical transformation.
Attack width is compared against its analytical oracle, NOT lower-always-better.
Report centroid error, width absolute error, energy outside expected gate,
partial leakage, raw peak and gain. Retain ordinary source-relative global PSD,
5ms RMS/onset and multi-window local STFT metrics unchanged for natural audio.

Post-design synthetic banks: eight seeds2609160..2609167,48/96k,six shifts,
locked/heap/hps_heap_ola. Same source files/arrays across modes. Verify identity,
finite/exact-length output, channel permutation/antiphase, independent OLA/mask
oracles, pure/invalid input and no allocation in the isolated C++ kernel.

No threshold/metric retuning after results. Source and executable hashes,
complete grid, independent test oracle, failures and source-cluster summaries
must be retained. Failed approaches remain research rather than being promoted.
The previous24ms attack-projection counterexample stays negative evidence; a
new method avoiding it does not establish all-condition superiority.

## Scope of performance and adoption

C++ mask/OLA kernels can be allocation-free; the Python separator/full renderer
allocates, uses centered medians and complete-signal arrays. Benchmark kernel
cost separately; no32/64-frame whole-DAW timing or fixed latency claim.
GCC/Clang20/23 and ASan/UBSan kernel tests plus Python/old-core regressions.
No native zplane run, MOS transfer, human listening or main merge in this study.
