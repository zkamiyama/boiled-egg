# Timing, rate scaling and independent formants — 2026-09-13 JST

## Scope and decision

Implemented opt-in synthesis-center timing, sample-rate-scaled analysis, independent formant shifting, and an exact Multi-resolution FIR optimization. Restored the previously local objective-quality harness, its tests and CI to the repository. No product core, public product ABI, adapters, state serialization or main branch changed. No backend was promoted. Manual profiles and separate Off/Harmonic/Monophonic policies remain intact.

**Quality diagnostics improved substantially, but 96 kHz small-buffer realtime capacity is still not qualified.** No human listening or native élastique pitch comparison was performed. No MOS labels are assigned to newly rendered audio.

## Published implementation

| Commit | Change |
|---|---|
| `8b8987b8` | Restore full objective-quality harness |
| `b0be042c` | Restore 14 calibration/integration tests |
| `7c285a58` | Activate objective-quality Python3.11/3.13 CI |
| `e37a166f` | Opt-in C feature API, timing, rate scaling, formant ratio |
| `f7aa9a81` | CLI and C++ RAII controls |
| `0361c876` | C ABI/layout, streaming/no-allocation tests and callback benchmark |
| `ecb5b0c8` | Exact FIR traversal optimization |
| `dc726ece` | Analytical/corpus feature evaluation |
| `4eab4eac` | 270-case tonal/high-band gate |
| `056b537d` | Ten feature/CLI/integration regressions |
| `3feccf95` | Feature CI and exact-source artifact |

Validated code checkpoint: `3feccf955dde35393d19718b0585c64b1d1a44dd`, tree `a15d0c24b7e41166d55770e81ab53656b111f927`. The downloaded CI archive passed every source SHA256 and exact Git-tree check. All **42 files in research/cpp_pv_rt** match the final measured local DSP subtree byte-for-byte. Four principal analysis modules have identical computational ASTs; the inherited metric helper differs only in three docstrings' indentation. The exact downloaded source passed the full 171+6 Python suite with the matching local renderers.

Primary measurements preceded the FIR optimization; their original working-source and executable hashes remain unchanged. FIR equivalence is established by a separate 795-WAV replay. Evaluation manifests name their base revision and independently fingerprint actual working code/binaries rather than falsely attributing an uncommitted measurement to a later commit.

## Feature contracts

**Centered timing:** analysis input is padded by N/2, but the first synthesis-window center remains N/2 from the synthesis start. Opt-in centered timing crops N/2 synthesis samples instead of N/2 times the internal stretch. There is no post-hoc waveform alignment. This fixes the measured static-ratio event offset, not transient width or all dynamic time maps. The centered-mode latency query is a conservative input-lookahead hint across the inherited research ratio range, **not a fixed host/PDC output delay**.

**Scaled rate policy:** the smallest power-of-two factor with rate <=48000*factor scales FFT, hop and cepstral order. No down-scaling below48k. Multi-resolution's cutoff remains6500Hz and FIR becomes `(taps-1)*factor+1`. At96k its branches become2048/512 and1024/384, order80, FIR257, rather than the fixed1024/256 and512/192, order40, FIR129. API acceptance through384k is not a full-range quality qualification; this pass evaluates48/96k plus the44.1k corpus.

**Independent formants:** `initial_formant_ratio` and per-handle setter/getter specify output/input envelope-frequency scale in[0.5,2], independently of pitch/time. Ratio1 preserves; matching pitch cancels envelope EQ, tested byte-for-byte. Nonunity requires Harmonic or Monophonic. Effective envelope warp is `pitch_ratio/smoothed_formant_ratio`; the target has a10ms log-domain time constant per analysis frame. Calls are single-audio-owner operations, **not a new UI-thread mailbox or sample-offset event API**. Reset retains targets and clears smoothing. PV ABIv2/config68bytes and Multi-resolution ABIv1/config56bytes, original create functions and defaults remain compatible.

New header: `boiled_egg_research_features.h`. APIs: default features, PV/Multi-resolution create_ex and formant ratio setter/getter. Both RAII wrappers and CLIs expose the feature set. CLI flags: `--timing legacy|centered`, `--rate-policy fixed|scaled`, `--formant-ratio R` or `--formant-semitones ST`. Invalid, nonfinite and out-of-range controls are rejected.

