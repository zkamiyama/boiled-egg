# Explicit ramps: final resumption and verification — 2026-09-15 JST

## Delivered scope

The agreed order is implemented on draft PR #10, stacked on #9: arbitrary-duration pitch ramps, variable-time streaming ramps, then an independent offline phase-gradient comparison. The new ramp API is public pure C with header-only C++ wrappers, opt-in spectral only. WSOLA/default plugins, existing event/state interpretation and stable main are not promoted or replaced. Issues #1/#2 remain open for their broader adoption requirements.

This resume began at `2d2b7fbefd162438145502420bd9a489d5eb8a47`, where the core features, study and earlier validation were already committed. It downloaded CI artifact10376129630 and verified its ZIP SHA256/CRC and all197 source hashes before rebuilding. Those inherited implementations are not claimed as newly invented in this resume.

New code commit `f8e5ef2cbce84f396597860a408b4a3084796115` adds independent randomized trajectory tests only. Its tree `d8eeb9b7e5c81a1f0b87f881a0d9608fd229903b` exactly matches the tested local source. No DSP, ABI, thresholds, benchmark policy, plugin UI/state or existing evaluator arithmetic was changed by that commit. This final record is documentation only.

## API behavior

`boiled_egg/automation.h` exposes `boiledegg_process_realtime_ramps`, `boiledegg_push_ramps` and `boiledegg_get_automation_info`, plus RAII methods. Events are fixed32-byte records, sorted, at most256 per call. Each call has a single audio owner; the ramp API is not a concurrent UI mailbox.

Duration0 is a step. A positive N reaches its target on the Nth accepted input sample, counting the event sample as1. Linear-ratio and log-ratio curves are independent of ratio/semitone target units; log pitch ratio is linear semitones. Interruptions and repeated targets restart from the current effective value. The old event entry points keep their default10-ms interpretation. Existing CLAP/VST3 points/state and the ReaPitch-inspired editor are not reinterpreted; no new ramp-duration GUI knob is claimed.

Variable time additionally requires CONTINUOUS_TIME, CONTINUOUS_PITCH and streaming I/O. Accepted inputs drive W=sum(T) and V=sum(T*p). Both ratios are [.5,2], with the conservative rectangular bound max(currentP,targetP)*max(currentT,targetT)<=2 checked after each equal-offset group. Some safe opposing curves are intentionally rejected. Backpressure consumes only the accepted input/event prefix; callers drain and rebase the remainder. Pull advances neither ramp. Flush freezes effective controls at the end of real input and emits floor(W+.5) samples, without completing an unfinished ramp using padding.

Realtime remains T=1, with fixed full-pitch-range delay: Transient2112/4160 samples at48/96k and General3648/7232. Exact input timestamps are not instantaneous spectral response: STFT windows still spread transitions. See AUTOMATION_RAMPS.md and the installed-C consumer_ramps.c for construction, return-code handling and an executable example.

## New randomized regression

`tests/ramp_randomized_checks.hpp`, invoked by the existing time-ramp CTest, generates deterministic interrupted pitch/time plans with both curves; durations0,1,2,31,257,1500,UINT32_MAX; duplicate-offset commands; independent targets; and a long deliberately backpressured stream. Targets stay in the declared coupled envelope. The reference evaluates each segment in long-double closed form, not by importing/reusing the private ramp recurrence.

There are **8115 accepted-prefix checkpoints** and **13 paired output cases** across48/96k, both qualities and three formant policies, comparing block31/257. It checks effective values, remaining durations, both independent integrals, EOS rounding/freezing, pull purity and finite linked-channel output. The backpressure case must actually encounter an unaccepted suffix. These pass; no underlying runtime defect was found by this additional test. These test renders are not counted as extra perceptual-quality evidence.

## Fresh local build and evaluation

| Verification | Result |
|---|---|
| GCC14.2 and Clang17, C++20/23, spectral ON |23/23 CTests each|
| Matched Clang ASan+UBSan, leak detection on |23/23|
| Spectral OFF |13/13|
| Installed shared ON and OFF C11/C++ consumers |3/3 each|
| Python ramp7 + existing dynamic12 + phase7 + legacy dataset3 |29 tests, no skips|
| Independent heap kernel |513000 affine phase values,917916 bounded heap removals,zero processing allocations|

Fresh primary evaluations:144 paired synthetic trajectories/288 outputs,480 paired actual-source trajectories/960 outputs,72 synthetic plus180 natural phase-study outputs. **1500 primary outputs**, not added to earlier-session/CI reruns as independent cases. The supplied20 mono44.1k sources are used directly and fingerprinted; source audio/MOS is not redistributed.

