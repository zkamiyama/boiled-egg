# Phase-edge transport and linked STFT consistency — 2026-09-15 JST

## Decision

Two independent research extensions were implemented and evaluated. Direct discrete-edge phase transport improves analytical partial balance but does not reverse the inherited heap renderer's natural temporal regression. Linked-channel consistency projection improves several spectral descriptors and, at two iterations, RMS shape relative to heap, but reduces onset correlation. Four/eight iterations produce a severe narrow-attack failure at +12 semitones. **Neither is promoted.**

This is draft PR11 on research/phase-edge-integration, stacked on the explicit-ramp branch. No product DSP, public ABI, plugin/UI/state, formant policy, automation or main change. The existing SDK remains available unchanged. No native-zplane processing, human listening, MOS, full-pipeline realtime or physical CPU-tail attribution is claimed.

## Provenance and implementation

Base b3f6d8c53bcf1f9380aa104c4bfcb773609e8ec5 and its eight workflows were checked. The restored local baseline initially came from the verified f8e5ef2 CI archive (198 tracked hashes); b3f6 adds only the prior final report. The new code is independently implemented atop the project's prior heap, not copied competitor code.

Key commits: ebf51058 protocol; e76b1f40 edge kernel; 4243c20f post-pilot projection addendum; 5de7f5c3 validated FFI; 351708b8 linked projection; 46e48264 matched renderer; 6bec0e01/dcac2f6e kernel and Python tests; bb5e024f complete-grid study; 9490bb78 metric tests; a29b79f6 benchmark; d256b51a build; 95d064ca CI. All are separate meaningful commits.

Validated code checkpoint: **95d064ca76ccb00e858e61578bd2c6f2a64e161f**, tree **645316a2e82c0e1697519cdb63b4cbcd8450f61f**. This result commit is documentation only. Successful final CI source was downloaded and all212 tracked hashes verified. Every locally present measured source file matches; the only four absent local files were workflow/protocol/addendum/prior final documentation. No computational difference was found. The downloaded source was independently rebuilt and passed2 CTests and16 Python tests.

### Hypothesis1: observed edge increments

Prusa/Holighaus Phase Vocoder Done Right estimates centered node derivatives and integrates trapezoid increments along a magnitude-prioritized path. The new ablations replace time edges, frequency edges or both with observed wrapped phase increments. The time edge uses synthesis-hop times the heterodyned interframe frequency estimate; the frequency edge uses stretch times the neighboring-bin wrapped phase difference. Same priorities/ties, input magnitudes, windows/hops, channel rotation and resampler. This tests a hypothesis, not an established bug in the original paper.

The edge kernel preallocates at construction, performs at most2*bins heap removals and needs no future-frame derivative for the both-edge formula. However, the Python renderer stores whole-signal arrays and selects its reference channel from the full input; it is still **offline**, not a new causal product backend. No explicit transient detector or source-profile classifier is added.

### Hypothesis2: linked consistency projections

The five-source edge pilot was negative, recorded before adding a separate hypothesis. Starting from inherited heap spectra, synthesize, analyze again, and project each multichannel coefficient onto `source_vector * exp(j*theta)`, where `theta=arg(sum(conj(source_vector)*estimate_vector))`. A zero inner product retains the previous feasible point. This preserves target coefficient magnitudes and interchannel ratios at projection, not necessarily the synthesized waveform's exact stereo image or magnitudes. It is not an output envelope EQ, limiter or fitted gain normalization.

Fixed budgets2/4/8 are all reported. This is a project-specific linked alternating-projection experiment, not a reproduction of SELEBI or of the online framework cited below. Increasing STFT consistency need not improve the desired attack. There is no formant preservation or dynamic automation in this renderer.

## Frozen protocol and data

Eight modes: locked, heap, edge_time, edge_frequency, edge_both, project2, project4, project8. The same five pilot sources were Ardour_2, Female_4, Male_6, Rock_4, Triangle_02. Their results and projection addendum were committed before remaining-source confirmation. No tuning followed confirmation. The other15 sources are withheld within this iteration only: the entire corpus has been reused historically.

| Primary suite | Outputs |
|---|---:|
|20 actual mono44.1k references x TSM ratios0.5/1.5/2 x8 modes|480|
|Bank/attack/noise/stereo x48/96k x6 pitches plus unity x8 modes|448|
|8 new banks x48/96k x6 nonunity pitches x4 fixed modes|384|
|**Total**|**1312**|

New seeds2609150..2609157 and the four new-bank modes locked/heap/edge_both/project4 were fixed before confirmation. Project4 is the middle budget, not the best pilot result. The original source WAVs are the actual supplied20 test references. Training files were not used. No replacement dataset or native/derived-Elastique baseline was introduced.

Every output has finite samples and exact length/rate/channels; raw output is neither normalized nor limited. Manifests bind source, renderer, kernel and analysis hashes; resumable per-case journals reject mismatches and incomplete grids. Rerenders and pilots are not counted as additional primary evidence. All outputs are discarded after measurement; the bundle does not redistribute user or generated audio.