**FIR optimization:** replace a per-tap variable modulo with two reverse contiguous spans through the same ring. Coefficients, tap order and double accumulation order are unchanged. No approximation, normalization, limiter or processing allocation is introduced.

## Matrix and input integrity

| Primary experiment | Measurements |
|---|---:|
| Synthetic: seven fixtures,48/96k,six pitches plus unity,five profiles,legacy/candidate; three vowel formant policies and96k timing-only attack ablation | 1575 |
| Exact held-out grid:20 sources x6 pitches x5 profiles x2 variants,Harmonic | 1200 |
| Measured target ratios:60 x5 profiles x2 variants,Harmonic | 600 |
| Derived-Elastique measured-ratio baseline | 60 |
| Independent formants:2 vowels x2 rates x3 pitches x5 profiles x2 modes x5 formant shifts | 600 |
| **Primary total** | **4035** |

Every primary output was finite and matched expected frames, rate and channels. Independent-formant ratio1 controls are reused but each row is a unique requested condition. Tone gates, replay, unit-test renders and benchmarks are not added to4035.

The supplied archives still audit as **240/240 paired,20 mono44.1k references,zero missing**. Training references are not pooled. Derived-Elastique means provided Elastique TSM output plus exact-length Fourier resampling, **not native Elastique pitch-shifter output**. Its measured ratios are not renamed to exact±3/7/12. Raw audio is neither normalized nor limited. Attack/corpus metrics do not align away timing errors.

## Results

### Attack timing and width

Eight known2ms gated events occupy eight distinct analysis-hop phases. Values below average those eight events; they are not individual-event maxima.

| Fuzzy48k | Legacy centroid bias | Centered bias |
|---|---:|---:|
| -12st | +10.659235ms | -0.007431ms |
| +12st | -5.337419ms | -0.004086ms |

Across five profiles,two rates,six nonunity shifts, the largest absolute candidate **condition-mean** bias is **0.050521ms**. Selected-profile CI calibration retains a0.2ms limit. This is static-control synthetic evidence, not a general zero-latency guarantee.

Mean excess attack width at48k remains about3.461ms for Fuzzy,3.553ms for Transient and8.083ms for General. Multi-resolution improves3.815→3.207ms. At96k, Multi-resolution scaling broadens its fixed-window legacy1.635ms to3.211ms while improving tonal fidelity. That tradeoff remains explicit.

### 96k tonal/formant quality

Means over six nonunity pitches and two fixtures; known-partial envelope errors, lower better, not human-vowel MOS.

| Metric | Legacy | Candidate |
|---|---:|---:|
| Multi-resolution partial balance | 11.51111dB | 5.18156dB |
| Multi-resolution fixed formants,Harmonic | 31.29096dB | 8.13207dB |
| Fuzzy fixed formants,Harmonic | 10.63054dB | 8.14390dB |
| Transient fixed formants,Harmonic | 10.61666dB | 8.13088dB |

Legacy96k single-PV tests doubled FFT/hop manually but left cepstral order40; Multi-resolution stayed fixed. Candidate scales all of these analysis parameters. Better spectral results do not erase attack/CPU costs.

### Natural held-out exact grid

120conditions/profile,Harmonic. RMS shape is normalized10ms power-envelope error against the source; no waveform time alignment.

| Profile | RMS shape error legacy→candidate,dB | Onset correlation legacy→candidate |
|---|---:|---:|
| General | 2.80771→1.19515 | 0.58657→0.81436 |
| Transient | 1.84987→0.85315 | 0.76056→0.87786 |
| Multi-resolution | 1.82797→0.86397 | 0.78015→0.88136 |
| Fuzzy-noise | 1.84973→0.85498 | 0.76083→0.87788 |
| Fuzzy | 1.85077→0.87086 | 0.76111→0.87690 |

Fuzzy paired RMS-shape change is -0.979906dB, descriptive source-cluster95% interval[-1.209182,-0.766252]. Onset change is+0.115790, interval[+0.094840,+0.137345]. Bootstrap4000draws resamples20sources with all six pitches kept together. No multiplicity-corrected/perceptual significance claim.

