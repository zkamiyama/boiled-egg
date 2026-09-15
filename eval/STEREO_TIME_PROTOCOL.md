# Roadmap B: stereo and local-time audit (2026-09-16 JST)

Parent roadmap #15 / qualification #17, after the analytical formant audit #23.
Evaluation only. No product DSP, ABI, plugin, defaults, eligibility or main change.
This audit does not grant listening eligibility or select a winning algorithm.

## Frozen panel and inputs

Reuse the named configurations of eval/formant_audit/study.py: PV General and
Transient, each Off/Harmonic/Monophonic, and direct offline Rubber Band R3
Off/Preserved. Preserve distinct policy names. R3 is external/evaluation-only,
not native zplane. Record actual executable/library/dependency hashes.

Two seconds, 48/96 kHz, five operations: T=1,p=1; T=.9/1.1,p=1;
T=1,p=2^(+/-7/12). Four deterministic stereo fixtures per operation:
1. broadband/tonal signal with R=-.375*L;
2. the same left signal with an exactly silent right channel;
3. alternating left/right 4ms windowed bursts at .30/.75/1.20/1.65 seconds;
4. the preceding bursts with channels exchanged.
Total: 2 rates x5 operations x4 fixtures x8 configurations=320 rendered outputs.
No fixture/threshold adjustment after rendering. No external recording required.

## Independent checks, not an aggregate quality score

Require unchanged rate/channels, finite float32 WAV and requested rounded length
with the inherited at-most-one-frame rounding allowance. Check the linked
proportional residual norm / left norm and silent-channel norm / left norm
against the predeclared 1e-5 relative control. Zero output energy is a failure,
not a perfect stereo score. Channel exchange covariance is measured separately;
there is no inferred full-stereo transparency from these limited examples.

For each known burst, report energy centroid minus prescribed T*input-center,
5%-95% energy width, captured energy and opposite-channel leakage in a fixed
+/-80ms output-time window. Do not correlate/search/crop/shift audio to fit a
preferred answer. These are finite-window, single-burst diagnostics, not proof of
all-frame alignment. A local transient-preserving time stretcher may intentionally
redistribute positions; report deviations without a post-hoc quality cutoff.
Do not treat the earliest peak or the shortest width as automatically correct.

Keep metadata/relational-control failures, all configurations and raw receipts.
No raw normalization, limiter, gain fitting or latency subtraction. The reference
uses its documented offline compensation. Presentation gain remains separate.
All current operation eligibility is unchanged; preservation quality and live-host
qualification still need separate evidence. Listener responses remain zero unless
actual explicit submissions are supplied. No new DSP research before roadmap B
has a documented use-case deficiency.

Official contract consulted: https://breakfastquay.com/rubberband/integration.html
