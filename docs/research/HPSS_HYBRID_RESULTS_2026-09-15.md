# Linked HPSS hybrid and OLA noise diagnosis — 2026-09-15 JST

## Decision

Implemented long harmonic phase processing plus short percussive OLA/PV, followed by a separately declared source-address power-normalization experiment. The naive hybrid fails the natural spectral/time comparison. Power normalization corrects a white-noise gain model but does not remove repeated-grain periodic correlation. **Neither full renderer is promoted.** The reusable result is an independently tested mask/OLA/variance kernel and a reproducible explanation of two different failure mechanisms, not a production-quality replacement.

Draft PR12 is on `research/hpss-transient-hybrid`, based on `research/phase-edge-integration` at58f1c6b7c6e34967cad92f63cf6f6897d0f9b6fa. No product DSP, public ABI, plugin/UI/state, formant policy, automation or main change. No native-zplane processing, blind listening, MOS, full-pipeline realtime or physical CPU-tail attribution.

## Source and publication scope

The initial prior CI archive passed CRC and all212 tracked hashes. The previous branch HEAD and three successful workflows were checked. New commits are meaningful separate units: f5436647 protocol;3ae57cb4 masks/OLA;5eb7cfcf FFI;1fc9e57d renderer;a7ccd703/73d1ff5c tests;b67b7846 metrics;ffbab7e2 post-primary hypothesis;392887b9/bac72057 grouped weights;cda0c75e supplementary renderer;b1c2c0ff independent power tests;3a2879ef build/oracles/negative calibration;93ab679e CI;8fc906d8 microbenchmark;37cb4095 operational documentation.

Validated checkpoint **37cb4095b02564f727e393e6128e6b33f6e888aa**, tree **e3b9b0f1d098d29fb0405e4772c1e945d2d763c8**. This results commit is documentation only. Downloaded CI source has231 verified tracked hashes. Every locally present measured source matches exactly; five absent local files were workflow/protocol/addendum/README/prior-result documentation, not computational files. A fresh build of downloaded source passes3 CTests and21 Python tests, and all three resulting local library SHA256s equal the measured libraries.

The primary `research/hpss_hybrid/study.py` write was blocked by the connector. It was not retried through another GitHub action. That actual evaluated harness, supplementary runners, journals and aggregate bootstrap analysis are delivered **local-only**. They are not claimed committed or CI-executed. The independent kernels, renderers, metrics and unit tests are committed. This is a reproducibility-delivery limitation; it is not hidden by reporting all1728 outputs as hosted-CI tests.

## Hypothesis and construction

Conceptual basis: Driedger/Mueller/Ewert, Improving Time-Scale Modification of Music Signals Using Harmonic-Percussive Separation (SPL2014), author accompanying page. Long-window PV for harmonic content and short time-domain OLA for noise-like/percussive content jointly change local magnitude support and phase treatment. SELEBI2026 motivates joint magnitude/phase localization, but this is **not** its separation-free method or a reproduction of either complete paper. No external reference implementation was copied.

Our separator uses shared-channel RMS STFT magnitude, Hann2048/FFT4096/hop256 at48k (double at96k), centered17-frame/17-bin medians and soft complementary squared masks. Values are rescaled before squaring to avoid overflow; silent bins split1/2. Harmonic reconstruction is H; P=input-H retains complementary reconstruction. The same mask applies to every channel. Centered/full-array processing is offline.

Six primary modes: unchanged locked and heap; hps_locked_ola/hps_heap_ola; hps_locked_pv/hps_heap_pv. H uses the inherited long-window phase renderer. P uses Hann256 at48k/512 at96k, dense hop floor(window/(8*max(1,alpha))) for waveform OLA, or matched short locked PV as a branch-type control. Pitch uses time*pitch stretching followed by the inherited Fourier resampling convention. There is no output limiter, fitted loudness factor, frame-envelope correction or per-file mode selection. No formant preservation or dynamic-time host operation is added.

## Primary fixed evaluation

| Suite | Generated outputs |
|---|---:|
|20 actual mono44.1k references x ratios.5/1.5/2 x6 modes|360|
|bank/attack/noise/stereo/55Hz/mixture x48/96k x6 shifts plus unity x6|504|
|8 new banks x48/96k x6 shifts xlocked/heap/hps_heap_ola|288|
|**Primary total**|**1152**|

New-bank seeds2609160..2609167 and all modes were fixed before outputs. The five named diagnostic pilot sources are Ardour_2,Female_4,Male_6,Rock_4,Triangle_02. No parameter tuning followed primary outputs; remaining15 sources are within-iteration confirmation only, not a pristine holdout. The20-file corpus has been reused historically. Training files/native baselines were not substituted.

Inputs, code, kernels and output PCM are fingerprinted. Complete-grid checks and manifest-bound per-cell journals reject incomplete/duplicate/mutated data. Raw audio is not normalized or limited. All outputs satisfy finite/exact-length/rate/channel requirements. Unity maximum absolute error in the primary synthetic set is2.22e-16.

