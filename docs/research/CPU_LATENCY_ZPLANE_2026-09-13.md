# CPU tails, compact latency and supplied-zplane comparisons — 2026-09-13 JST

## Conclusions and limits

A deterministic eight-channel scheduling-budget defect was found and fixed. Rare elapsed/CPU-time spikes also occur in a fixed-count integer loop with no DSP; the observed audio spikes cannot be attributed solely to variable DSP work. Guest measurements do not identify the ultimate host/CPU cause, and they cannot retrospectively explain every previously reported outlier. **Hard-realtime qualification remains open.**

A new opt-in, pitch-aware fixed-delay API reduces the Fuzzy/Transient unity-pitch delay from 56 to 32.667 ms at 48 kHz and from 54.667 to 32.333 ms at 96 kHz. Legacy creation, existing research plugins, product ABI/adapters/state and main remain unchanged. This is not a new low-latency plugin release.

Against the supplied Elastique TSM recordings, temporal descriptors improve, but average broad-envelope and log-spectral error do not establish an overall advantage. Derived-pitch temporal improvements survive a Formant-Off control. **These recordings are not a current native zplane pitch-shifter benchmark; no perceptual superiority percentage or new MOS score is justified.**

## Implementation and provenance

Initial branch HEAD was `699dd3c8dad4fd9e30b0240a09c83c51280a5270`. Its runtime matched the previous exact `e5a166bb` archive; 699 adds documentation. Work stayed on `research/formant-v0.3-integrated`.

| Commit | Change |
|---|---|
| `81f070b2` | Per-call CPU/wall/resource-counter probe and independent work controls |
| `6370755d` | Conservative coroutine work bound, compact-latency API and tests |
| `77b6a278` | Direct TSM / derived-pitch comparison, calibration tests and supplied-label association |
| `d7905f6a` | Portable tail summaries retaining cold starts and raw outliers |
| `d25a1367` | Formant-Off temporal control and three additional tests |
| `8401ddaa` | Isolated overlap-guard budget compatibility |

CI artifact 10317350487 from run 34754727356 was downloaded and its archive plus all 220 tracked-file hashes verified. All executable/analysis files matched the local files; the previous documentation-only report was restored from the archive. With the two subsequent control files, the local tree exactly matched `d25a1367` tree `6a87e9010a96158fa86719cc55130c309e70c06e`. The later isolated patch does not alter the ordinary runtime.

The main comparison was generated before the scheduler budget adjustment. Its actual renderer hashes are retained. Replaying all 800 candidate outputs with the final normal runtime reproduced **800/800 complete WAV files byte-for-byte**. The 300 additional Formant-Off renders use the final runtime. No earlier measurement is relabeled with a later executable hash.

## CPU-tail investigation

`rt_tail_probe.cpp` measures CLOCK_THREAD_CPUTIME_ID and CLOCK_MONOTONIC_RAW around each processing call. Optional RUSAGE_THREAD counters and CPU IDs bracket the call outside the timed region. Measurement vectors are allocated/touched before timing and CSV output occurs afterward. Captured counters include minor/major faults, voluntary/involuntary guest switches, migration, completed frames and maximum coroutine-step counts. Their OS meanings are documented in [1–3].

The 384,000 diagnostic iterations comprise audio, silence, tiny/decaying signals, empty-call and constant-work controls. Normal audio uses 96 kHz, stereo, block32, static +7 st, four formant targets per callback, scheduled SIMD, CPU0 affinity. Three 24,000-call repetitions retain the first second separately as cold start; each has 21,000 steady calls. The steady deadline is 333.333 microseconds. These runs use the legacy fixed-delay bridge, not the compact delay.

| Steady workload | Calls | CPU p99 across repeats | Maximum CPU | CPU deadline misses |
|---|---:|---:|---:|---:|
| Fuzzy, normal audio | 63,000 | 139.88–143.48 us | 1,533.08 us | 41 |
| Multi-resolution, normal audio | 63,000 | 109.65–161.22 us | 4,660.89 us | 56 |
| Fixed 80,000 integer recurrences, no DSP | 63,000 | 145.05–157.94 us | 3,136.84 us | 127 |

The fixed-work median is about 86.8 us, yet its maximum has CPU 3,136.835 us and wall 3,136.346 us, with no page fault or recorded guest switch. Its loop count and operations do not depend on audio or data. This rules out **DSP-specific variable work as the only explanation** of the measurement environment's tails; it does not prove which hypervisor, CPU-frequency, cache or accounting mechanism caused each audio outlier.