After timing correction, Transient has the smallest mean RMS shape error while Multi-resolution has the highest onset correlation. Earlier uncorrected rankings must not be treated as timeless algorithm rankings. On the separate measured60conditions, candidate Multi-resolution has0.78903dB/0.90099onset versus derived-Elastique1.63315dB/0.84029; these source-relative measurements do not establish native product superiority.

### Independent formants

**480/480 nonzero formant-shift conditions improve analytical envelope-target error over leaving formants at ratio1.** At48k Fuzzy/Harmonic mean error falls18.0513→9.5793dB; with pitch held fixed,17.3206→8.4163dB. Residual error remains substantial. A separate440→660Hz tone test verifies pitch remains within3cents while formant ratio changes. Natural vocal timbre/intelligibility and audible automation transitions still require listening.

### Peaks and exact compatibility

Candidate exact-grid Fuzzy maximum sample peak1.621937,47/120 above unity; Multi-resolution1.755639,52/120 above unity. Float samples above unity are not automatically clipped files, but headroom/artifact review remains needed. The fourfold FIR peak estimate is not a standards-compliant true-peak meter.

**900/900 legacy corpus DSP WAVs match the preceding evaluation byte-for-byte.** Pre/post FIR replay matches **795/795 Multi-resolution WAVs**:315synthetic,120independent-formant,360corpus. The60 derived replay files are excluded from that DSP count. Same-toolchain equivalence is not cross-compiler bit identity or subjective quality proof.

## Performance: remaining blocker

Same VM,CPU0affinity,48/96k,mono/stereo,32/64frames,six pitches,Harmonic,four profiles. Each pre/post optimization stage has three repetitions, alternating legacy/candidate order within each repetition. Each cell measures1200callbacks after200warmup callbacks. Compiler/corpus work finished before timing. Thread-CPU and wall measurements, unchanged PV controls, first-output/input-lookahead observations and all repetitions are retained.

The median per-cell Multi-resolution candidate p99 CPU-time improvement over48conditions is **36.0176%**. Table values are worst pitch of each cell's three-repeat median p99/deadline; above1 misses the deadline.

| Rate/channels/block | Before FIR optimization | After |
|---|---:|---:|
| 48k/mono/32 | 0.635 | 0.529 |
| 48k/stereo/32 | 1.057 | 0.761 |
| 48k/stereo/64 | 0.649 | 0.460 |
| 96k/mono/32 | 3.259 | 1.751 |
| 96k/mono/64 | 1.689 | 1.040 |
| 96k/stereo/32 | 5.755 | 2.972 |
| 96k/stereo/64 | 3.072 | 1.680 |

All measured48k candidate cells are below1 in this summary, not a portable realtime guarantee. At96k candidate Fuzzy also exceeds deadlines:stereo32=2.299,stereo64=1.310. No CPU threshold was relaxed. Stages were sequential; shared-VM variability remains relevant. Quality-preserving rate scaling still needs bounded workload distribution/SIMD before promotion. Input-lookahead hints are not a tested fixed host/PDC delay.

## Validation

GCC14.2,Clang17,Python3.13.5; dependency/executable versions and hashes retained.

| Validation | Result |
|---|---|
| GCC C++20/23 | 12/12 CTests each |
| Clang C++20/23 | 12/12 CTests each |
| Clang ASan+UBSan,leak detection | 12/12 CTests |
| Exact committed-source research Python | 171/171,no skips |
| Exact committed-source legacy TSM Python | 6/6 |
| Centered/scaled tonal gate | 270/270,no failures |
| Worst low-tone error / minimum target-to-spur | 2.153085cents /22.816859dB |
| Worst high-band p95 ripple | 0.145946dB <0.25dB |
| Feature hosted CI | CTest12 +feature10 +tones270 passed |
| Existing-product hosted CI | All nine jobs passed |

C/C++ tests include old ABI layouts, zero/short input, reset, exact duration, block partitioning, stereo relation, manual scaling equivalence and formant/pitch cancellation. No-allocation coverage includes cold processing, flush/reset and pitch/time/formant changes. Functional extreme-ratio tests are not audible-quality qualification. The earlier near+24st peak pathology was not repaired/requalified.

