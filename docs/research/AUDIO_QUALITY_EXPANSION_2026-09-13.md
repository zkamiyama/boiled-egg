# Expanded objective audio-quality evaluation — 2026-09-13 JST

## Scope and delivery status

Added five synthetic diagnostic families and new temporal/oversampled-peak measurements on the supplied held-out corpus. No DSP, product ABI, adapters or main branch changed. No perceptual score or promotion decision is asserted.

Committed: `audio_quality_metrics.py` at `72f28e55c3dd62daf39a30277b206f44c5725b21`, and eight standalone calibration tests at `4aa671f30217fc119852c6796f6890819acf316d`.

**The GitHub tool blocked creation of `eval_audio_quality.py`.** The locally executed harness, fourteen additional tests, proposed CI workflow and follow-up scripts are delivered in the accompanying source/patch bundle; they are NOT claimed to be committed or activated in CI. The complete local test suite passed. A documentation-only indentation difference inside the local metric helper's three docstrings is included in the patch so that its bytes match the recorded analysis hash.

Base branch at session start: `5a69f4618f61fdbd017b39deb42aecf1ea94da8e`. The 158 inherited tracked source files matched the previously validated `dc153c3` archive; the intervening `5a69f46` change was documentation only. Every C++ DSP file remained unchanged. The local evaluation records its base Git revision plus independent analysis-file and renderer hashes, rather than pretending the uncommitted harness belongs to that Git commit.

## Execution matrix and integrity

| Experiment | Renders |
|---|---:|
| Five synthetic families, 11 fixtures, 48/96 kHz, 6 shifts plus unity | 1,050 |
| Exact held-out grid: 20 sources x 6 shifts x 5 profiles, Harmonic | 600 |
| Measured target ratios: 60 conditions x 5 profiles, Harmonic | 300 |
| Derived-Elastique baseline at those 60 measured ratios | 60 |
| Independent stereo follow-up: 3 seeds x 6 shifts x 2 rates x 5 profiles | 180 |
| Attack frame-phase sweep: 6 shifts x 2 rates x 5 profiles | 60 |
| **Total objective renders** | **2,250** |

The main run is 2,010 renders; the two follow-ups add 240. Calibration/pilot renders are not added to this total. Every render was checked for finite samples, sample rate, channels and exact frame count. Raw audio was neither normalized nor limited. Synthetic oracle level normalization affects fixture construction only, not renderer output.

Shifts are -12, -7, -3, +3, +7, +12 semitones, with unity reported separately. Block size is 64. PV profiles explicitly scale FFT/hop with rate: General 2048/256 at 48 kHz, 4096/512 at 96 kHz; Transient/Fuzzy modes 1024/256 and 2048/512 respectively. **Multi-resolution retains its existing fixed 1024/256 + 512/192 configuration at both rates.** Thus the 96-kHz comparison tests these actual configurations, not equal window duration across all algorithms.

All 20 held-out references are mono, 44.1 kHz. The 88 training references are not pooled in. The 240 processed files are inventoried; only the 60 in-target Elastique ratios become derived baselines. This baseline is supplied TSM plus Fourier resampling, NOT native Elastique pitch output. MOS values are not assigned to new audio. Exact and measured-ratio grids remain separate.

All **900 newly rendered corpus DSP WAV hashes match the previous corpus**, despite block64 versus block256. The 60 newly written derived WAV file hashes differ from the previous record, although all maximum sample peaks agree. The previous raw derived WAVs were unavailable for a sample-by-sample comparison, so byte equivalence is not claimed for those 60 files.

## Metric definitions and controls

1. **Attack width and timing:** known 2-ms sin-squared gates on a four-tone carrier. Width is the interval containing 5-95% of local energy; report excess over an analytically shifted carrier with unchanged gate. Separately report energy centroid timing and energy outside the gate after centering. Scheduled-onset pre-energy is not automatically called pre-echo. The follow-up uses eight events spanning eight phase positions relative to the 48-kHz 256-sample hop.
2. **Partial-envelope fidelity:** harmonic and inharmonic steady oscillator banks. Compare normalized energy within +/-4 Hz of known shifted partials against an analytic oracle; report log-power RMSE. Also report the energy outside the union of those bands in dB. That energy includes frequency error and sidebands; it is NOT a pure distortion-SNR measurement.
3. **Noise texture:** stationary band noise with three seeds; measure in-band Welch power flatness, maximum absolute autocorrelation at 2-40 ms, and 10-ms RMS coefficient of variation. Compare with same-band Gaussian controls, not an impossible zero-modulation reference. Flatness alone is not an audio-quality score.
4. **Stereo image:** stationary noise with correlation 0, 0.7 or -1; report correlation, magnitude-squared coherence and level-difference errors against a matched statistical oracle. The independent follow-up repeats correlation0.7 with three new seeds. These are synthetic Formant-Off tests, not real stereo-music listening results.
5. **Formant shape:** two synthetic 120-Hz harmonic sources with fixed-Hz resonant envelopes, evaluated against resynthesized shifted harmonics retaining that envelope. Compare Off/Harmonic/Monophonic separately. These are not human voices or direct estimates of F1/F2 locations.

The natural-corpus diagnostics use normalized channel-power envelopes without waveform matching or time warping: 10-ms RMS shape error and 1-ms-bin energy-transport distance. The latter is distribution displacement, not a claim of a uniform playback delay. A fourfold Kaiser FIR oversampling peak estimate is also recorded; it is NOT a BS.1770-compliant true-peak meter.

Steady metrics crop 250 ms at both ends. Attack/corpus metrics do not align away timing errors. Analysis is float64, never an antiphase-canceling downmix. Log floor is -120 dB relative power; missing/silent signals are invalid, not excellent scores. Temporal active bins use a source-relative -40 dB threshold. No threshold was tuned to make an algorithm win.