Normal steady runs have zero page faults and CPU migrations. The visible cgroup throttling counters did not increase during those runs. Most misses have no recorded guest switch; some do. The indices of missed callbacks have zero overlap between any two repeated identical-input runs for each profile. Removing resource-counter instrumentation still leaves outliers, up to 1,864.5 us in the Fuzzy repetitions. Empty-call controls have sub-microsecond ordinary overhead but also occasional timing-bracket outliers.

The guest exposes a virtualized AMD EPYC environment. Hardware and software perf-event attempts are unavailable (the final capture returned EACCES). Guest counters cannot exclude unobserved ancestor throttling or host scheduling. Consequently neither “all DSP bugs” nor “proven host noise” is an acceptable blanket explanation. Controlled physical-machine tracing is needed to finish attribution of the rare tails.

Artificial tiny input with FTZ/DAZ enabled reduced one p99 measurement from about 83.68 to 57.50 us. Normal-signal tails and integer-control tails persist, so denormals do not explain the ordinary spikes. **No SDK-wide FPU-mode change was made.** The probe restores its own mode and reports this only as a diagnostic ablation.

### Separate deterministic work-budget bug

At 96 kHz, General, eight channels, Monophonic, pitch0.5, the expanded runtime test failed at input position3069 before either fixed-delay prefix finished: frame_overrun1, output underrun0, last completed frame8886 coroutine steps, nominal budget20 steps/input. A later, more expensive frame could not finish within the nominal hop.

`frame_step_bound()` now counts a conservative upper bound on FFT work, per-channel loops, monophonic scanning, Fuzzy initialization and state copies. The constructor takes the maximum of the old budget and ceil(bound/hop). No FFT, phase or amplitude arithmetic is changed. This fixes the deterministic corner, **not the unexplained two-channel timing spikes**. Functional eight-channel tests are not eight-channel CPU-capacity guarantees.

## Compact fixed delay

New C entry points:

- `boiledegg_research_host_compact_latency(config)` queries the bound.
- `boiledegg_research_host_create_compact(config,result)` selects it explicitly.

Existing `create()` keeps its previous delay; the C struct layouts are unchanged. Existing Formant Lab plugins still call legacy creation and therefore do not automatically acquire the shorter delay. Static pitch is in[0.5,2], time=1; changing these during processing is still unsupported. Formant automation remains frame-latched with 10-ms smoothing. The table is DSP-bridge delay, excluding device/DAW buffering.

For a child FFT size N, hop H and pitch p, the conservative sample-availability bound is

`ceil(N/2 + 2H + (N/2 + 24)/p + 2)`.

It is rounded upward to32 samples. Multi-resolution uses the maximum child bound plus FIR half-length and pairing allowance. With zero algorithmic frame overruns, frame k completes by input time N/2+(k+1)H; its safe synthesis position is round(kHp). Cleanup capacity8/tick exceeds the maximum production slope2, and resampling capacity2/tick exceeds the output slope1. Crop, right support and rounding yield the expression. This is not the lowest observed latency fitted to the test signals and not a CPU-time upper bound.

| Fuzzy / Transient | Pitch | Old delay | Compact delay | Reduction |
|---|---:|---:|---:|---:|
| 48 kHz | -12 st | 56.000 ms | 44.000 ms | 21.43% |
| 48 kHz | 0 st | 56.000 ms | 32.667 ms | 41.67% |
| 48 kHz | +12 st | 56.000 ms | 27.333 ms | 51.19% |
| 96 kHz | -12 st | 54.667 ms | 43.333 ms | 20.73% |
| 96 kHz | 0 st | 54.667 ms | 32.333 ms | 40.85% |
| 96 kHz | +12 st | 54.667 ms | 27.000 ms | 50.61% |

Validation comprises 1,936 worst-service/burst models, 90 independent delayed-waveform/automation comparisons, and 210 actual configurations with odd31-sample blocks, 48/96/192 kHz, all five profiles,1/8 channels, seven pitches including nonintegers, alternating formant policies and noise/silence. All pass with zero algorithmic underruns. This is not full-range rate/channel audio-quality certification.

## zplane comparison protocol

Exact supplied inputs:20 mono44.1-kHz references,240 processed files,5,520 score rows. Eighty recordings are labeled Elastique. Their observed output/input length ratios are used directly, not guessed from filename percentages:60 target conditions in0.512583–1.974375,20 separate stress conditions in2.010902–3.928655. Every profile is reported; no per-file winning-profile selector is used.