Feature CI run34728410521,artifact10308926524 records code3feccf95. Product CI run34728410545 at that checkpoint passed all nine jobs including TSan,CLAP,VST3 Steinberg validator,sanitizers and installed consumers. These are existing-product regressions, not promoted-feature host tests. No new local TSan/CLAP/VST3 run is claimed. Development compile/runner errors were fixed and their logs retained.

## Public élastique comparison

Official references checked2026-09-13; SDK and plugin specifications are distinct.

| Capability | Public reference | Current research status |
|---|---|---|
| Stable timing | PRO SDK timing stability/sample-accurate stretching[1] | Static pitch bias reduced; dynamic maps/fixed host latency not qualified |
| Mono/poly formants | PRO SDK supports both[1] | Separate policies retained; no perceptual parity claim |
| Independent pitch/timbre | PITCH plugin±1octave independently[2] | Independent±1octave formant ratio now in C,C++,CLI; host automation/state pending |
| Rates | PRO SDK32–384k;PITCH plugin44.1–192k[1][2] | Scaling and48/96k evidence; full-range quality incomplete |
| Interchannel phase | PRO SDK coherence[1] | Fuzzy linked-channel rotation and synthetic stereo checked; no all-profile/listening parity |
| Channels | PRO SDK48;PITCH plugin16[1][2] | Research remains1–8; no superficial limit increase |
| Workload | EFFICIENT split processing;SDK SIMD listed[1] | FIR optimized;96k small blocks still miss deadlines |
| Plugin effects | PITCH MIDI,delay/freeze,AU/AAX/VST3[2] | Not added to this SDK-focused change; existing adapters unchanged |

Next priority: bounded FFT/frame workload distribution and SIMD/kernel optimization, then a fixed-latency integration contract and sample-offset/atomic-mailbox handling for new formant controls. Native licensed comparison and human listening remain necessary. UI effects or unsupported channel-limit increases would not close the measured gap.

[1] https://licensing.zplane.de/technology#elastique
[2] https://products.zplane.de/products/elastiquepitch

## Reproduction

```sh
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
cmake -S research/cpp_pv_rt -B build/features -G Ninja -DCMAKE_BUILD_TYPE=Release -DCMAKE_CXX_STANDARD=20
cmake --build build/features -j 2
ctest --test-dir build/features --output-on-failure
export BOILED_EGG_PV_CLI="$PWD/build/features/boiled_egg_pv_rt_cli"
export BOILED_EGG_MULTIRES_CLI="$PWD/build/features/boiled_egg_multires_rt_cli"
python -W error::ResourceWarning -m unittest discover -v -s research -p 'test_*.py'
python -W error::ResourceWarning -m unittest -v eval/test_tsm_dataset.py
python research/check_feature_quality.py --build "$PWD/build/features" --output results/feature-tonal.json
for suite in synthetic formant; do
  python research/eval_research_features.py --suite "$suite" --build "$PWD/build/features" \
    --base-commit "$(git rev-parse HEAD)" --workers 3 --output "results/features-$suite"
done
python research/eval_research_features.py --suite corpus --build "$PWD/build/features" \
  --base-commit "$(git rev-parse HEAD)" --ref-dir data/ref_test --test-dir data/test \
  --catalog data/TSM_MOS_Scores.csv --workers 3 --output results/features-corpus
# No competing build/corpus load; use a CPU available on your machine:
for repeat in 1 2 3; do
  taskset -c 0 build/features/boiled_egg_features_bench "$repeat" > "results/callback-$repeat.csv"
done
# Example: pitch -7st, desired formants +3st, explicit Fuzzy:
build/features/boiled_egg_pv_rt_cli in.wav out.wav --time 1 --profile transient --mode fuzzy \
  --pitch-semitones -7 --formant harmonic --formant-semitones 3 \
  --timing centered --rate-policy scaled --block 64
```

The analyst bundle retains exact committed source, measured analysis overlay, primary/replay/callback CSVs, input hashes, local/CI logs and a longer report. Dataset audio/MOS and raw renders are not redistributed. No pending local-only feature implementation or unactivated feature CI is represented as committed.
