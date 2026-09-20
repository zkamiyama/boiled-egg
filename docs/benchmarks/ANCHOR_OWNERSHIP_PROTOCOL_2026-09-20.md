# Full-band anchor ownership ablation — 2026-09-20 JST

Base main18e74119694d869e01db22592941da887314795c, treeec0ee7895abbc0dd4f505d9e7164e4f89b4756fa. Related #41/#19/#17, parent #15. Register before new renders. PR42 long_wide recovered pure-tone criteria but violated transient stops. PR13/14 used component separation/local replacement and suffered real-corpus or detector losses; do not repeat that mechanism or treat supplied landmarks as detection success.

## Hypothesis and intervention

A single event may occur in multiple source grains at incompatible output positions. Constraining every contribution that touches its protected source/output neighborhood to one time-map intercept may remove duplicate/smeared events. Wide waveform-similarity search remains available outside those neighborhoods. Explicit source landmarks isolate synthesis from detection. No automatic classification, detector, component separation, residual replacement, PV fallback, learned score or generated replacement tone.

Add only a separate C++20/23 finite-file NRT research kernel and Python measurement host. Not installed SDK ABI or a product-mode change. Mono48/96k, time1, constant pitch ratio[.5,2], input<=3s, at most16 landmarks, normalized finite nonzero input. Single synchronous call; offline allocations permitted/bounded; no realtime/streaming/freeze/formant/stereo qualification. Existing298 source files and defaults remain unchanged.

New kernel is an independent centered WOLA/WSOLA adaptation, NOT PCM-equivalent to SDK WSOLA. Window4096/8192, hop window/4, search20ms, Hann weighting, normalized overlap, correlation coarse step4/8 and sample stride2/4 with fine refinement. Zero padding at file edges; output length exactly input length. Internal duration multiplier=pitch, followed by fixed64tap Blackman sinc resampling with cutoff .94*min(1,1/pitch). No output gain or lag fit. Exact unity bypass is declared separately.

Three manually selected ablation modes share this kernel:
1. free: source center near output_center/pitch, selected by normalized correlation with the preceding grain's natural continuation.
2. snap: add one grain centered at each rounded intermediate target pitch*source_anchor, and lock grains whose support touches that target to source_center=source_anchor+output_center-rounded_target; choose nearest anchor when supports intersect. No ownership mask.
3. owned: same positions as snap; additionally suppress a contribution if its source sample is within6ms of any marked source anchor OR its destination is within6ms of that anchor's intermediate target, unless its grain has that anchor's exact source-minus-output intercept. Renormalize only surviving weights; fail on uncovered output samples. Protect nonoverlapping neighborhoods: reject anchors whose input or intermediate-target separation is <=12ms, not silently merge/drop them. Always retain grain source/target centers, selected anchor, scores, masked counts and weight extrema.

This rule attempts to prevent duplicate event transport but may impose incompatible tonal phase at successive anchors or discontinuities at mask boundaries. Those are explicit rejection outcomes, not artifacts to fit away. Supplied markers are a diagnostic/edited-offline capability only. Missed/shifted/false markers remain controls; do not report oracle-marker results as automatic detection or universal quality.

## Fixed grid

12 generated1-second families, endpoint20ms fades for tones, no hidden random tuning:
- tone41, tone61, tone83 phase0; tone97 phasepi/3;
- harmonic61 partials1/2/3/5 amplitudes .12/.06/.03/.015;
- bursts_sparse: .18-amplitude4kHz Gaussian carrier bursts at .24/.64s, sigma1.5ms;
- mixed61: those bursts plus .08-amplitude61Hz tone;
- dense83: same bursts at .420/.447/.650s plus .08-amplitude83Hz tone;
- missed61: mixed61 with only first marker supplied;
- offset61: mixed61 with both supplied markers2ms late;
- false61: pure .2-amplitude61Hz with false markers .24/.64s;
- extension53: .08-amplitude53Hz phase.37 plus3kHz bursts at .293/.681s, sigma2.5ms.