For **time stretching**, the reference is rendered at the provided file's observed duration ratio with pitch1 and Formant Off. The baseline is the provided Elastique TSM recording itself. For **derived pitch**, time1 and the observed pitch ratio are used, with Harmonic preservation; the baseline is provided TSM followed by exact-length Fourier resampling. The CSV does not identify its zplane SDK version or processing mode. It is not evidence of performance against the latest SDK/native pitch shifter.

Main evaluation:80 conditions x2 operations x(5 candidates+baseline)=960 measurement rows, including800 newly rendered candidate WAVs. Additional no-preservation control:60 x(5 candidates+baseline)=360 rows,300 candidate renders. The800 exact-replay renders are validation, not additional independent quality cases. All candidate renders are finite and have exact expected frames, rates and channels; observed frame errors are0. TSM target length was chosen from the baseline, so the baseline's duration error0 is definitional, not an independent timing-accuracy win.

TSM features use a uniform normalized time axis, as specified by constant time scaling; there is no fitted delay, DTW or waveform alignment. Reported metrics are cepstral broad-envelope error, onset correlation,10-ms normalized power-envelope shape error, normalized log-spectral distance, spectral convergence and chroma correlation. The spectral log floor is -80 dB relative amplitude with source-active frames above -40 dB RMS. Pitch measurements do not compare unchanged chroma or waveform phase to an intentionally shifted signal.

Paired intervals are descriptive95% percentile intervals from4,000 source-cluster bootstrap draws, retaining all three target ratios within each of20 resampled sources. They are not multiplicity-corrected significance statements or listener populations. A lower diagnostic is not automatically perceptually better. Original and generated signals are not normalized or limited during rendering.

### Direct time stretching: all60 target conditions

| System | Envelope error dB (lower) | Onset correlation (higher) | RMS shape dB (lower) | Log-spectral distance dB (lower) |
|---|---:|---:|---:|---:|
| Provided Elastique | 2.1041 | 0.6803 | 1.8724 | 6.3154 |
| General | 2.9316 | 0.7111 | 1.3776 | 7.0737 |
| Transient | 2.1319 | 0.7249 | 1.3190 | 6.4089 |
| Multi-resolution | 2.1373 | 0.7237 | 1.3212 | 6.4982 |
| Fuzzy-noise | 2.1363 | 0.7253 | 1.3196 | 6.4067 |
| Fuzzy | 2.1363 | 0.7265 | 1.3208 | 6.4115 |

Fuzzy versus provided Elastique: onset delta+0.046262,48/60 wins, interval[+0.026699,+0.068321]; RMS-shape delta-0.551686 dB,57/60 wins, interval[-0.716282,-0.404319]. Its mean envelope error is+0.032208 dB worse and log-spectral distance+0.096061 dB worse, both intervals crossing0. This supports a temporal-feature advantage in this set, **not overall timbral or perceptual superiority**.

General has the best average spectral convergence among these candidates (0.1754 versus provided0.2419) but worse log-spectral distance. Metric definitions and signal characteristics matter; the data do not justify combining them into a marketing score.

### Derived pitch and preservation fairness

With Harmonic preservation, Multi-resolution has envelope4.7903 versus baseline7.0745 dB (59/60 wins), onset0.9010 versus0.8403 (51/60), and RMS shape0.7890 versus1.6332 dB (59/60). Fuzzy is4.7874/0.8964/0.7987 respectively. **The envelope comparison includes a feature mismatch:** the derived baseline is not verified to preserve formants while the candidates do. The public PRO specification supports formant-preserving native pitch [4]; these numbers cannot be substituted for that test.

Therefore a separate **Formant Off** control evaluates temporal metrics only; it deliberately does not score an unshifted spectral envelope as the ideal for intentionally shifted timbre.

| System, preservation off | Onset correlation | Wins/60 | RMS shape dB | Wins/60 |
|---|---:|---:|---:|---:|
| Derived baseline | 0.8403 | — | 1.6332 | — |
| Transient | 0.8920 | 52 | 0.7028 | 59 |
| Multi-resolution | 0.8943 | 52 | 0.7031 | 59 |
| Fuzzy | 0.8922 | 54 | 0.7260 | 59 |

Fuzzy Off onset delta is+0.051865, interval[+0.035881,+0.069674]; RMS-shape delta-0.907150 dB, interval[-1.170096,-0.671317]. Thus the temporal improvement is not solely an artifact of enabling formant preservation. It remains a derived-baseline result, not native pitch parity.

### Descriptor versus provided subjective labels

