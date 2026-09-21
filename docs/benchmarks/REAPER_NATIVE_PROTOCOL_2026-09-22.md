# Native vendor comparison through REAPER — 2026-09-22 JST

Issue58, parent17/20/15. Base main1d01d9a59d4c2f6a9775dd9bc975195667639b4e,
tree ac208e780d0b3d8f0d83ff9d6d0f427d407e70bf. This unit adds an external-host
adapter and objective comparison, not another costly DSP candidate. Existing
product defaults, ABI/state/IDs/latency/tail and all337 existing files stay unchanged.

## Actual external software and boundary

User-provided ELASTIQUE_DEMO_3.4.5.zip contains one Windows EXE; it is archived
privately but is not executed in this Linux experiment. User-provided REAPER7.80
Linux x86_64 is run as the complete application through its public CLI and Lua
API. Its actual EnumPitchShiftModes responses expose elastique3.3.3 Pro,
Efficient and Soloist. These are not interchangeable with the3.4.5 demo or a
standalone zplane SDK build. No proprietary module is loaded outside its host,
reverse-engineered, modified, or redistributed with project sources.

The two original archives were privately stored and downloaded again; SHA256 and
sizes match. Backup does not grant perpetual trial or redistribution rights.
REAPER's official evaluation is60days with full features. No trial/license state
is cleared, forged or bypassed. A dedicated configuration isolates user projects;
the same profile is retained across this experiment. Vendor archives are not put
in GitHub or public CI. Keep private Drive IDs out of the public repository.

## Adapter qualification before scientific grid

Use exact REAPER7.80/Linux version and runtime enumeration, not guessed ordinal
labels. Required profiles: Pro/Normal mode9/sub0; Pro/Preserve Formants (Most
Pitches)9/4; Soloist/Monophonic11/0. These IDs are accepted only when the actual
names also match. The adapter fails on unavailable/name-mismatched modes, output
overwrite, invalid ranges, missing audio and incorrect readback. No fallback.

Each new project has one source item, no FX, unity item/take/track/master gain,
center pan and unity pan law, no item/automatic fades or looping, source offset0,
D_PLAYRATE=1/time_ratio, D_PITCH=semitones, B_PPITCH=1 and explicit I_PITCHMODE.
Render uses exact bounds/rate/channels, FLOAT WAV, no normalize/dither/tail. Save
per-render project, public API readback and output. Use normal action41824.
The host can bound/crop its output at the requested duration; this is an explicit
REAPER offline-render contract, not unbounded raw SDK buffering.

A first sink-format probe produced PCM16 and was rejected; the verified FLOAT
configuration is ZXZhdyAAAA==. Preflight223Hz controls use unchanged duration,
+/-12st, and time ratios.5/2 with pitch preserved. Verify length/pitch and exact
unity PCM, and inject a wrong engine name. These are adapter controls, not the
registered comparative-quality observations. A missing physical JACK device does
not prevent offline file rendering and is not a physical DAC test.

## Fixed first comparison

5 generated families x48/96k x-12/0/+12st x8 explicit engines x3 repeats=720
renders (240cells). All use2second mono inputs and time_ratio1. No transient or
pitch automation, freeze, stereo, live device, natural voice or MOS claim.

Families: .2-amplitude61Hz sine, phase.31,30ms endpoint fade; two synthetic
harmonic-envelope signals F0=120/220Hz, harmonics1..30, phases.17*k and amplitudes
.03*E(kF0)/k^.7; Gaussian bursts amplitude.18/sigma1.5ms/carrier3500Hz at.55/1.35s;
.08-amplitude61Hz plus those bursts. Envelope E(f)=.08+exp(-.5*((f-650)/95)^2)
+.8*exp(-.5*((f-1200)/125)^2)+.6*exp(-.5*((f-2500)/180)^2). These are synthetic
signals, not recorded speakers or an independently sampled natural corpus.

Vendor engines are the three profiles above. SDK engines are fresh unchanged
main WSOLA General Off; PV General Off/Harmonic/Monophonic; PV Transient Off.
Use the actual backend CLI with block64 and explicit spectral opt-in. No copying
an old research patch, automatic method choice or unsupported-formant substitution.

## Separate correctness, abnormalities and quality evidence

Reuse comparison_contract audio/hash/ratio validation and offline_pv_benchmark's
unrestricted dominant-frequency estimator and sinusoid-component measurement.
Keep every attempt and failure. No silent-output success, gain/lag fitting, DTW,
normalization, clipping, successful-subset ranking or relabelling old binaries.

For61Hz, measure the middle1second:5cent frequency,1dB target-component amplitude,
1% unexplained-energy goals, separately and jointly. Mixed bass uses a fixed
500Hz fourth-order zero-phase lowpass as a diagnostic, not a true separated stem.

For harmonic signals, measure30 target sinusoidal components in the same1second
interval (all tested target frequencies are integer Hz). Off target keeps original
harmonic amplitudes while shifting their frequencies by p. Preserved target is
.03*E(kF0*p)/k^.7. Report absolute dB-RMSE separately to both targets at frequencies
250..3500Hz where max(targets)>=.00015, plus unexplained energy. No fitted gain is
removed. This is a specified continuous-filter engineering target, not a unique
ideal voice or a MOS scale. Pro's chosen preserve-preset is not claimed equivalent
to either boiled-egg policy; Soloist is recorded by its actual complete mode name.

For bursts/mixed events, use1kHz fourth-order zero-phase highpass and fixed+/-80ms
windows. Save absolute centroid error,5-95% width and energy; centroid is not onset.
Retain raw full peak/RMS. No formant policy is silently treated as Off to create an
ideal transient waveform. Event findings are descriptive, not a naturalness gate.

Freeze input/source/executable/libraries/settings/environment/plan SHA before the
full comparison. Three repeats check within-environment output reproducibility,
not independent quality samples. Vendor nondeterminism must be reported rather
than changing settings to force equal output. Host render wall time and SDK CLI
wall time have different overhead; do not compare them as kernel CPU or callback
capacity. quality_selection remains null. No blanket elastique parity claim.

## Sources and acceptance

Official REAPER ReaScript API: https://www.reaper.fm/sdk/reascript/reascripthelp.html
Official evaluation: https://www.reaper.fm/purchase.php
Official zplane demo distribution: https://licensing.zplane.de/technology
Use runtime help and API readback for the supplied binary's actual behavior.

A successful unit delivers the running adapter, calibrated negative controls,
complete raw/provenance/results, and explicitly named remaining comparisons.
Vendor-free CI tests are not REAPER render evidence. Any product change requires
a separate justified fix and its own regression gates; this comparison changes no
product DSP. Future real vocals/phrases, dynamics, stereo, TSM, other preservation
presets and the3.4.5 Windows demo remain distinct work.
