# Sustained spectra, selective windows, native-comparison readiness and CPU clocks — 2026-09-14 JST

## Decision

The frequency-coherence guard is a useful **opt-in sustained-content candidate**, not a default replacement. It substantially improves short-window Fuzzy partial balance and improves all four displayed mean descriptors against the supplied Elastique TSM recordings. It slightly worsens onset correlation with Harmonic preservation on the separate exact-pitch grid. A new SELEBI-inspired offline NSGT experiment reduces synthetic attack spreading; on music its main spectral gain comes from the added phase-coherence ablation, not adaptive windows alone.

**Native zplane pitch comparison and ultimate physical attribution of rare CPU tails remain unresolved.** No native engine ran, no human listening occurred, no new MOS was inferred, and no research backend/plugin was promoted. Product ABI, existing plugins, state and main remain unchanged. Existing compact-delay behavior is retained; this pass does not claim another latency reduction.

## Provenance and implementation

The resumed branch was `c37b5256f33836f6105aad1caad956a778da0859`, which already contained interrupted NSGT, native-contract and coherence-guard work. The guard and its modulo-phase alias correction are inherited from that work, not claimed as new inventions in this follow-up.

The local baseline is the previously downloaded `8401ddaa28b939b58b362bcd2f9c09072210841c` archive: all 222 tracked hashes were verified. A GitHub compare from 8401 to c37 confirms no ordinary C++ runtime files changed. The local guarded tree reconstructs the two isolated guard patches on that baseline. It is **not a byte-for-byte checkout of the complete c37 tree**. The exact measured guarded source, combined patch, build flags and executable hashes are supplied, including the reconstruction script. The isolated repository patches remain unpromoted.

| Commit | Change |
|---|---|
| `ebc66f9b` | Fenced RDTSCP/CPU/wall diagnostic without usable perf counters |
| `6d2c8d50` | Offline selective-window v2 with optional phase-frequency coherence |
| `7334189e` | Paired C++ follow-up, shared input files and four independent oscillator banks |
| `e4ab5dcc` | Six selective-window correctness tests |
| `05e63ce7` | Fixed/adaptive/adaptive-coherent analytical and TSM comparison runner |
| `d1b4c87d` | Four calibration/integrity tests for the follow-up harness |

C++ comparisons record whole-WAV hashes. NSGT synthetic diagnostics use float64 arrays; its corpus outputs are quantized to float32 before metrics and have PCM hashes. Cross-pipeline results are not bit-equivalence claims. The final NSGT runner reproduced all 234 initial synthetic measurement rows byte-for-byte in the CSV; the original measured runner is retained. Repeated runs are not additional independent quality cases.

## Recent research considered

1. Akaishi, Holighaus and Yatabe, **SELEBI**, arXiv:2602.16421, 18 February 2026. Variable windows and nonstationary Gabor synthesis address magnitude/phase temporal mismatch around percussive events. The paper also discusses bounded-delay implementation. Our implementation is offline and differs in onset weighting, coverage-driven hop selection, phase propagation and resampling; it is not a reproduction of the complete method.
2. Polak and Erkut, **Low-Latency Pitch-Shifting with STN Decomposition**, DAS-DAGA 2025. The author-hosted abstract describes sinusoidal/transient/noise processing and acknowledges quality limits against commercial systems. It motivates separating texture problems but does not establish superiority of our implementation. No new full STN backend was added here.
3. Liu and Akama, **Self-supervised restoration of singing voice degraded by pitch shifting using shallow diffusion**, arXiv:2601.10345, January 2026. This singing-specific learned restoration route was not trained or executed here. It is not evidence of a mixed-music, stereo, allocation-free 32-frame solution.

This is a verified recent-paper selection, not an exhaustive search or a claim of the latest paper in every venue. Primary sources are listed below.

## C++ guard and study design

After a detected rise, the guard stays inactive for approximately one FFT window plus two hops. During steady regions it compares a bin's phase-derived frequency with its assigned peak owner's frequency. If their **modulo-hop phase difference** exceeds half an FFT bin, the bin uses its own predicted phase rotation rather than an incompatible owner's rotation. The modulo comparison avoids mistaking phase-estimator aliases separated by 2pi/hop for genuine disagreement. FFT/hop sizes, magnitudes, formant policy, shared-channel rotation and normalizer are unchanged.

