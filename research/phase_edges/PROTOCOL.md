# Edge-local phase transport: predeclared research protocol

Base: b3f6d8c53bcf1f9380aa104c4bfcb773609e8ec5, draft automation-ramp work.
No product DSP, ABI, plugins, defaults or existing phase-gradient renderer change.

Question: does differentiation to centered node gradients followed by trapezoid
integration blur local phase differences and contribute to the inherited heap
renderer's temporal-envelope regression? This is a hypothesis, not a proved bug
in the paper or the previous implementation.

The 2017 Prusa/Holighaus paper (arXiv:2202.07382, equations13-18 and Algorithm1)
uses centered gradients and trapezoid steps. This study instead tests transporting
the observed discrete phase increment directly along the selected graph edge.
The magnitude-prioritized traversal, input, windows, hops, weak-bin policy,
stereo rotations and output resampler stay matched. No transient classifier,
output envelope correction, limiter, optimized time alignment or copied external
implementation. SELEBI (arXiv:2602.16421,2026) motivates examining magnitude/phase
localization, but this is not its nonstationary-window algorithm.

Five fixed variants:
- locked: unchanged inherited identity phase-locking comparator;
- heap: unchanged centered-node/trapezoid comparator;
- edge_time: exact heterodyned interframe increment for temporal transport only;
- edge_frequency: directly wrapped neighboring-bin phase increment only;
- edge_both: both direct edge increments.

Temporal increment = actual synthesis hop * (bin omega + wrapped observed
interframe residual / analysis hop). Frequency increment = stretch * wrapped
neighboring-bin input phase difference. No parameters fitted per source.
Both-edge transport does not require a future frame for its gradients; the
comparison renderer remains offline and is NOT a qualified live backend.

Before whole-corpus results: independently test exact conservative discrete
fields, traversal against exhaustive-priority oracle, bounds, no allocations,
silence, endpoint bins, unity and stereo. The five pilot sources are fixed as
Ardour_2, Female_4, Male_6, Rock_4, Triangle_02. Then evaluate all20 provided test
references, retaining pilot labels; the rest are within-iteration confirmation,
not a pristine holdout. The corpus has been used historically.

Primary natural stretch ratios:0.5,1.5,2.0. Reuse the previous 5ms RMS shape,
positive RMS-flux correlation and global normalized Welch PSD descriptors; add
local multi-resolution spectral shape to detect global-PSD-only gains. Never
substitute missing user files. Independent synthetic tests: harmonic/inharmonic
banks, narrow attacks, noise and linked stereo at48/96k, shifts+-3/7/12 and unity.
New seeded banks fixed to2609150..2609157. All raw outputs are finite/exact-length
checked, unnormalized and fingerprinted. No native zplane or MOS inference.

Report every variant, wins/losses and source-cluster descriptive intervals, not
only a selected winner. Any post-pilot design change must get a separate name
and be declared before confirmation. Retain negative evidence. Candidate kernel
costs are compared on identical inputs with preallocation; microbenchmarks are
not full32/64-frame audio-callback qualification. Main remains unchanged.