A separate check uses only the original240 supplied MOS labels for the original240 recordings, with no new-render labels and no fitted model. Spearman associations across the three methods are onset+0.4622, RMS shape-0.2295, broad-envelope error-0.2842 and log-spectral distance-0.2918. Within the80 Elastique recordings, onset is+0.7404. Methods/ratios are confounded; these are not independent predictive validation. The dataset paper also warns about objective/perceptual correspondence [5]. Do not translate a29.5% reduction in the numeric dB-error value into “29.5% better sound.”

### Negative evidence retained

Beyond the target range, maximum raw sample peaks remain severe: Multi-resolution32.2506 for time stretching and18.8422 for derived pitch; Fuzzy8.0239 and8.6630. These stress rows are not pooled into the60-condition target averages. Target maxima also exceed unity in floating point (e.g. Fuzzy TSM1.5947). No limiter or output normalization was added. The isolated overlap-guard is still not enabled or promoted in the evaluated runtime.

## Tests, CI and retained failures

GCC14.2 C++20/23 and Clang17 C++20/23 each pass21/21 CTests. A clean matched-Clang C/C++ ASan+UBSan build passes21/21 with leak detection. An earlier sanitizer link attempt mixed C and C++ runtimes and failed before tests; that log is retained. Final Python research tests pass195/195, legacy6/6, no test skips. The scheduled tonal/high-band gate passes270/270 with unchanged3-cent/22-dB/0.25-dB thresholds. Worst observed low-tone error is2.153085 cents and high-band p95 ripple0.145946 dB. These pitch numbers characterize boiled egg only; no equivalent zplane synthetic output was supplied.

The dedicated execution/host CI at d790 (run34754727356) passed all four jobs, including Python3.11/3.13, scheduled quality, loaded CLAP/VST3 and mailbox TSan. The artifact was independently verified as above. Later control scripts do not change DSP or adapters. Final CI state is retained with the delivery rather than inferred from an absence of failures.

The expanded210-case test exposed a second budget issue only under the old **50% isolated overlap-guard patch** (run34754727365, job103717069392):48k Multi-resolution8ch, pitch1.999, frame_overrun1. That experiment shortens the actual hop, so its budget must use the shortest guarded stride at maximum allowed pitch2 rather than the nominal hop. The patch now does so; clean local50% and75% builds each pass22/22 without skips or relaxed thresholds. Ordinary runtime and measured outputs are unchanged. The failing log excerpt and original patch are retained.

## Reproduction

```sh
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
cmake -S research/cpp_pv_rt -B build/study -G Ninja -DCMAKE_BUILD_TYPE=Release
cmake --build build/study -j2
ctest --test-dir build/study --output-on-failure
export BOILED_EGG_PV_CLI="$PWD/build/study/boiled_egg_pv_rt_cli"
export BOILED_EGG_MULTIRES_CLI="$PWD/build/study/boiled_egg_multires_rt_cli"
python -m unittest discover -v -s research -p 'test_*.py'
python -m unittest -v eval/test_tsm_dataset.py
# Diagnostic counters are not inserted into the SDK process API.
taskset -c 0 build/study/boiled_egg_rt_tail_probe 2 96000 32 1.4983071 24000 1 normal 0 1 > normal.csv
taskset -c 0 build/study/boiled_egg_rt_tail_probe 2 96000 32 1.4983071 24000 1 control 0 1 > control.csv
python research/summarize_rt_tail_probe.py --csv normal.csv control.csv --output tails.json
python research/compare_zplane_outputs.py --build "$PWD/build/study" \
  --refs data/ref_test --tests data/test --catalog data/TSM_MOS_Scores.csv \
  --workers 2 --output results/zplane
python research/check_pitch_formant_control.py --build "$PWD/build/study" \
  --refs data/ref_test --tests data/test --catalog data/TSM_MOS_Scores.csv \
  --workers 2 --output results/pitch-off-control
```

For compact delay, explicitly call the new C factory and query the returned latency. There is no automatic plugin behavior change. The delivery contains source/patches, all comparison CSVs, raw diagnostic calls, hashes and success/failure logs, but no user audio, MOS catalog, external SDK binaries or newly claimed listener scores.

References checked2026-09-13:
[1] https://man7.org/linux/man-pages/man2/getrusage.2.html
[2] https://man7.org/linux/man-pages/man3/clock_gettime.3.html
[3] https://docs.kernel.org/admin-guide/cgroup-v2.html
[4] https://licensing.zplane.de/technology
[5] https://arxiv.org/abs/2006.00848