Main C++ study: **1,596 synthetic renders plus 1,800 corpus renders**. Synthetic fixtures comprise the previous 11 fixtures and four oscillator-bank seeds, 48/96 kHz, six nonunity pitches plus separately reported unity, with all three policies on the two vowel fixtures. Comparators are General, Transient, Fuzzy and Fuzzy-noise baseline plus the two guarded Fuzzy modes. Every compared renderer receives the same source WAV within its cell.

Corpus: the supplied 20 mono 44.1-kHz test references, not the 88 training references. Exact pitch has 120 conditions with Off and Harmonic separately. Direct TSM has 60 measured target ratios, pitch=1 and Off, compared to the provided Elastique recordings themselves. The test corpus has been reused during development and is not a fresh blind holdout.

All C++ outputs pass finite/rate/channel/frame checks. The study uses centered timing and rate scaling. No output limiter, normalization, fitted delay or DTW is used. Descriptors retain existing definitions. A dB-error reduction is not a percentage improvement in perceived sound.

### Sustained partial balance

Lower is better. Means across six nonunity shifts. The four new banks use independent frequencies/phases and a 24-dB amplitude span, seeds93173–93176; they were not in the original two-bank pilot.

| 48-kHz fixture set | Old Fuzzy | Guarded Fuzzy | General |
|---|---:|---:|---:|
| Original harmonic/inharmonic | 5.107818 dB | **0.157781 dB** | 0.010517 dB |
| Four new oscillator banks | 3.778136 dB | **0.638466 dB** | 0.011119 dB |

At96k the new-bank means are3.767703→0.633340dB. General remains substantially more accurate on these steady banks. The guard narrows the short-window gap rather than eliminating it.

The guarded/non-guarded nonunity synthetic WAVs are identical for all24 attack cells,72 noise cells and72 stereo cells, counting both Fuzzy modes and both rates. This is fixture-specific, not proof that every natural transient/noise mixture is unchanged. Harmonic synthetic-vowel error at48k improves8.221917→7.463732dB; substantial residual error remains.

### Direct TSM against the supplied Elastique recordings

| Metric | Supplied Elastique | Old Fuzzy | Guarded Fuzzy | Guard wins/60 vs supplied |
|---|---:|---:|---:|---:|
| Broad-envelope RMSE, lower | 2.104070 | 2.136278 | **1.940758 dB** |43|
| Log-spectral distance, lower | 6.315414 | 6.411475 | **6.023543 dB** |47|
| Onset correlation, higher | 0.680285 | 0.726547 | **0.730168** |51|
| RMS envelope shape, lower | 1.872449 | 1.320763 | **1.319013 dB** |56|

Against old Fuzzy, spectral distance improves in53/60 conditions, worsens in4, ties in3. Against supplied Elastique, all four metrics improve simultaneously in33/60 conditions. This is not an overall perceptual score. The supplied CSV does not identify the native SDK version or processing mode.

Guard minus supplied baseline: spectral delta−0.291871dB, descriptive source-cluster95% interval[−0.493639,−0.091147]; envelope delta−0.163312dB, interval[−0.313449,−0.036133]; onset delta+0.049883, interval[+0.031250,+0.070136]; RMS-shape delta−0.553436dB, interval[−0.713507,−0.404585]. There are20 source clusters,4,000 draws, seed93173. Intervals are not multiplicity corrected and do not establish audible significance.

### Exact pitch: nonuniform improvement

120 conditions, Harmonic. Envelope error improves5.215338→5.059962dB,94wins/20losses/6ties versus old Fuzzy. However, onset correlation decreases **0.876904→0.873586**, delta−0.003318 and interval[−0.005801,−0.000929]. RMS-shape error changes0.870860→0.878747dB. The maximum raw sample peak rises1.621937→1.695722. With Off, RMS-shape also worsens slightly on average. Keep the guard opt-in; do not replace the general-purpose path based only on steady tones.

## Selective-window v2: new offline implementation and ablations

