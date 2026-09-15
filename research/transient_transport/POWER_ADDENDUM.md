# Post-pilot addendum: unit-power grain normalization

The first six-mode study on the five declared pilot sources completed90 outputs.
No remaining15-source or new-mixture results had been generated at this point.
Mean RMS/onset/globalPSD: locked1.651325/.472192/1.399696;
heap1.846691/.455643/.765434; split_heap_ola2.113712/.462747/4.744270;
split_heap_anchor2.272182/.433688/3.025342. Thus simple component splitting and
short OLA did not solve the temporal/spectral tradeoff. Retain these failures.

One specific additional hypothesis is now fixed before confirmation. Ordinary
OLA averages overlapping grain samples. For decorrelated noise these weights
reduce expected power, unlike coherent overlap of the same source samples.
Test a deterministic, duplicate-aware weight normalization instead of inferring
an amplitude correction from output/reference audio.

For a destination sample, group overlapping grains with the same source-index
offset. Let w_j be each synthesis weight and G a group. Use denominator
sqrt(sum_G (sum_{j in G} w_j)^2). Identical source samples add coherently within
a group; distinct indices are treated as uncorrelated. This is exact for white
noise covariance and reduces to ordinary coherent normalization for unity or
unit-slope anchored sections. Real residuals need not be white: tonal leakage,
correlation and amplified tails remain possible failure modes. Do not present
expected-white-noise power preservation as a bound or universal quality result.

The implementation uses no measured input/output RMS, gain fitting, limiter,
or spectral-envelope target. It is a synthesis-weight change, not post-output
normalization. Four overlapping grains yield at most three prior overlap checks.

Add fixed modes split_heap_power and split_heap_anchor_power to the original six.
Keep all eight in final tables. All previous settings, detector thresholds,
source cohorts, ratios and metrics are unchanged. Full intended counts are480
natural,448 analytical and384 new-mixture outputs=1312. The initial90-output
pilot is exploratory, not added to that primary total. No further parameter or
method selection after confirmation is permitted in this iteration.