All true centers remain evaluator metadata; the renderer receives only the declared supplied marker file. Empty marks for unmarked tones. 5 arms: unchanged SDK default and long_wide at block64, new free/snap/owned. 12families x2rates x3shifts(-12/0/+12) x5arms =360cells,3fresh executions =1080. Block32 checks belong to SDK regression, not fictional streaming of the new offline kernel. Every run and its timing/PCM/file hashes is retained; duplicate byte storage may be content-addressed. Do not select only favorable source/pitch/marker conditions.

Before the grid, register a plan SHA binding inputs/marks/all source/new binary/SDK library/dependencies/settings/measurement/environment. Acoustic revisions require a new experiment and preservation of preceding results, not overwriting. No natural audio or MOS is generated in this bounded first unit.

## Measurements and decisions

Reuse offline_pv_benchmark unrestricted dominant-frequency and joint sinusoid amplitude/unexplained-energy diagnostics. Pure tones: settled .15-.85s; <=5cent, <=1dB amplitude error and unexplained energy<=.01 separately. False-marker tones remain separately visible. Harmonic diagnostics retain each target partial; not misrepresented as single-tone qualification.

Events: keep raw sparse-event metrics as previously defined; additionally apply the same fixed zero-phase4th-order1kHz highpass to output and an analytic local-resampling oracle (event centers unchanged, carrier*pitch, sigma/pitch). Measure energy centroid and5-95% width in nonoverlapping windows bounded by center midpoints and80ms outer radius. Keep missing/weak event counts, energy relative to oracle, and full-file out-of-neighborhood leakage. Gates for correctly supplied sparse/dense/extension marks: absolute position<=1ms, width<=1.2*oracle, absolute event-energy error<=3dB, and no worsening relative to SDK default by>1ms or width>1.2x. Missing/offset controls are sensitivity, not positive gates.

Mixture bass: same fixed4th-order500Hz lowpass applied only for diagnosis; .15-.85s unrestricted peak, target amplitude and unexplained energy. Keep raw full-wave peak/RMS and max sample difference; filtering must not be called a perfect component decomposition. Whole-interval bass failures/phase modulation must remain even if a selected steady subinterval looks good. A clean isolated tone plus a correctly placed isolated burst does not establish success on their mixture.

Accept only a scoped research result if both bass and event criteria pass on the relevant correctly marked mixture cells without hiding identity or marker controls. No generic product promotion, Issue41 closure or naturalness superiority from this screen. Runtime/execution integrity success is distinct from quality failure. Time per full offline call, per-cell3-repeat median, cold/warm and actual memory estimates/process RSS; no callback80%/1.25x hard-RT claim.

## Controls and review

Calibrate known frequencies including50cent faults,10ms event shifts, missing/zero signals, marker shifts, timestamp versus PCM hash. New kernel tests: length/identity/determinism, no-marker ablation identity, exact anchor intercept/mask ownership, malformed/unordered/duplicate/close/boundary marks, budgets/NaN/Inf/stereo scope, errors without partial outputs. GCC/Clang20/23 plus ASan/UBSan on new C++ kernel; synchronous independent-object threads if tested, no invented same-instance concurrency. Fresh unchanged SDK26CTest and scoped existing Python regressions; missing assets/zero test counts/skips are not passes.

## Primary context, not a reproduction claim

Driedger/Mueller TSM Toolbox author page https://www.audiolabs-erlangen.de/resources/MIR/TSMtoolbox/ includes classical WSOLA and nonlinear anchorpoint mappings. Verhelst/Roelands ICASSP1993 DOI10.1109/ICASSP.1993.319366 is WSOLA's origin. The ownership rule here is our bounded engineering experiment, not their exact algorithm, not SELEBI, and not a new claim of academic priority. The prior PR13/14 failures justify separating landmark detection from full-band transport in this unit.