`selective_nsgt_v2.py` implements centered Hann nonstationary analysis, shared multichannel phase rotation, positive overlap-weight normalization and prescribed Fourier output resampling. It provides fixed-window, adaptive-window and adaptive-plus-coherence variants. The last is our project experiment, not attributed to SELEBI. It has **no formant preservation** and is not a replacement for the required harmonic/monophonic policies.

Longest window2048 at48k and4096 at96k; FFT length twice the window. The detector is a power-weighted mixed-phase derivative. Hop sizes use a coverage rule, not the paper's full redistribution algorithm. Comparisons across C++ and NSGT also include window/resampler differences; adaptation itself is judged against the matched fixed NSGT kernel.

**234 synthetic plus180 corpus outputs** were measured. Pitch tests cover six fixtures, two rates and six shifts; attack TSM tests cover three expansion factors at both rates. Attack start times scale, but the ideal2ms event duration is intentionally retained.

| NSGT raw attack width at48k | Fixed | Adaptive | Adaptive+coherent |
|---|---:|---:|---:|
| TSM expansion, three ratios |8.507260ms|**5.250674ms**|5.250674ms|
| Pitch shifts, six ratios |6.809330ms|**5.901766ms**|5.901766ms|

On the60 real TSM conditions:

| Variant | Envelope dB | Spectral distance dB | Onset | RMS shape dB |
|---|---:|---:|---:|---:|
| Fixed NSGT |2.652561|6.640710|0.722312|1.368884|
| Adaptive NSGT |2.651272|6.642772|0.719009|1.364971|
| Adaptive+coherent |2.148488|**5.969025**|0.723915|1.382524|
| Supplied Elastique |2.104070|6.315414|0.680285|1.872449|

Adaptive windows alone do not demonstrate broad real-corpus improvement in this implementation. Coherence helps spectral distance but worsens RMS shape against fixed NSGT. Some stationary harmonic/noise events are falsely detected; those results are retained. This is an offline alternative, not a realtime-qualified replacement, and not a verdict on a faithful SELEBI reproduction.

## Native comparison: not completed

The inherited `native_pitch_contract.py` requires source/configuration identity and has no derived-baseline fallback. This session prepared a compatible **98-condition request pack**,12 synthetic source WAVs,48/96k,six shifts plus unity, explicit Off/Harmonic controls. All98 source hashes, headers and the manifest identity were verified. Pack ID:

`f08624e25fa0ebebaac59e51ae7a311103e321a10299b43a8e2e6e523e2b1672`

The official REAPER page advertises an ordinary fully functional60-day evaluation. Its displayed Linux7.78 download redirected to a CDN the tools could not retrieve; local download also failed. No application or native zplane engine ran. This is an acquisition/execution limitation, not proof of an absent license and not a native result. The opt-in GitHub discovery workflow was not presented as successful.

The pack contains only inputs, requests and a blank receipt. Actual engine/host versions, modes, formant settings, hashes and float outputs are required, using host latency compensation without fitted alignment. Declared metadata alone does not cryptographically prove vendor identity; retain host logs. Native cents-level superiority remains unknown. No latest-native claim follows from the old provided TSM recordings.

## CPU clocks: new evidence, physical cause unresolved

New `rt_tsc_probe.cpp` places fenced RDTSCP around CPU/wall brackets. TSC includes clock-call overhead and is not a retired-cycle/instruction counter. Guest CPUID reports hypervisor and invariant TSC. The retired-instructions perf-event attempt returns **ENOENT(2)** here; prior EACCES is not relabeled as this run's error.

**288,000 raw iterations**: baseline Fuzzy, guarded Fuzzy, fixed80,000 integer recurrences and no-op; three repeats of24,000 calls each. First3,000 per run are retained as cold start. DSP uses96k stereo,32frames,+7st,four formant events/call,CPU0 affinity. No audio renders/builds overlap the probes. A small existing-CSV summary ran during initial warmup; this was not a perfectly isolated machine.