Natural metrics retain prior definitions:5-ms normalized RMS shape, positive RMS-flux correlation, whole-signal normalized Welch PSD, and local512/2048/8192 Hann STFT shape under prescribed time-axis scaling. These are source-relative diagnostics, not errors against a unique ideal musical stretch or native-vendor output. Local reconstruction-scale metrics are not independent perceptual evidence.

Analytical attacks retain the2ms gate and shift the carrier; report width ABSOLUTE ERROR against this oracle, centroid error, outside-gate energy and event gain. A narrower width alone is not universally better. Mixtures use a declared high-pass isolation for attack diagnostics; this is an analytical family, not a learned source classifier.55Hz raw Hilbert ripple is descriptive and can be affected by finite-record behavior; it is not the established high-band modulation gate.

## Primary natural results: rejected

Means over60 conditions:

| Mode | RMS shape dB | Onset correlation | Global PSD dB | Local2048 dB |
|---|---:|---:|---:|---:|
|Locked|1.602618|0.453783|1.347236|4.613709|
|Heap|1.880296|0.434090|0.771756|4.782577|
|HPSS locked OLA|2.392731|0.422089|5.179083|8.489876|
|HPSS heap OLA|2.574722|0.415517|5.136394|8.617448|
|HPSS locked short-PV|1.999398|0.442159|2.095541|6.021094|
|HPSS heap short-PV|2.117467|0.423830|2.108728|6.154797|

HPSS heap OLA versus heap: global PSD worsens60/60, mean+4.364638dB, source-cluster95% interval[+3.404773,+5.506672]; RMS worsens55/60,mean+0.694427dB,interval[+0.441178,+0.955582]. Onset delta-0.018573 has interval[-0.047174,+0.008960],25wins/35losses. The15-source subset likewise has globalPSD45/45 losses and RMS40/45 losses. Switching P to short PV reduces damage but still loses globalPSD60/60 and RMS49/60 versus heap.

Examples: HPS-heap-OLA Triangle_02/T2 globalPSD+13.012205dB and onset-0.174927; Child_4/T.5 RMS+2.318630dB. HPS-heap-shortPV Ocarina_02/T1.5 onset-0.215112. No claim is made that the original published HPSS system, other windows/masks or all decompositions would fail similarly.

### Synthetic tradeoff

At48k six nonunity pitches, original partial-bank error: locked0.557228,heap0.007490,HPSS-heap-OLA0.232878,HPSS-heap-shortPV0.218535dB. New eight banks:0.498520/0.007323/0.380307dB for locked/heap/HPSS-heap-OLA. The hybrid narrows the ordinary locked weakness but loses much of heap's precision.

At+12st48k, oracle attack5-95% width0.922360ms:

| Mode | Width ms | Absolute width error ms | Outside-gate energy |
|---|---:|---:|---:|
|Locked|7.813835|6.891475|0.747150|
|Heap|0.492353|0.430008|0.000616|
|HPSS heap OLA|1.507278|0.584918|0.034105|
|HPSS heap short-PV|1.248010|0.325650|0.006461|

The simple short branch avoids the earlier projection's24ms case but is not jointly best. HPSS-OLA attack output in this case is about8.92dB below the source RMS; narrower attacks alone cannot establish fidelity.

## Post-primary mechanism diagnosis and follow-up

A fixed white-noise control shows conventional dense OLA loses roughly7–10dB away from unity. At a given output sample, identical original-source addresses should add coherently; distinct white-input samples have independent variance. Let w_g be the sum of window weights for one source address. The expected numerator variance is sigma^2*sum_g(w_g^2), not sigma^2*(sum_g w_g)^2. We independently implement sqrt(sum_g(w_g^2)) as a denominator. This depends only on positions/windows, **not measured source/output loudness**. At unity all addresses agree and it reduces to window-sum normalization without an arbitrary unity bypass.

This model does not cover colored/tonal cross-sample correlations or H/P branch interference. Monotone source-minus-destination address groups are checked before mutation. Scratch and result buffers are caller-owned; the full output-sized Python use remains offline, not a stream-ready buffer contract.

The committed addendum precedes576 supplementary outputs:336 synthetic+240 natural. Four fixed modes cross dense/sparse hop and amplitude/grouped-power normalization. Sparse hop is floor(min(window/4,window/(2*alpha))). **144 outputs repeat primary dense-amplitude controls; all144 PCM hashes match.** Thus1152+576=1728 generated evaluations contains repeated conditions, not1728 independent sources. The remaining432 are new supplementary mode/condition combinations. A portable local-only runner exactly replays both supplementary CSVs,576 rows; that replay is not additional research evidence.

Supplementary natural means:

| Mode | RMS shape dB | Onset | Global PSD dB | Local2048 dB |
|---|---:|---:|---:|---:|
|Dense amplitude|2.574722|0.415517|5.136394|8.617448|
|Dense grouped power|2.239994|0.455916|5.403402|8.632468|
|Sparse amplitude|2.244039|0.423419|3.938185|7.382162|
|Sparse grouped power|2.064425|0.438541|3.766784|7.139188|

