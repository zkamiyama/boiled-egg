# Independent CPU, compact-latency and zplane recheck — 2026-09-13 JST

## Scope and provenance

The resumed session found the requested work already committed through `41c93d6ab560cb342d8b82f4a77d5bbe3ca9dd99`. It did not overwrite that work or claim its fixes as new. This follow-up independently rebuilds the runtime, reproduces the old scheduling failure, reruns the audio comparison and repeats CPU diagnostics. Its new artifact is the standalone reproducer at `de3557914ea94b487a8b45ec674dae4f08536cb4`, plus this report. No production or research DSP arithmetic, host defaults, plugin IDs/state, or main was changed in this follow-up.

Runtime source: `8401ddaa28b939b58b362bcd2f9c09072210841c`, downloaded in CI artifact **10317680790**, run **34755222030**. All **222 tracked-file SHA256 values** and ZIP CRC passed. The later 41c93 commit is documentation-only. GCC14.2/C++20 Release was rebuilt locally from this source; the manifests record executable and analysis hashes. The older reproduction library was rebuilt from the prior exact `0321326e` archive.

The prior report's 384,000 probe iterations are NOT pooled with the new **288,000** iterations here. The primary audio recheck contains **800 candidate renders / 960 measurement rows**; the Formant-Off pitch control adds **300 candidate renders / 360 rows**. Repeated baselines are not extra independent source material. Synthetic gate renders are separate.

## 1. Confirmed deterministic scheduling defect

The same `research/experiments/reproduce_host_work_budget.cpp` was compiled against old and fixed static libraries. It uses the legacy fixed-delay creator, so delay compaction is not a confound. Input is deterministic alternating silence/noise with formant events, 96kHz, eight channels, Monophonic, static pitch0.5, block31.

| Profile | Old runtime | Fixed runtime |
|---|---|---|
| General | status6, frame_overruns1, failing block starts at input3069 | success beyond50,000 input frames, overruns0 |
| Fuzzy | success, overruns0 | success, overruns0 |
| Multi-resolution | success, overruns0 | success, overruns0 |

The reported position is the first index of the failing31-frame call, not an exact failure sample inside the call. General's old budget was20 coroutine steps/input, or10,240 per512-sample hop. The fixed run observes a frame needing10,448 steps and provides21/input. The inherited conservative work bound fixes this reproducible defect. This is separate from rare two-channel CPU-time spikes and does not establish eight-channel realtime capacity.

## 2. Fresh CPU-tail evidence

Same-machine sequential probes, CPU0 affinity, 96kHz stereo, block32, static+7st, four formant events/callback. No compilation, corpus rendering or tests overlapped these probes. Measurement storage is allocated before timing; CSV output is after timing. Three24,000-call repetitions rotate normal Fuzzy, normal Multi-resolution and fixed-count integer controls. First3,000 calls of each run remain in the cold-start data; each steady portion has21,000 calls. The deadline is333.333us.

| Steady workload | Calls | CPU p99 range across3 repeats | Maximum CPU | CPU deadline misses |
|---|---:|---:|---:|---:|
| Fuzzy | 63,000 | 140.61–142.63us | 2,795.55us | 22 |
| Multi-resolution | 63,000 | 108.37–138.63us | 7,032.54us | 44 |
| Fixed80,000 integer recurrences, no DSP call | 63,000 | 138.84–146.24us | 3,810.28us | 61 |

The integer control has a median around86.78us and does exactly the same number of operations on every iteration. Its worst recorded sample has CPU3,810.278us and wall3,808.406us, with no fault, guest context switch or migration. Therefore DSP-specific variable work cannot be the only explanation for this environment's tails. This does NOT uniquely identify the physical cause of any one audio outlier.

Across repeated normal-audio runs, the per-call completed-frame schedule and output-energy sequences are identical. Deadline-miss callback indices overlap in **zero** pairs of repetitions for each profile. Steady normal runs have no page faults or migrations; only1/66 normal-audio CPU misses has a recorded guest context switch. The visible cgroup throttle counter does not increase in any of the15 probe runs.

The guest identifies as KVM on an AMD EPYC9V74. CPU0's cumulative steal-time counter increases2–6 USER_HZ ticks across each primary run. This is evidence of virtual-machine CPU interference somewhere in the run, not callback-level attribution. It cannot explain the exact accounting of a particular CPU-clock spike. Hardware cycles and software task-clock perf_event_open attempts both return EACCES, so retired-work/frequency/host-scheduling attribution cannot be completed from this guest.