| Steady workload | Calls | CPU p99 range | CPU maximum | Deadline misses |
|---|---:|---:|---:|---:|
| Baseline Fuzzy |63,000|140.53–141.02us|1,525.91us|34|
| Guarded Fuzzy |63,000|138.90–141.45us|2,357.29us|38|
| Fixed integer work, no DSP |63,000|193.56–237.50us|2,342.65us|178|
| No-op |63,000|0.20–0.21us|127.47us|0|

Deadline333.333us. Guarded ordinary-audio p99 is similar, but no full48/96k32/64 CPU matrix was rerun. Rare deadline misses are not solved.

The worst integer sample in repeat1 has CPU2,342,651ns, wall2,341,231ns and6,084,832TSC ticks, with no guest switch/fault/migration. This corroborates a long interval outside DSP. Other outliers differ between nested-clock brackets; timer-call cost matters too. A virtual TSC can share the VM time model and does not identify host preemption, frequency/cache effects or accounting mechanisms. **Ultimate physical/virtualization attribution and hard-RT qualification remain open.** Raw maxima, misses and OS snapshots are retained. No global FPU/governor/scheduler policy changed.

## Local validation and failed hosted CI

Guarded GCC14.2 C++20/23 and Clang17 C++20/23 each pass21/21 CTests. Matched-Clang ASan+UBSan with leak detection passes21/21. Baseline CTest also passes21/21. Coverage includes pure C, no-allocation processing, scheduled/SIMD equality, compact delay, reset and linked stereo.

Inherited195 Python tests pass with both baseline and guarded CLIs. Ten new Python tests and six legacy dataset tests pass:211 distinct tests within this stated scope. This is not a claim that every interrupted new module in the complete c37 remote tree was fetched/tested. Actual commands and logs are supplied. The guarded scheduled tonal gate passes270/270 with unchanged thresholds. No fresh manual DAW, native-vendor or cross-platform host qualification is claimed.

**Hosted CI is not green.** Run34770137023 returned four failures with `steps:null`. Run34770528571 atd1b4c87d failed immediately; its explicit retry also failed all four jobs with `steps:null` (103759570955,103759571111,103759571118,103759571125). Annotation details/logs were unavailable through the connector. Do not infer billing/quota or source-code cause. Local success does not substitute for hosted success. No gates were disabled and main remains untouched.

## Reproduction and delivery

Apply the two isolated patches only in a disposable research worktree:

```sh
git apply research/experiments/fuzzy_coherence_guard.patch
git apply research/experiments/fuzzy_coherence_guard_alias_fix.patch
cmake -S research/cpp_pv_rt -B build-guard -G Ninja \
  -DCMAKE_BUILD_TYPE=Release -DCMAKE_CXX_STANDARD=20 \
  -DCMAKE_CXX_FLAGS=-DBOILED_EGG_EXPERIMENT_COHERENCE_GUARD=1
cmake --build build-guard -j2
ctest --test-dir build-guard --output-on-failure
# Build an unpatched worktree separately as build-base.
OPENBLAS_NUM_THREADS=1 python research/eval_sustained_guard_followup.py \
  --baseline /absolute/build-base --guard /absolute/build-guard \
  --suite synthetic --output results/guard-synthetic
OPENBLAS_NUM_THREADS=1 python research/run_selective_study.py \
  --suite synthetic --output results/nsgt
# Add --refs, --tests and --catalog for either script's --suite corpus.
```

Delivery contains measured source snapshots, transformations, all CSV/JSON, commands, logs and hashes. Original user audio/MOS and external native executables are excluded. Counts:3,396 C++ plus414 offline outputs = **3,810 primary generated outputs**. Both corpus tables reuse the same60 supplied baselines, not120 independent references. The144-output pilot and234-output NSGT replay are validation, excluded from the primary total. The98 native requests are inputs, not native outputs.

Primary references checked for this work:

- https://arxiv.org/abs/2602.16421 and https://arxiv.org/html/2602.16421v1
- https://arxiv.org/abs/2601.10345 and https://arxiv.org/html/2601.10345v1
- https://cerkut.github.io/publications/ (Polak/Erkut, DAS-DAGA2025)
- https://cdn.kernel.org/doc/html/latest/virt/kvm/x86/timekeeping.html
- https://licensing.zplane.de/technology
- https://www.reaper.fm/download.php
