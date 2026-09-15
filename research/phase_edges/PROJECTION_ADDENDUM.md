# Supplement after the five-source pilot

The predeclared five-source edge pilot did not reverse the centered heap's
mean temporal regression. Means at ratios0.5/1.5/2: locked RMS1.651325/onset0.472192;
heap1.846691/0.455643; edge-both1.844961/0.447825. These are pilot descriptors,
not a whole-corpus conclusion or a defect established in the original paper.

A second, explicitly separate hypothesis is now included: refine the heap
initialization by alternating synthesis/analysis with projection onto fixed
input STFT magnitudes and fixed interchannel ratios. Each coefficient vector is
projected onto source_vector*exp(j*theta), with theta=arg(sum(conj(source)*estimate)).
Zero inner products keep the previous feasible point. No per-frame loudness
matching, waveform envelope compensation, limiter or output normalization.
The ordinary overlap-add normalization is unchanged.

Fixed iteration budgets are2,4,8; names project2/project4/project8. This is an
independently implemented linked-channel alternating-projection experiment,
not an exact reproduction of Griffin-Lim variants, SELEBI or a neural model.
All three start from the inherited centered heap, not the new edge transport.
It allocates and iterates over the whole signal: offline only.

The same five pilot sources give RMS1.731723/1.772095/1.786870 and
onset0.446180/0.439071/0.434577 for2/4/8 iterations, versus heap1.846691/0.455643.
Global PSD improves but onset does not. All variants, including losses, proceed
to the20-source report. The remaining15 names are not used to retune anything.

Before confirmation: the additional eight-bank test is fixed to seeds2609150..
2609157 and four comparators locked/heap/edge_both/project4 (the middle iteration
budget, not the pilot winner). Synthetic original-bank/attack/noise/stereo tests
include all eight modes,48/96k,6shifts plus separately reported unity. No final
winner selector or promotion rule is implied by this study.

Primary conceptual sources: Prusa/Holighaus Phase Vocoder Done Right,
https://arxiv.org/abs/2202.07382; SELEBI https://arxiv.org/abs/2602.16421;
Griffin-Lim alternating STFT consistency, with later optimization discussion in
https://arxiv.org/abs/2309.07043. No external implementation is imported.