Six additional12,000-call controls retain no-op, silence, tiny input, tiny+FTZ/DAZ, normal input without resource counters, and fixed integer work without resource counters. Tiny-input p99 decreases81.17→57.66us with FTZ/DAZ, but outliers persist. Normal input without resource-counter instrumentation still reaches2,987.91us. Denormals or getrusage instrumentation are therefore not sufficient explanations for ordinary tails. No global SDK floating-point mode was changed.

**Conclusion:** a deterministic work-budget bug is confirmed and fixed; an environment-wide tail component is also demonstrated. The remaining physical/virtualization/accounting mechanism is unresolved. Hard-realtime safety is not established. Raw maxima, cold starts and all misses remain in the delivery.

## 3. Compact fixed delay independently queried and tested

Existing `boiledegg_research_host_create()` preserves its original delay. `boiledegg_research_host_create_compact()` explicitly opts into the shorter bound; `boiledegg_research_host_compact_latency()` predicts it. Actual queried handle delays agree with the bound. This is an upper bound on sample availability conditional on zero scheduler overruns, not a proof of minimum possible latency or CPU execution time.

| Fuzzy/Transient | Pitch | Legacy | Compact | Reduction |
|---|---:|---:|---:|---:|
| 48kHz | -12st | 56.000ms | 44.000ms | 21.43% |
| 48kHz | 0st | 56.000ms | 32.667ms | 41.67% |
| 48kHz | +12st | 56.000ms | 27.333ms | 51.19% |
| 96kHz | -12st | 54.667ms | 43.333ms | 20.73% |
| 96kHz | 0st | 54.667ms | 32.333ms | 40.85% |
| 96kHz | +12st | 54.667ms | 27.000ms | 50.61% |

The reexecuted tests include1,936 service-bound models,90 compact delayed-waveform/event cases and210 actual corner configurations. All pass. The compact bridge still requires time1 and fixed pitch[0.5,2]. Its formant target is frame-latched with10ms smoothing. **The previously delivered Formant Lab plugins still use legacy creation; their reported delay has not silently changed.** Device/DAW buffering is additional.

## 4. Objective comparison against the supplied Elastique recordings

The20 supplied mono44.1kHz references and240 processed files remain exact matches to the catalog. Eighty processed recordings are labeled Elastique, but the CSV supplies no SDK version or mode. The main comparison regenerates all five candidates: General, Transient, Multi-resolution, Fuzzy-noise and Fuzzy. It does not select a different winning mode per file.

Primary results use60 conditions:20 sources with three measured output/input ratios each, approximately0.512583–1.974375. The other20 conditions at2.010902–3.928655 are stress only. This is not the exact±3/7/12 semitone grid.

For direct TSM, candidates use pitch1, Formant Off and the provided recording's measured duration ratio. The baseline is that recording itself. For derived pitch, the baseline is that recording plus exact-length Fourier resampling; it is not native zplane pitch output. A separate Formant-Off control removes the preservation mismatch from the temporal comparison. Scheduled fixed-delay processing supports time1 only; TSM comparison uses the separate immediate path.

Metrics use prescribed constant-rate feature-time mapping, not fitted delay/DTW. They are source-relative engineering descriptors, not calibrated perceptual scores. Confidence intervals resample20 sources with all three ratios retained,4,000 draws; no multiplicity correction or new-render MOS is claimed.

### Direct TSM: primary60 conditions

| System | Broad envelope RMSE dB, lower | Onset correlation, higher | RMS shape dB, lower | Log-spectral distance dB, lower |
|---|---:|---:|---:|---:|
| Provided Elastique | 2.1041 | 0.6803 | 1.8724 | 6.3154 |
| General | 2.9316 | 0.7111 | 1.3776 | 7.0737 |
| Transient | 2.1319 | 0.7249 | 1.3190 | 6.4089 |
| Multi-resolution | 2.1373 | 0.7237 | 1.3212 | 6.4982 |
| Fuzzy-noise | 2.1363 | 0.7253 | 1.3196 | 6.4067 |
| Fuzzy | 2.1363 | 0.7265 | 1.3208 | 6.4115 |

Fuzzy's onset improvement is+0.046262,48/60 wins, descriptive95% interval[+0.026699,+0.068321]. RMS-shape change is-0.551686dB,57/60 wins, interval[-0.716282,-0.404319]. Broad-envelope error is+0.032208dB worse on average and log-spectral distance+0.096061dB worse; both difference intervals cross0. Chroma correlation improves0.954229→0.963223,42/60 wins, but is not a cents-level pitch-error measure.