All480 natural ramp pairs are identical at blocks32/257, with exact finite output metadata and independently calculated duration. The144 analytic pairs also match, and1008 settled plateaus pass the unchanged5-cent/stereo controls: max settled error **0.1284670533 cents**, relative stereo error7.65439e-8. Max W/V error3.3644028e-8 samples in the analytic set and7.3341653e-9 in the natural set. These are control/settled-tone and integration results, not a whole-transition or native-vendor accuracy claim. Natural max raw sample peak1.619558;195/480 conditions exceed unity and are not silently limited.

Measured library SHA256 remains
`b25182a3246fb2cdf4b3e414b01b7b5ad26ee2b51e32c38f8a238e038d257e63`.
Fresh analytic CSV SHA256:
`595882e29cb1a074731ae916da5dbf6572de9bd6394edd48242b47d0b3ae512a`.
Fresh natural ramp CSV SHA256:
`7c900cfc4be6ae942c277b43dcce0e7a52a4707b76669b5d6ec9517b70c06140`.

## Phase comparison remains research

The independently implemented magnitude-prioritized phase-gradient integrator follows the idea of Prusa/Holighaus, Phase Vocoder Done Right (EUSIPCO2017; arXiv posting2022, https://arxiv.org/abs/2202.07382). It is not copied competitor code. All three compared renderers share input/windows/hops/resampling. The Python renderer needs one future frame and allocates; only the C++ kernel is allocation-free. No formant preservation, live automation or host qualification is claimed for this research renderer.

At48k, six pitches, partial relative-energy error is locked0.557228, temporal trapezoid0.072112, heap0.007490dB. Short-attack width is7.160486,23.325281,0.994823ms respectively. These are only two analytical fixture families.

Actual20-source TSM at ratios.5/1.5/2 gives:

| Descriptor | Locked | Temporal only | Heap |
|---|---:|---:|---:|
| Global normalized Welch PSD shape, lower |1.347236|2.269444|0.771756dB|
|5-ms RMS-envelope shape, lower|1.602618|3.744826|1.880296dB|
|Positive RMS-flux correlation, higher|0.453783|0.295040|0.434090|

Heap improves global PSD in60/60 conditions, but worsens RMS shape in43/60 and onset in35/60. It is therefore retained as research, not promoted. These source-relative definitions differ from previous cepstral/STFT metrics; do not pool them, label them native-zplane results or turn them into perceived-quality percentages. The source set has been used historically. Fresh phase CSV SHA256:
`477af8cc55b87c105e3ff30c31b1da80cf90ee75fd714c8269b050b28019b88c`.

## Fresh practical timing

After local build/evaluation work completed: CPU0-affined wall-only runs,24 settings (48/96k,stereo,General/Transient,three policies,32/64),three repetitions. Two explicit pitch events/callback exercise steps and interrupted linear/log ramps; formant mailbox updates are included. Warmup consumes the declared delay plus.5seconds. Per-state output fingerprints match. 86400 steady and67986 cold calls are retained.

Under the unchanged max-over-states(best-of-three)<=80%period policy, **24/24 pass**, worst ratio **0.380964**. Raw individual period misses30/86400, maximum ratio11.8587915 and57/72 actually complete steady runs below their periods remain reported. This is empirical library capacity, not p99/WCET, an uninterrupted run stitched from minima, or whole-DAW timing qualification. No noise subtraction or physical root-cause claim.

## Hosted verification and actual upload failure

At f8e5ef2 all eight workflows completed successfully: ci34919503529, rt-measurement-audit34919503710, dynamic-plugin-sanitizers34919503590, research-pv34919503539, dataset-tools34919503515, dynamic-pitch-editor34919503561, spectral-backend-preview34919503715 and automation-ramps34919503413. This includes public ramps, actual existing host modules/editor, ON/OFF, address/undefined/thread checks and practical capacity.

The first automation-ramps attempt had two artifact-upload failures after code checks passed. GCC20 job104224212004 logged a403 Forbidden at FinalizeArtifact after uploading2783636 bytes; Clang20 also failed the upload step. The failed workflow was rerun through the same authorized action without code, permissions, thresholds or continue-on-error changes. The rerun succeeds, including upload. No billing/source cause is inferred; earlier failure evidence is retained rather than called a test pass.

Final successful artifact10377637682 ZIP SHA256:
`c8205a32c6d253ae8e50d682a014e8ca2061c46c6dd8e8ec183d11297fa8e387`.
It was downloaded, CRC checked, and all **198 tracked hashes** match the measured local source. Its synthetic merge f57ef970f5789c6c6f922941457accebf7061b36 has the same d8eeb9b7 tree as the code checkpoint. Separate CI capacity is24/24, worst0.456552,zero raw steady misses and72/72 complete steady runs; those observations do not erase local30 misses.

The delivery includes source, test changes, fresh CSV/JSON, raw timing, logs and checksums. It excludes user recordings/MOS, generated audio, external SDK sources and fonts. Main remains protected from unqualified research promotion. This record does not claim native-zplane comparison, listening, a new GUI parameter, dynamic-time fixed-I/O insertion or completion of every item in Issues1/2.