Inherited5ms RMS shape, positive RMS-flux correlation and global normalized Welch PSD definitions are unchanged. Additional local STFT shape uses512/2048/8192 Hann windows,75% overlap, prescribed constant time-axis scaling, channel-power averaging, a single global energy normalization per representation, source-relative -40dB active bins and -120dB floor. No fitted delay or DTW. At96k window sizes double. These descriptors are source-relative, not errors against an ideal native stretch. The2048 descriptor overlaps the reconstruction scale, so its improvement is not independent perceptual validation.

## Natural results: no joint temporal/spectral winner

Means over60 conditions; lower errors and higher correlation are preferable.

| Mode | RMS shape dB | Onset correlation | Global PSD shape dB | Local2048 shape dB |
|---|---:|---:|---:|---:|
|Locked|**1.602618**|**0.453783**|1.347236|4.613709|
|Heap|1.880296|0.434090|0.771756|4.782577|
|Edge time|1.864922|0.437783|0.771852|4.800475|
|Edge frequency|1.899187|0.422280|0.775144|4.687850|
|Edge both|1.898515|0.423757|0.773245|4.695431|
|Projection2|1.731942|0.425552|0.604596|3.355998|
|Projection4|1.770226|0.418614|0.594438|3.106744|
|Projection8|1.776757|0.414139|**0.587578**|**2.964285**|

Edge-time versus heap RMS delta -0.015374dB has descriptive95% interval[-0.050272,+0.004665]; onset delta+0.003693 also crosses0. Both-edge RMS worsens+0.018220dB and onset worsens-0.010333, with intervals excluding0 in these directions. Direct increments alone do not explain or repair the natural regression.

Projection2 versus heap: RMS delta **-0.148354dB**, interval[-0.227196,-0.084934],46wins/14losses; global PSD **-0.167160dB**,54wins/6losses; local2048 **-1.426579dB**,60wins/0losses. But onset delta **-0.008538**, interval[-0.014024,-0.002989],25wins/35losses. It remains worse than locked on RMS and onset. More projection iterations improve spectral constraints further without reversing this tradeoff.

The15-source confirmation repeats the direction: Projection2 versus heap RMS -0.159482dB,36wins/9losses; onset -0.008230,19wins/26losses; global PSD -0.163235dB,40wins/5losses; local2048 improves45/45. Descriptive intervals resample source clusters4000 times,seed260915,keeping ratios within sources; no multiple-testing correction.

Counterexamples are retained: edge_both/Synth_Bass_2/T2 worsens RMS0.661769dB versus heap. Projection4/Ocarina_02/T2 worsens RMS0.713653dB. Projection8/Female_4/T2 loses0.162873 onset correlation. Raw natural peaks reach2.145606(edge_time),1.871401(heap),1.834582(project2) and1.182040(locked); no guarantee of bounded sample peaks or loudness neutrality is inferred.

## Synthetic spectra improve, but short attacks expose a failure

Mean relative partial-energy errors at48k, six pitches:

| Bank set | Locked | Heap | Edge both | Projection4 |
|---|---:|---:|---:|---:|
|Original analytical bank|0.557228|0.007490|0.000502|0.000277dB|
|New8 banks|0.556826|0.010102|0.003175|0.002071dB|

At96k the new-bank values are0.557844/0.010156/0.003138/0.002035dB. These are genuine fixture-level improvements, not percentages of perceived sound quality. Noise/stereo diagnostic rows are retained, and projection does not establish universal time-domain stereo transparency. Unity reconstruction maximum absolute error is3.33e-16 across the primary synthetic suite.

**Important counterexample:** at48k,+12st, the four-iteration projection expands the attack's5-95% energy width to **24.094226ms**, eight iterations to24.035278ms, versus heap0.492353ms. Two iterations yield0.589273ms. This is visible in the original recorded descriptor and reproduced in independent CI.

After discovering that result, a supplementary oracle audit compares all112 attack rows with the analytical shifted carrier retaining the2ms gate. At+12st the oracle's energy width is **0.922360ms**. Thus narrower than heap is not automatically more accurate either: raw width alone must not be labeled an error with lower-always-better direction. The extra audit is explicitly post-hoc, not another1312-case trial or new render count. No measurement values or thresholds were retuned to hide the failure. The separate timing and waveform-localization constraints remain necessary.

## Control replay and source differences

The unchanged locked/heap outputs from this study were replayed through the unmodified inherited renderer in the **same current environment**: **120/120 output PCM SHA256s match exactly**. This isolates the effect of the new alternatives.

A separate comparison to the previous session's delivered phase CSV gave0/120 whole-PCM hash matches, despite identical inputs and descriptor differences at floating-point-roundoff scale. That failed comparison is retained; its physical/library cause was not isolated. Same-current-environment identity is not retroactively presented as cross-session/cross-library identity. The new studies use NumPy2.3.5,SciPy1.17.0,SoundFile0.13.1; full source/library hashes are supplied.

