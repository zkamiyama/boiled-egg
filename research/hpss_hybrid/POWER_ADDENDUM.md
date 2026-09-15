# Post-primary OLA diagnosis and fixed supplementary hypothesis

The frozen six-mode study has finished:504 synthetic,360 actual-source and288
new-bank outputs. All are retained. HPSS+OLA is worse on the60 natural cells:
heap/HPS-heap-OLA global PSD0.771756/5.136394dB, RMS1.880296/2.574722dB,
onset0.434090/0.415517. Short-PV control is less bad but not jointly superior.
No parameters of this primary experiment will be changed or its results erased.

A separate fixed-seed white-noise control isolates an OLA issue: for TSM factors
.5/1.5/2, conventional sum-window normalization attenuates by approximately
10.27/7.35/7.25dB. At unity the same samples overlap coherently and gain is0dB.
For distinct independent input samples the expected output variance is instead
sigma^2 * sum(group_weight^2), with weights grouped by identical source index.
This observation does NOT prove every natural failure comes from OLA power.
Band-limited/tonal residuals have cross-sample correlation and imperfect HPSS can
still introduce destructive branch interference. Source-relative spectral
normalization cannot restore the relative H/P balance lost during synthesis.

## Supplementary algorithm, fixed before its corpus outputs

Use sqrt(sum(group_weight^2)) as the percussive OLA denominator. A group contains
contributions referring to the same input sample at that output sample. Equal
source addresses are coherent; distinct addresses are treated as independent.
At unity all addresses agree, yielding the conventional sum of windows, without
an arbitrary near-unity bypass. The denominator depends only on source/destination
positions and windows, NOT measured output level or a fitted target envelope.
It is a white-noise model, not a universal power-preservation guarantee.

Two fixed hop rules: original dense win/(8*max(1,alpha)); sparse
min(win/4,win/(2*alpha)), floor and minimum1. Four variants: original dense
amplitude, sparse amplitude, dense grouped power, sparse grouped power.
H remains the same inherited heap, separator/mask/windows stay unchanged.
No limiter or ad-hoc peak clipping. All four modes will be reported.

Evaluate the same60 natural TSM cells and synthetic bank/attack/noise/stereo/
low55/mixture48/96k,seven pitch ratios. This is a post-primary exploratory
follow-up on historically reused sources, not an untouched holdout. Record
expected-white variance calibration, near-unity behavior, oracle width/centroid,
nonstationary gain/peaks, new C++ no-allocation tests and all losses.

The primary study.py GitHub write was blocked by the connector. It remains an
explicit local-only delivered harness, not retried through a different action.
Independent implementation and unit tests remain committed. This supplementary
hypothesis is not a replacement path for that blocked primary-file publication.