A supplementary paired CSV counts directional outcomes without combining scores. Fuzzy improves both temporal descriptors in47/60 conditions, and all four displayed metrics in27/60. These are descriptive conjunctions, not a newly calibrated overall-quality gate. For example, Ocarina_02 at ratio1.293373 improves onset correlation but worsens log-spectral distance by3.096402dB. Blanket sonic superiority would conceal important counterexamples.

### Derived pitch: Formant Off on the candidate, temporal comparison only

| System | Onset correlation | Wins/60 | RMS shape dB | Wins/60 |
|---|---:|---:|---:|---:|
| Derived Elastique | 0.8403 | — | 1.6332 | — |
| Transient | 0.8920 | 52 | 0.7028 | 59 |
| Multi-resolution | 0.8943 | 52 | 0.7031 | 59 |
| Fuzzy | 0.8922 | 54 | 0.7260 | 59 |

Fuzzy's onset delta is+0.051865, interval[+0.035881,+0.069674]; RMS-shape delta-0.907150dB, interval[-1.170096,-0.671317]. The temporal advantage survives removal of formant preservation, but this remains a derived-baseline result.

With Harmonic preservation, Fuzzy's broad-envelope error is4.7874 versus derived7.0745dB,59/60 wins. That comparison includes a preservation-feature mismatch and is NOT a claim of beating native formant-preserving ELASTIQUE PRO. Current public PRO specifications include mono/polyphonic formant-preserving pitch shifting.

All candidate output frame counts match their requested lengths. TSM baseline duration error is zero by construction because its observed length sets the target; this does not demonstrate a duration-accuracy victory. Likewise, the synthetic270-case gate's maximum2.153085-cent error characterizes boiled egg only: matching zplane synthetic tone output was not supplied, so a cents-level comparative victory cannot be calculated.

Stress peaks and limitations from the main comparison remain in the CSV, not pooled into primary means. No limiter/normalizer, native-pitch benchmark, human listening or MOS prediction was added.

## 5. Validation and delivery

Fresh local GCC14.2/C++20 CTest: **21/21**. Fresh research Python: **195/195**, legacy Python: **6/6**, no test skips. Fresh scheduled low-tone/high-band gate: **270/270**, unchanged thresholds. The standalone identical-source old/fixed reproducer was compiled and executed against both runtime libraries.

CI run34755222030 at8401ddaa was explicitly read: all four jobs passed, including Python3.11/3.13, the3.13 scheduled gate, loaded CLAP/VST3 modules and mailbox TSan. New changes are a standalone diagnostic and documentation, not new DSP or plugin behavior. Prior multi-compiler/sanitizer evidence remains in the preceding report; it is not relabeled as a fresh local matrix.

A first probe-runner attempt stopped before measurements because this guest lacks `/proc/pressure/cpu`; the runner now records unavailable optional counters. A first long tonal invocation reached the tool execution-time limit without publishing a result; the complete rerun produced270 cases and zero failures. Both logs are retained rather than treated as quality failures or discarded evidence.

Delivery includes the exact source archive, new reproducer, execution commands, comparison/control CSV+JSON,288,000 raw diagnostic rows, per-run OS snapshots, repeat-invariance checks, fixed-delay queries and test logs. No user corpus audio or MOS file is redistributed in the bundle.

Evidence SHA256:

- Main measurements: `684e123428bc0e81c47599cd9de32a5234c3ddcffb4ff67f5be45b3a646506ef`
- Formant-Off control measurements: `4a803552c2f2f34445429c50914bce1457ba6220eede05d22d10983396b6d69a`
- Fresh probe summary: `4c186694692b0c9aa4dc0d40ff9efdfde60a008ef23628c6cf11bb3eb2fa976a`
- Scheduled tonal gate: `2f896a647caedb5f6874f373e0baf75663d6e5e0aa390709c256e7dff4627de4`

Official definitions checked2026-09-13:

- https://man7.org/linux/man-pages/man2/getrusage.2.html
- https://man7.org/linux/man-pages/man3/clock_gettime.3.html
- https://man7.org/linux/man-pages/man5/proc_stat.5.html
- https://docs.kernel.org/admin-guide/cgroup-v2.html
- https://man7.org/linux/man-pages/man2/perf_event_open.2.html
- https://licensing.zplane.de/technology