Power fixes part of the temporal/gain problem but leaves or worsens spectra. Dense-power versus dense-amplitude improves RMS49/60 and onset45/60; globalPSD worsens41/60,mean+0.267008dB,interval[+0.101509,+0.440195]. Sparse-power reduces globalPSD56/60 versus the bad dense control, but remains far worse than original heap. This is a post-primary exploratory study, not untouched confirmation.

### Gain and coloration are different failures

In the separate32-row noise-model audit,48k white noise(seed261),T2:

| Short OLA | RMS gain dB | Strongest lag | Output correlation | Source correlation at same lag |
|---|---:|---:|---:|---:|
|Dense amplitude|-7.240788|16|0.974702|0.005878|
|Dense grouped power|+0.029200|16|0.974702|0.005878|
|Sparse amplitude|-1.242171|64|0.660820|0.003344|
|Sparse grouped power|+0.006590|64|0.680557|0.003344|

Dense power normalization restores the expected noise level, while periodic correlation remains. Both dense versions also have the same PSD flatness0.000585629 in this audit. This directly distinguishes gain loss from repeated-grain coloration; it is stronger than merely observing a worse aggregate score. It does not prove every natural-audio error has this sole cause. Repetition/weight geometry, separator leakage and inter-branch phase remain separate concerns.

A negative calibration now checks that the known dense construction has lag16 correlation>.95 and that power normalization does not remove it. That test passing means the known limitation is reproduced, NOT that this output passes a sonic-quality gate. No threshold was relaxed to promote the candidate.

## Verification and remaining scope

- GCC14.2/Clang17 xC++20/23:3/3 isolated CTests each.
- Matched-Clang ASan+UBSan with leak detection:3/3.
- New mask kernel:5001 independent long-double comparisons across huge/tiny finite values.
- New OLA:362142 exact samples versus independent gather reference; invalid inputs transactional.
- Grouped-power:24918 values versus independent source-address dictionaries; zero allocations in each new kernel.
- Committed Python scope:21/21. Two extra local journal/grid tests pass; four repeated oracle tests in the preserved original local file are not counted again.
- Existing spectral publicSDK GCC20 regression:23/23, product source unchanged.

An initial uninitialized-name defect in the added low-tone evaluator was caught by its test before primary scoring and corrected. Its original failed log is retained; thresholds/source data/DSP were not changed to bypass it.

The inherited locked/heap renderer was separately replayed in the same current environment:120/120 current primary PCM hashes match. A comparison to the previous session's saved CSV yields0/120 whole-PCM matches despite identical input hashes and descriptor differences no larger than4.71e-14. The cross-session/library cause is unproven. That failed archival byte comparison remains separate; current-environment identity does not retroactively certify cross-environment reproducibility.

Kernel-only timing:43200 measured+7200 warmup calls,CPU0-affined,4096source frames stereo,windows256/512,three ratios and three repeats. CSV retains mean,p99 and maxima. It excludes HPSS/FFT/full synthesis and cannot be read as32/64-frame callback capacity. OLA accumulator clearing is outside its measured primitive; grouped-weight scratch clearing is inside its function. No universal timing ratio, new realtime guarantee or CPU-tail cause.

## Hosted CI and source verification

At37cb4095, all triggered PR workflows succeeded: research-hpss-hybrid34927899001 (five jobs), productci34927898803 and research-pv34927898814. Dedicated CI executes3 CTests/21 Python tests per compiler configuration plus address/undefined instrumentation; it does NOT run the local-only full corpus/supplement harness.

Successful GCC20 artifact10380895152 was downloaded. ZIP SHA256:
`4d5478ea979a59f0dc245178df6f476041657ad12d29868ba7533e5ca2929b2f`.
CRC and231 source hashes verify. Synthetic merge bf44207a4a54c7ad65fd31f25b7c423050ddea5a has treee3b9b0f1d098d29fb0405e4772c1e945d2d763c8. Fresh source rebuild passes3/3 and21/21, reproducing measured local library SHA256s:
- masks/OLA:7ec59e9d2a0f8ae94a7f1e73efe0e07f4b2a62648490ec5732b09fae39ac2d81
- grouped power:d60a5c02b99c8bb6906a8066af2d879c81a238933794f2df18aad829b236454e
- inherited heap:fe52138833142ebb2368e8038890081136228c999abdae911a29f7b4d102aec5

## Reproduction and conclusion

Build/test commands are in research/hpss_hybrid/README.md. The delivery contains exact validated source, local-only measurement/aggregation runners, all CSV/JSON/journals, frozen protocols, original failures and logs. Original user audio/MOS, generated waveforms, fonts and external SDKs are not redistributed. Use the supplied reference folder only when reproducing the actual20-source study; do not label a substitute dataset as the original.

The next useful hypothesis is to control correlation/repetition in the noise-like residual, or explicitly transport transient events while treating stochastic residuals separately, not simply increase phase refinement or fit output gains. That next hypothesis is not claimed implemented here. Preserve this candidate as research and keep stable main unchanged.

Primary conceptual references:
- https://www.audiolabs-erlangen.de/resources/2014-SPL-HPTSM/
- https://arxiv.org/abs/2602.16421
