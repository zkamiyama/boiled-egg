# E3: extreme range and seven preservation presets — 2026-09-22

Base main6f3ed4508a1c0123539f2e32b8fd37dd8ebdb168, Issue60/58/17/15.
This is a bounded baseline measurement, not a DSP expansion or product promotion.
Existing product code, old primary comparison contract and Most-only study stay unchanged.
No automatic fallback, inferred vendor Hz boundaries or heavy iterative algorithm.

## Two panels fixed before audio measurement

PRESETS: four two-second synthetic harmonic sources. Development uses the previous
vowel120/vowel220 generator and envelope. Confirmation uses F0=97/311, phase .29*k,
30 harmonics, amplitude .03*E(f)/k^.7, E(f)=.08+Gaussian(730,110)+.8Gaussian(1420,150)
+.6Gaussian(2850,210), and30ms endpoint fades. These are separate generated source
families, not independent natural recordings.48/96k; time1; pitch-24/-12/+12/+24;
seven REAPER Pro Preserve presets plus SDK PV General Harmonic/Monophonic;3 runs.
4*2*4*9*3=864 attempts. All7 presets are included with exact runtime names/IDs.

BOUNDARIES: previous low61/bursts/mixed61 fixtures,48/96k, and11(time,pitch) pairs:
(1,0),(.25,0),(.5,0),(2,0),(4,0),(1,-24),(1,24),(2,12),(.5,-12),(1,7),(1.5,-5).
Pro Normal, SDK WSOLA General, SDK PV General Off/Transient Off;3 repeats.
3*2*11*4*3=792 attempts. Total1656 planned attempts. This is a finite-file offline
screen with fixed block64; no8x stress, stereo, formant shifting, ramps or freeze.

## Capability and output contract

Use real SDK query/validate for every requested configuration and store status,
float32 ratios and build inventory. Nonzero status is unsupported only when it
matches the independently declared existing capability; unexpected status fails.
Unsupported rows remain in the denominator, with no output or fabricated score.
Pro uses the complete supplied REAPER7.80/linux-x86_64 and its named elastique3.3.3,
not the archived3.4.5 demo or a private library call. Reuse public Lua/render actions,
readbacks and saved projects. No trial reset, binary modification or redistribution.
Check process exit, complete batch counts, FLOAT, exact rounded length, rate,
mono, finite/nonzero PCM, file hashes and3-repeat identity. Failed rendered audio
is different from unavailable SDK configuration. No trimming/gain fitting or
resampling of measured output. Host bounds are finite render bounds, not a proof
of rawstream latency compensation. Times of host actions and CLI calls are separate.

## Metrics and calibration

Reuse unrestricted dominant-peak pitch and sinusoid projection. Pure-tone gates:
5cent,1dB target amplitude,1% unexplained energy, each retained. For variable time,
measure output source-clock interval[.5T,1.5T]. Noninteger harmonic frequencies
use joint sine/cosine least squares, NOT rounded FFT bins. Harmonic target frequencies
are k*F0*p; only frequencies below.45*rate are measured. The excluded harmonics
are explicit; no requirement to reconstruct beyond Nyquist. Preserved target
amplitudes use E(k*F0*p), Off target uses source amplitudes. Score250..3500Hz bins
whose larger target amplitude>=.00015. Retain both dB-RMSE values, residual,
fundamental amplitude and raw peak/RMS. This analytical envelope is not MOS or a
universal vocal ideal; amplitude projection changes no output gain or phase.

For events move centers by T, locally resample each original Gaussian by p
(sigma=.0015/p,carrier3500*p), retaining its peak. Filter both output and analytic
oracle with the same1kHz fourth-order highpass. Compare centroid,5–95% width,
energy and outside-window energy in center windows radius min(.08,.35*T).
Centroid is not onset. The lowpass500Hz mixture tone is diagnostic, not separated
truth. Keep raw positions and failures; do not average away energy/width tradeoffs.
Calibrate noninteger tones/harmonics, silence, time-scaled positions, gain faults,
wrong output length/type, invalid preset, fabricated unsupported and incomplete grids.

## Selection must precede confirmation

Execute development first. For each pitch, select the vendor preset with the lowest
mean preserved-envelope RMSE across the2development sources/2rates (repeat0 only;
others are repeatability, not extra observations). Tie follows fixed preset order.
Likewise select SDK Harmonic/Monophonic only when every development cell is available.
Unavailable or failed groups get no selection. This optimizes one declared diagnostic,
not a quality certification. Store all errors/side effects as well as selected names.
Hash and register the selection receipt BEFORE confirmation is rendered. Do not
retune using confirmation. Report fixed-selection comparisons and full preset curves
separately; posthoc per-cell best is explicitly diagnostic. At unsupported pitches,
there is no SDK quality comparison or victory. Confirmation is a small synthetic
holdout, not source/engine-independent MOS validation.

Plan freezes all source/input/settings/metrology, fresh SDK/vendor binaries and
link dependencies before each stage. Rebuilds or processing/metric changes need a
new plan and full affected rerun. No product PCM/ABI/ID/latency/default change.
CI tests evaluators without proprietary software; actual vendor runs are separate.
Acceptance is faithful measurement and reproducibility, not mandatory acoustic wins.
Next units are measured cheap DSP changes/input-range controls, then separately
validated PV range expansion. Costs/RT deadlines must not be inferred from host startup.

Primary contracts: https://www.reaper.fm/sdk/reascript/reascripthelp.html ;
https://www.reaper.fm/purchase.php . Actual capability is established by this build,
not inferred from documentation. Original vendor archives are already privately backed up.
