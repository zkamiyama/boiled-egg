# Linked transient detection and shared-phase recombination

Base: 81505c8ace89809d4583b3da7a2bbe2d22330ca1. Research only; no product/main,
ABI, plugin, formant or automation changes. Offline constant TSM, pitch=1.

## Hypotheses fixed before new measurements

D: the previous 40-ms global refractory period deletes independent stereo events.
Compare legacy global40, global6 (spacing-only control), and per-channel6 with
1-ms bounded-span fusion. Keep the inherited 1-ms power envelope, 5% relative
prominence and 4x local-median rejection. Fusion uses normalized prominence,
strongest candidate, earliest time on ties. Nearby events in different channels
must not suppress each other merely because another channel is louder. This is
an engineering ablation, not a claimed new onset-detection paper. Closely spaced
or very weak events may still fail; report one-to-one precision/recall and errors.

R: independently evolving phases after a complementary split can introduce a
recombination penalty. Derive one full-band phase rotation and apply it to both
components. With no replacement, linear STFT/OLA must reconstruct the original
full-band processed output to numerical precision. Then compare replacement of
all percussive audio with replacement of only input-localized transient residuals.
The latter is Y_full - A_R(q) + transport(q), q=g_input*p, where A_R is the fixed
full-input-derived phase rotation plus synthesis operator. No oracle locations,
output-fitted gain, limiter, envelope matching or post-hoc winner selection.

Seven fixed modes: locked, heap, independent_legacy, independent_linked,
shared_long, shared_linked, localized_shared. shared_long is an algebraic control,
not a novel quality algorithm. All use the same existing base long-window kernel.
Localized input gate: full inside half the protected radius, cosine taper to zero
at the protected radius; radius=min(12ms,20% adjacent/end gap*min(1,T)).

## Evaluation and publication

First reproduce the old 27-ms staggered stereo failure. New confirmation uses
previously unused seeded signals with event spacings 4/7/12/19/27/38/54/83 ms,
unequal channel levels, dual mono, polarity inversion, sustained components and
noise. Detector truth is for scoring only. Same-channel close events and weak
broadband background are negative controls. Report oracle timing/energy/width
errors, not lower-is-always-better raw attack widths.

Use the actual supplied20 mono44.1k references at T=.5/1.5/2. The five development
sources remain Ardour_2,Female_4,Male_6,Rock_4,Triangle_02; all other sources are
within-iteration confirmation, not historically untouched material. Freeze code
before confirmation; amendments, failed proposals and tuning must be labeled.
No new native-vendor or perceptual score. No redistribution of original audio.

Inherited blocked evaluation files remain local-only; do not republish them by
another path. This study will add its own independently scoped detector and
recombination checks and compare against committed renderers. Missing publication
or CI coverage must be stated, not masked by skipped imports.

Conceptual sources: Driedger/Mueller/Ewert HPTSM (2014),
https://www.audiolabs-erlangen.de/resources/2014-SPL-HPTSM/ ;
Prusa/Holighaus Phase Vocoder Done Right (2017),
https://arxiv.org/abs/2202.07382 ;
Akaishi/Holighaus/Yatabe SELEBI (2026), https://arxiv.org/abs/2602.16421 .
These motivate the hypotheses; none is reproduced in full here.
