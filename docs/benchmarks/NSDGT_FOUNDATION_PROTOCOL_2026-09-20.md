# NSDGT numerical foundation / preregistration — 2026-09-20 JST

Base main c8ffe65a24d21e627a3558883497daeb853473de; tree8db4ba61f000175de9118d60bdee2a2de4a9d7d5. This document precedes the new transform implementation tests and numerical grid. Scope is Issue44 only; not SELEBI/PVDR quality reproduction. Existing308 files remain unchanged. Single bounded research unit, not a promise of background work.

## Research sequence

Issue44 numerical analysis/dual synthesis -> Issue45 paper-condition SELEBI/PVDR reference -> Issue46 48/96k pitch/compression and joint bass/event validation. Issue47 constrained resynthesis is conditional on a measured deficiency, not compulsory. Issues48/49 are independent NRT product and bounded-lookahead RT promotion tracks after scoped quality evidence. Parent19/15, quality17 and existing WSOLA defect41 remain separate. PR40/42/43 are complete historical experiments, not patches to reapply.

## Mathematical contract

Fixed frequency channel count M, real finite windows g_j of length W_j<=M and strictly ordered integer centers a_j. Window sample r corresponds to t=r-floor(W_j/2), local phase origin at a_j. Input is a finite complex vector x[0..L-1], zero outside this interval; no cyclic wrapping of the input. The FFT slot is t modulo M. Coefficients:

C[j,k] = sum_r x[a_j+t] g_j[r] exp(-i2*pi*k*t/M).
D[l] = sum_j g_j[l-a_j+floor(W_j/2)]^2 (in-support samples only).

The forward FFT is unnormalized, inverse FFT has1/M. Synthesis overlap-add uses g_j[r]/D[l] after inverse FFT. Thus the normalized analysis energy (1/M)*sum|C|^2 equals sum D|x|^2. Standard unweighted coefficient frame bounds are M*minD and M*maxD. The matrix is diagonal only in the declared painless W_j<=M regime. Reject W_j>M; do not pretend the diagonal inverse is general.

This is a finite zero-extension independent implementation grounded in SELEBI II.B/C (fixed M, variable windows/hops) and nonstationary Gabor frame theory. The paper uses periodic indexing; our finite boundary is a documented difference. No phase-vocoder time/pitch modification, detector or quality claim is included. Use the existing product's float FFT as an unchanged numerical primitive, double accumulation for overlap/diagonal, and independent complex128/direct DFT references. Never copy external GPL implementation into the product.

## Validation and budgets

NRT-only C++20/23 research library, not installed or linked into the SDK. Expose bounded analysis/synthesis of interleaved complex float arrays plus explicit windows/schedule. No retained hidden source: synthesis takes coefficients and schedule, never original input. Accept mathematical zero inputs but reject a zero output for a nonzero reconstruction fixture in the evaluator. Deliberately erase coefficients and confirm zero synthesis, and scale/edit coefficients to reject bypass fake success.

L1..288000, M power of2 in16..16384, W2..M, at most4096 frames, at most8388608 complex coefficients, real finite window values |g|<=1, complex finite input bounded componentwise1 for analysis. Window offsets and coefficient capacities are validated before access. Full windows have explicit supplied support; no hidden source-dependent adaptation. Plan/operation memory estimate bounded by declared budget, with sizes checked before allocation. Record analytical storage separately from process peakRSS/allocator and caller-owned buffers. Reject minD==0 (uncovered), minD<1e-8 or maxD/minD>1e6 (ill-conditioned); NEVER add epsilon or clamp a denominator. Reject malformed/short arrays, invalid centers, NaN/Inf, arithmetic overflow, altered identities. No partial caller output on a reported failure.

## Fixed numerical grid

Rates22050/48000/96000 are fixture metadata, not rate-dependent hidden behavior. M1024/2048/4096 respectively. Lengths17,1001, floor(rate/8)+1. Eight signals: first/middle/last impulses amplitude.5, real61Hz sine amplitude.2, constant.1, fixed-seed uniform complex noise[-.1,.1], complex chirp (real/imag sinusoid amplitude.15), and all-zero mathematical control. Source seed20260920, each input generated once and hashed before runs.

Four explicit schedules: fixed long Hann (hop M/4), smooth lengths between M/8 and M (hop M/32), abrupt alternating long/short Hann and sqrt-Hann (hop M/32), and irregular deterministic hops M/64 times[1,3,2,4] with window lengths cycling[M,M/2,M/8,M/4] and real Hann/rectangular windows. Include center0 and L-1, deduplicate centers, use exactly specified windows. They are transform stress schedules, not SELEBI onset detection.

3rates x3lengths x8signals x4schedules =288 cells;3 fresh analysis+synthesis runs =864 pairs. Retain full input/schedule, complex reconstructed outputs, coefficient hashes, per-cell diagnostics and every repeat timing. Full large coefficient arrays need not be archived: record hash and retain complete small direct-DFT cases; reproduction regenerates them from retained input/schedule. No silent successful subset.

Before the grid run, register a plan SHA binding all source/FFT, input/schedule, new library and linked dependency hashes, numerical environment and the complete grid. A changed binary gets a new plan/run. Exploratory test failures remain separate. Any change after the full grid requires a new plan and paired rerun.

## Fixed gates and independent controls

For nonzero inputs: max complex sample error/input peak <=3e-6; relative L2 error<=3e-6; finite output and nonzero energy. Zero input must return exactly zero. Imaginary residual on real fixtures is separately retained, not silently dropped. Coefficient error vs independent complex128 FFT <=3e-6 after normalization by max(1,input L1 window norm bound); independent dual synthesis vs native <=3e-6 relative to input peak. Parseval/frame-diagonal relative error<=5e-6 (zero case separate). Repeat coefficient/output bit identities must match within each environment; no cross-compiler bit identity promise.

Small direct-DFT and direct exponential synthesis with M16/32/64 and odd/even/asymmetric/negative real windows independently test phase origin and inverse1/M; tolerance3e-6 absolute at bounded amplitudes. All canonical basis impulses for a small odd length must reconstruct (not only one tone). Coefficient edits/erasure, complex linearity, idempotence and Hermitian property of coefficient projection A*S test that this is an actual transform and canonical dual. Expose holes and ill-conditioned examples by naive window shrink/large gaps/near-zero window gains; record rejection, never optimize their parameters after measurement.

Run exact enabled CTest inventory and unique Python control IDs, skip0. GCC/Clang20/23, ASan/UBSan and independent-call thread test (TSan if runnable); existing SDK freshly built/full26CTest as a bounded unchanged-source regression. Missing runtime support is a recorded nonpass, not a suppressed test. Cold/whole-call timings are not realtime callback capacity. Main defaults/state/IDs remain untouched.

## Primary references and follow-on boundary

https://arxiv.org/html/2602.16421v1 (II.B/C equations1-4 and IV/V; fixedM, variableW/hop)
https://arxiv.org/abs/1612.05156 (nonstationary Gabor PV)
https://github.com/ltfat/phaseret (external reference for Issue45, not a copied implementation)

A successful unmodified roundtrip and stable dual do NOT prove edited coefficients consistent or natural. This unit does not fix #41, complete #45, change quality/formant policy, or qualify pitch/formant/stereo/freeze/RT. Issue45 must still freeze actual paper windows/hops/masks/phase conventions, licensing and baseline source before a new acoustic experiment.