## Verification and kernel cost

- GCC14.2/Clang17 xC++20/23:2/2 isolated CTests each. New kernel checks259700 curved conservative-field phase values,430524 bounded removals,zero processing allocations; inherited kernel tests also run.
- Matched-Clang ASan+UBSan with leak detection:2/2.
- Public research Python:16/16, including independent exhaustive priority oracle, nonaffine identity without renderer bypass, exact baseline replay, short/odd/silence/duration, stereo and projection-objective checks, local-metric calibration.
- One additional local-only paired-summary calibration passes; it is not a seventeenth committed/CI test.
- Existing public spectral SDK GCC20 regression:23/23. Product source is unchanged; this is regression verification, not offline-renderer host qualification.

The traversal microbenchmark compares equivalent prepared increments and requires exactly equal outputs. It performs24000 measured iterations plus4800 warmup across513/1025/2049/4097 bins and3 repetitions. Median mean-time reductions are about3.49%,0.91%,0.55%,0.64% respectively. Values include only traversal, not increment construction, FFTs, projection passes, resampling or a complete32/64-frame callback. Full-study elapsed times include Python allocations and parallel jobs and are not realtime evidence. Raw maxima remain in the CSV. No new physical CPU-tail conclusion is drawn.

The bootstrap summarizer create-file request was blocked by the connector. It was not retried via a different action. That script and its extra calibration remain **local-only**, clearly labeled in the bundle, not represented as committed/CI-executed. Primary study, numerical tests, descriptor implementation and this report are committed. This is a delivery limitation, not a hidden missing quality result.

## Hosted CI and final source audit

At95d064ca, all three triggered PR workflows succeed:
- research-phase-edges34923818796:five jobs, GCC/Clang20/23,16 Python tests,448-output synthetic replay, address/undefined sanitizers and artifact upload.
- product ci34923818811:existing product checks.
- research-pv34923818709:existing research checks.

Downloaded GCC20 artifact10379190802 has ZIP SHA256
`d3df43109c0340b2989b4718992c7c5bb2f4fc32e703d7f26aa07237ec80d285`.
CRC and all212 source hashes verify; synthetic merge commitd018f903d51ce371650d053238aff6d2ed275129 has tree645316a2e82c0e1697519cdb63b4cbcd8450f61f. The downloaded source rebuild passes2/2 CTests and16/16 Python tests. CI independently reproduces the24ms projection counterexample; its synthetic observations are not added to local primary count.

Primary CSV SHA256s:
- natural ca53052380acdb11e346bc5ea916da4275ffa6abc2c16875fe113a95b2d0b120
- synthetic 3fb430464c2f39f22982d662e1a5bec52e918101da7a05dfb1097e45d1eeec67
- new banks 6f74126a1fdec6f816e6d69a3f65bd09290266505288c69da1b5d44e7c82086f

## Reproduction and next direction

```sh
cmake -S research/phase_edges -B build-edge -G Ninja -DCMAKE_BUILD_TYPE=Release
cmake --build build-edge -j2
ctest --test-dir build-edge --output-on-failure
export BOILED_EGG_PHASE_HEAP_LIBRARY="$PWD/build-edge/libphase_heap.so"
export BOILED_EGG_PHASE_EDGE_LIBRARY="$PWD/build-edge/libphase_edge.so"
OPENBLAS_NUM_THREADS=1 python -m unittest discover -s research/phase_edges -p 'test_*.py' -v
OPENBLAS_NUM_THREADS=1 python research/phase_edges/study.py --suite synthetic \
  --kernel "$BOILED_EGG_PHASE_HEAP_LIBRARY" --edge "$BOILED_EGG_PHASE_EDGE_LIBRARY" \
  --cache results/edge-cache --output results/synthetic --workers 2
# Use --suite corpus --refs /absolute/20-reference-folder for actual audio.
# Use --suite banks and a distinct cache/output for fixed new seeded banks.
```

The retained code provides a useful phase-edge kernel and stereo-constrained reconstruction baseline, but does not justify adopting either full renderer. Next research should address local magnitude/time placement around transients jointly with phase, rather than chasing a smaller whole-signal PSD error. That is a next hypothesis, not a result already obtained.

Primary conceptual references checked:
- Prusa/Holighaus, Phase Vocoder Done Right (2017; arXiv posting2022), https://arxiv.org/abs/2202.07382 and HTML equations13-18/Algorithm1.
- Akaishi/Holighaus/Yatabe, SELEBI (2026), https://arxiv.org/abs/2602.16421. Magnitude/phase localization motivates the question, not a claimed reproduction.
- Peer/Welker/Kolhoff/Gerkmann, A Flexible Online Framework for Projection-Based STFT Phase Retrieval (2023), https://arxiv.org/abs/2309.07043. Its online framework is not implemented here; the shared-channel fixed-budget full-signal projection is this project's ablation.
