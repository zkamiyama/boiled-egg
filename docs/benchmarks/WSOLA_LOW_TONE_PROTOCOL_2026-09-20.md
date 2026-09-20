# WSOLA low-tone window/search ablation — 2026-09-20 JST

Base main939270b9b26fa04e481f3f6feaae0e90102599c9, tree294d9bfdaf950bcbf277d8be246b73dcefc2c260. Related #41/#19/#17, parent #15. This protocol precedes new acoustic measurements. PR40 already added isolated offline PV research; do not repeat it, promote its rejected iterative candidate, or remerge historical branches.

## Question and scope

Investigate the recorded61Hz WSOLA failure without a learned quality score or automatic backend switch. Hypothesis: the short search tolerance limits available phase-compatible segments; a longer window plus wider search may recover low-tone accuracy, at extra latency/work and possible transient damage. Window-only and search-only arms help separate effects but this is NOT a full factorial design: the public configuration constrains search<window/2 and the existing scheduler needs search<=hop/(time*pitch) for startup. Do not change SDK defaults or validation to conceal that limitation.

Add an explicit offline, finite-file research host that calls the actual unchanged C ABI/C++ core with named configurations. No new backend/quality/parameter/plugin ID; no live/freeze/formant/automation/stereo or hard-real-time claim. This is an SDK configuration study, not a newly invented WSOLA or guaranteed high-quality offline mode. Existing runtime, public headers, plugin, transport and GUI files remain unchanged. Restrict host to mono48/96k, formantOff, time1, pitch[-12,+12], finite nonzero audio<=3seconds; output directories must be new. Reject unsupported requests and preserve failure evidence. Never synthesize a replacement tone in the host.

## Fixed configurations (window/search frames)

|name|48k|96k|
|---|---|---|
|default|1024/128|1536/192|
|wide_only|1024/255|1536/383|
|long_only|4096/128|8192/192|
|long_wide|4096/960|8192/1920|

These are explicit user/research choices, never inferred from the input. The two long arms have rate-scaled windows, while long_only intentionally retains the production search at each rate. Record reported latency/tail/quantum from the real SDK; do not pass a long-window result off as unchanged realtime latency. Keep fifo262144 and qualityGeneral. Frame size32/64 are host input/pull partitions, not WSOLA frame windows.

## Complete generated exploratory grid

Ten0.75-second families: pure41/61/83Hz each at phase0 and pi/3, pure223Hz phase0, harmonic83Hz (partials1,2,3,5 with amplitudes .12,.06,.03,.015), isolated two-event4kHz Gaussian bursts, and those bursts mixed with223Hz. Pure-tone amplitude .2, stationary families have20ms linear endpoint fades. Bursts match PR40 centers .28/.49seconds and sigma1.5ms. Known61Hz phase0 replays #41; other synthetic conditions are fixed extensions, not an independent natural-audio holdout.

10 families x2rates x2blocks x3pitches(-12,0,+12) x4configs =480 cells, each3 fresh handles =1440 complete renders. Use unchanged shared-library C ABI via a bounded Python offline host. Keep input/output float WAVs, every receipt and repeat, no successful-subset scoring. Record hashes of inputs, all project source, library and linked dependencies, host/measurement code and numerical environment in a plan; register its SHA before the run. Do not attach old measurements to a rebuilt binary.

Reuse PR40 unrestricted dominant-frequency estimator, joint sinusoid amplitude/unexplained-energy diagnostic, fixed-window event position and5–95% energy width. No target-centered peak search, gain/lag fit, DTW, resampling of inputs or output normalization. Low/pure settled interval .15–.60seconds. Mixed signals retain raw peak/RMS only, not imaginary component isolation. No predicted or measured MOS is produced.

## Fixed decision criteria and controls

Tone fidelity: <=5cent dominant-frequency error; no zero/NaN/partial-length success; separately require target projection amplitude error<=1dB and unexplained energy<=.01 to call a pure-tone cell clean. Do not infer passing these from frequency alone. A config is not promoted to a product mode on this synthetic screen. For long_wide vs default, any burst event with absolute position error increased by>1ms OR width ratio>1.20 is a transient stop. Preserve regressions and tradeoffs per cell. A boundary width improvement cannot offset a frequency failure elsewhere.

Calibrate the estimator on every declared pure frequency/rate/shift before the screen: known frequencies within .1cent,50cent injected error detected; known10ms event displacement; added non-target component; silent/NaN input rejected. Check native length, streaming progress/EOF, whole-vs32/64 partitions, reset/recreate reproducibility and compatibility with the real backend CLI at default. Repeat WAV identities must match within this environment. No cross-compiler bit identity is assumed.

Timing is fresh-handle construction+full Python/native stream+destruction, excluding WAV I/O and analysis; record first cold construction separately and compare per-cell3-repeat medians. It includes Python overhead and is NOT callback capacity or native kernel timing. Record whole-run peak RSS separately, not as per-instance owned memory. Report analytical workspace/configuration and SDK latency separately. No80%-period or1.25x realtime gate is claimed for this offline study.

Run new host negatives and relevant existing measurement/import/contract tests with unique test IDs and skip0; freshly build unchanged SDK and verify full26-test CTest inventory. CI should run the complete declared grid, preserve expected quality failures and require execution/measurement integrity, not silently turn a known bad default into a passing quality result. The plan may change only before measurements or via a separately identified correction with full rerun and retained old evidence.

## Literature context, not authority-based adoption

Verhelst/Roelands, ICASSP1993, DOI10.1109/ICASSP.1993.319366 is the WSOLA origin. Driedger/Mueller's author review (Applied Sciences2016,6(2),57; https://www.mdpi.com/2076-3417/6/2/57) explains frame length/tolerance relative to lowest-frequency periods and transient repetition/skipping. Its often-cited50ms/25ms parameters are not blindly installed here: this implementation's scheduler and API constraints differ. Source inspection plus controlled experiments are required; a configuration improvement does not establish a universal algorithm fix or naturalness advantage.