## Main findings at 48 kHz

Means over the six nonunity shifts. Attack values below use the additional eight-frame-phase sweep; partial values average the harmonic and inharmonic fixtures. Lower is better for both columns.

| Profile | Excess 5-95% attack width, ms | Partial-envelope error, dB | Off-partial energy, dB |
|---|---:|---:|---:|
| General | 8.210765 | 0.010517 | -48.275465 |
| Transient | 3.534645 | 5.173255 | -21.136626 |
| Multi-resolution | 3.778633 | 5.170022 | -21.120252 |
| Fuzzy-noise | 3.534897 | 5.103227 | -20.549825 |
| Fuzzy | 3.489511 | 5.103479 | -20.534079 |

General has a strong steady-partial advantage on these fixtures but substantially smears the narrow attacks. Fuzzy and Transient are very similar on attack width. The existing natural-audio onset result does not imply that Multi-resolution must win on every synthetic attack fixture.

**Timing is a separate issue:** at 48 kHz, Fuzzy's attack centroid shifts +10.689 ms at -12 st and -5.312 ms at +12 st in the eight-phase sweep. General reaches +21.352 and -10.645 ms. Total output duration remains exact. The single-PV timing pattern approximately follows FFT/(2*sample_rate)*(1/pitch_ratio-1); this is an empirical diagnostic, not a proved root-cause analysis or a DSP fix.

### Stereo follow-up, three independent seeds

18 conditions per rate/profile (3 seeds x 6 shifts), Formant Off, target correlation approximately 0.7. Values are absolute errors against the matched oracle; lower is better.

| Profile | 48-kHz correlation error | 48-kHz coherence error | 96-kHz correlation error |
|---|---:|---:|---:|
| General | 0.523714 | 0.318020 | 0.564925 |
| Transient | 0.628229 | 0.414789 | 0.637149 |
| Multi-resolution | 0.649682 | 0.420197 | 0.643174 |
| Fuzzy-noise | 0.039433 | 0.055348 | 0.037050 |
| Fuzzy | 0.039417 | 0.055336 | 0.037045 |

Fuzzy beats Multi-resolution on correlation error in 18/18 conditions at each rate, about 94% lower mean error on this fixture. This is a clear synthetic-stereo advantage but does not establish universal perceptual superiority. Both Fuzzy modes show nearly the same result; causal attribution to any one component still requires an ablation.

### Noise and formants

At 48 kHz, Fuzzy/Transient flatness is 0.988694/0.988705 versus Gaussian control0.992391. Their lag peaks are 0.044158/0.043951 and RMS CVs 0.070689/0.070907, versus control CV0.070478. There is no material demonstrated Fuzzy advantage on these stationary-noise metrics.

Fuzzy's synthetic fixed-formant error changes from Off15.729607 dB to Harmonic8.221902 and Monophonic8.486799 dB. Harmonic helps strongly versus Off, but Transient/Multi-resolution give 8.208626/8.209980 dB: Fuzzy is not better here. This is a new oracle-based measure, not directly comparable to previous broad cepstral-error values.

## Natural held-out corpus

Exact 120 conditions per profile, Harmonic. Mean 10-ms normalized RMS shape errors: General2.807713 dB; Transient1.849871; Multi-resolution1.827970; Fuzzy-noise1.849729; Fuzzy1.850766.

Paired source-cluster bootstrap, 4,000 draws with all six pitches kept within each of 20 resampled sources: Multi-resolution minus Transient is **-0.021901 dB**, descriptive95% interval **[-0.049896,-0.005039]**. Fuzzy minus Transient is **+0.000895 dB**, interval **[-0.021267,+0.018212]**. The small first difference is not automatically audible; no multiplicity adjustment or perceptual significance claim is made.

On the separate measured-ratio60 set, shape errors are Multi-resolution1.571456, Transient1.592323, Fuzzy1.588248 and derived-Elastique1.633150 dB. These source-relative temporal diagnostics do not provide a ground-truth native pitch-shift ranking.

## 96-kHz configuration warning

The fixed-window Multi-resolution configuration has partial-envelope error **11.511106 dB** and fixed-formant Harmonic error **31.290965 dB**, versus Fuzzy5.080898 and10.630540 dB. Its sharper attacks do not compensate for those tonal/formant failures. The configuration needs separate rate-scaling work before it is treated as broadly qualified at96 kHz. No configuration was silently changed to conceal this result.

## Software validation and limits

GCC14.2 C++20 Release build: **9/9 CTests**. Final research Python suite: **161/161**; legacy dataset suite: **6/6**; no skips. The22 added tests include eight standalone calibrations plus fourteen fixture/integration tests. Controls detect a known10-ms delay, 20% injected pre-energy, missing/detuned partials, noise looping/pumping and stereo collapse; gain and phase changes alone do not masquerade as partial-envelope defects.

No C++ DSP changed, so this session does not claim fresh multi-compiler/sanitizer/host/CPU qualification. Local correctness success means the experiment ran correctly, not that2,250 cases passed a perceptual-quality threshold. No human listening was performed.

Welch and coherence definitions are documented in the official SciPy references:
- https://docs.scipy.org/doc/scipy/reference/generated/scipy.signal.welch.html
- https://docs.scipy.org/doc/scipy/reference/generated/scipy.signal.coherence.html

The accompanying bundle contains the exact measured source overlay, apply-checkable Git patch, full CSV/JSON, raw logs, independent-seed/frame-phase follow-ups and checksums. User dataset audio/MOS and generated render audio are not redistributed in that bundle.
