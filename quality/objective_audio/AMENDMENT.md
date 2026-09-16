# Objective regression amendment: reference-index dependence

The first `static_stereo.patch` repairs the proportional signal but fails48/60
of the PREVIOUS unchanged channel-exchange tests. This is negative evidence, not
an acceptable tradeoff concealed by a scalar metric. It remains in git as a
rejected pilot. Do not use it for the final candidate.

The existing dominant-channel predictor chooses index0 on equal current energy,
including silence. Previous phase histories can differ across channels, making
that arbitrary choice observable after L/R exchange. The corrected static path
uses the current-power-weighted circular mean of interframe phase increments:
arg(sum_c |X_c|^2 exp(j*(phase_c - previous_phase_c))). This removes the channel-
index choice without averaging angles across the branch cut. Apply one bounded
rotation to each original complex channel coefficient. Mono, WSOLA and the
existing dynamic timeline are still unchanged. Two arrays are allocated at
construction, never inside processing/reset. No new lookahead or output fitting.

The full old diagnostic rerun of this second candidate passes240/240 metadata,
120/120 proportional/silent controls and60/60 exchange pairs. This is a regression
repair under the existing1e-5 threshold, not an audibility or MOS claim.
The second candidate is now frozen for the remaining repeated numerical, seeded,
mono-compatibility, toolchain and sanitizer checks. Those seeded cases were already
seen in the rejected pilot and are regression coverage, NOT a new blind holdout.
No changes to their targets, metrics or thresholds. All rejected records remain.

Use `pooled_static_stereo.patch` for the final candidate. Both patches apply to
the unmodified base and must NOT be stacked. A patch being present in this branch
does not enable it automatically: the dedicated workflow explicitly applies the
final patch before building/testing. Product/main and default ABI remain untouched.
