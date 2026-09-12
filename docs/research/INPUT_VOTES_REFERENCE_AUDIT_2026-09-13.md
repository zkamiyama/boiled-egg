# Input, vote and all-formant reference audit — 2026-09-13 (JST)

## Scope and provenance

This is the **4,752-render, three-formant** pass and its **18-trial** listening pack. It is separate from the harmonic-only 1,584-render / 36-trial checkpoint in `REFERENCE_PROFILE_VALIDATION_2026-09-13.md`; do not mix their artifact hashes or benchmark repetitions.

Work remained on `research/formant-v0.3-integrated`. No C++ DSP, public C ABI, wrapper, host adapter, state serialization or main-branch code was changed. No research backend was promoted. Existing concurrent reference-evaluation, player and ratings work was preserved rather than overwritten.

Initial source replay: `d0160627f55b56b9ae7d2bc49c6e5ba0ca7ac356`. The real-corpus run declares `6b746b1791cbc017897ecbdf9514b49d90c963dc` and records actual renderer hashes. Final complete source replay and Python validation used `1e8fc2a8ddbe8ed800de3be3ae45596e158beac6`, tree `69306214c9f769c87fb2683da26c25193f789b3f`; the local tracked tree matched exactly. DSP and reference-evaluator files were unchanged between those checkpoints.

## Implemented and committed

| Change | Commit |
|---|---|
| Exact ZIP/MOS input audit, no fuzzy reference substitution | `24e1e8a6` |
| Strict three/four-way winner-vote decoder, missing-answer accounting | `a1307d46` |
| Input/vote synthetic tests and CI | `f716b6a5`, `6b746b17` |
| Raw peak audit with WAV/CSV Peak and RMS agreement | `03e35863` |
| Peak-audit regressions and CI dependency coverage | `ecdbd9cc`, `3af76f4c` |
| Legacy correlation input-mutation fix and regression tests | `70ce3ab3`, `e6e08fef` |
| Restore unrelated report formatting after that fix | `1e8fc2a8` |

`audit_tsm_inputs.py` checks exact score-to-audio names, archive path safety, ambiguous basenames, audio-header compatibility and input hashes. `--require-four-way` blocks incomplete input rather than manufacturing a comparison. Header readiness alone does not certify finite audio samples.

`score_blind_votes.py` decodes legacy winner choices (`overall`, `attack`, `tone`) against each trial's A/B/C[/D] mapping. Wrong-pack IDs, duplicate/unknown trials, invalid labels and repeated listener/file submissions are rejected. Missing preferences are neither losses nor ties. Unbound legacy data requires explicit `--allow-unbound`. Counts are descriptive, not MOS, pairwise rankings or promotion decisions. This format is distinct from the new player's numeric ratings consumed by `summarize_profile_ratings.py`.

`report_reference_peaks.py` validates grid completeness and raw-file hashes, remeasures amplitude and requires CSV Peak/RMS agreement. It records peak time/channel, sample counts above unity, crest factor, RMS/peak ratios, and paired envelope/onset deltas. Undefined silence ratios remain null. It never alters raw audio or labels an inspection flag an audible artifact.

## Supplied dataset and remaining input gap

The supplied reference archive contains **88 training references**, not the required test references. The processed archive contains **240 files**, all exactly matched to the **5,520-row** MOS catalog. Their required reference set contains **20 names**, with **zero** overlap with the supplied 88. There are 80 Elastique, 80 FuzzyTSM and 80 NMFTSM processed files.

The real audit therefore reports **0/240 paired; 20 references missing** and exits **2** under `--require-four-way`. This expected readiness failure is not a software-test failure. `ref_test.zip` remains necessary for the original held-out four-way comparison. No MOS is transferred to new renders, and no derived-Elastique output is fabricated.

The available references are used only for a separate exploratory comparison. Original catalog categories are retained: music 27, solo 31, voice 30. All are 44.1 kHz; 13 are mono and 75 stereo. Music is not silently reclassified as mix or polyphonic.

## Real-audio matrix

Time ratio 1; block 256; pitches −12, −7, −3, +3, +7, +12 semitones; explicit General, Transient and Multi-resolution profiles; explicit Off, Harmonic and Monophonic formant policies.

**88 × 6 × 3 × 3 = 4,752 renders**, representing 1,584 paired conditions. All **4,752/4,752** were finite and had the expected sample rate, channel count and exact frame count. Envelope/onset diagnostics are averaged per channel, not calculated from a potentially canceling stereo downmix.

| Multi-resolution vs Transient | Conditions | Mean envelope-error delta, dB (lower better) | Mean onset-correlation delta (higher better) | Envelope wins | Onset wins |
|---|---:|---:|---:|---:|---:|
| Off | 528 | −0.000310 | +0.018310 | 257 | 469 |
| Harmonic | 528 | +0.000804 | +0.017757 | 202 | 457 |
| Monophonic | 528 | +0.000850 | +0.017197 | 193 | 459 |

The envelope means are effectively tied in this diagnostic; Multi-resolution is not uniformly better. Onset improvements are objective diagnostics, not listening preferences or a native Elastique comparison.

Within Multi-resolution, Harmonic reduces envelope error versus Off by 2.531344 dB on average, winning 521/528 conditions. Monophonic improves it by 2.195684 dB, winning 519/528. These are not all-condition wins and are not perceptual scores.

### Raw peaks

The strict raw audit completed all 4,752 measurements and flagged **729 profile rows** for inspection under peak >1.0 or peak/Transient >1.1 (plus explicit nonzero-versus-silence cases).

| Profile, all formant policies | Maximum raw sample peak | Flagged rows |
|---|---:|---:|
| General | 1.697386 | 352 |
| Transient | 1.599887 | 170 |
| Multi-resolution | 1.479400 | 207 |

These are sample peaks, not reconstructed true peaks. Floating-point samples above unity are not automatically clipped files. Flags are not 729 confirmed audible defects. No human listening assessment has been supplied.

## Validation

Local toolchain: GCC 14.2, Clang 17, Python 3.13.5, NumPy 2.3.5, SciPy 1.17.0, SoundFile 0.13.1. Logs and environment metadata are retained in the analyst validation bundle.

| Test | Result |
|---|---|
| GCC C++20 / C++23 Release | 6/6 CTests in each configuration |
| Clang C++20 / C++23 Release | 6/6 CTests in each configuration |
| Clang ASan + UBSan with leak detection | 6/6 CTests |
| Final exact-source research Python suite | 111/111, no skips |
| Legacy dataset suite after fix | 6/6 |
| Pure C consumers / allocation-free hot path | Included in each CTest configuration |
| Real-CLI integration within Python tests | 54 renders across all profiles/pitches/formant policies |
| Multi-resolution low-frequency safety | Max 2.153085 cents; min target/spur 23.006126 dB |
| High-band modulation | Worst p95 ripple 0.143867 dB, below 0.25 dB |
| Synthetic PV pitch | Max absolute error 0.003095 cent |
| Linked-stereo fixture | Relative RMS relationship error 4.4502e−5 |
| Blank numeric ratings | `not_listened`, zero completed triplets, null scores |

Product/main code was untouched. TSan, CLAP smoke and Steinberg VST3 validation were not rerun locally; this is research-backend/tool validation, not a new host-product qualification.

### Legacy evaluator bug found by the batch tests

The original identity test in `eval/test_tsm_dataset.py` failed onset correlation at 0.9987337907 against its unchanged >0.999 requirement. `_corr` used `np.asarray` followed by in-place centering; for float64 input this modified caller feature arrays, including overlapping views repeatedly used by `_best_shift`.

The fix makes independent copies before centering. Regression tests cover ordinary float64 inputs, read-only arrays, overlapping strided views, repeatable alignment and existing short/constant conventions. All six legacy tests now pass without loosening thresholds. Older results from this legacy TSM metric should be regenerated before relying on affected alignment/correlation diagnostics. The 4,752-render experiment uses the separate research metric implementation and is not affected by this fix.

### Callback measurements and CI timing failure

Three sequential Multi-resolution benchmark repetitions were pinned to CPU 0 after the corpus work. Matrix: 48/96 kHz, 32/64/128/256 frames, mono Harmonic, representative pitch ratios approximately 0.667 and 1.498 (±7 st). Median thread-CPU p99/deadline across the repetitions:

| Rate / block | Downshift | Upshift |
|---|---:|---:|
| 48 kHz / 32 | 0.350 | 0.353 |
| 48 kHz / 64 | 0.179 | 0.182 |
| 96 kHz / 32 | 0.704 | 0.715 |
| 96 kHz / 64 | 0.372 | 0.362 |

These are shared-VM diagnostics, not portable real-time guarantees, multichannel capacity measurements or full ±12-st CPU guarantees.

The `research-input-votes` CI passed at `3af76f4c` (run 34717368874). The legacy `dataset-tools` CI passed at `1e8fc2a8` (run 34717837777).

At `1e8fc2a8`, `research-pv` run **34717837751** initially failed only the window/hop CPU relative gate: Transient worst p99/deadline 0.525, legacy 1024/128 worst 0.413, ratio **1.271186 >1.25**. General was 0.721 in that window benchmark. Correctness, compiler, sanitizer, pitch/formant and tonal tests passed. The initial artifact and timing CSVs were preserved.

The unchanged-code rerun completed successfully: **all seven jobs passed**, including the window/hop gate and subsequent Multi-resolution CPU gate (retry job 103618502013). Three additional unchanged local window-benchmark repeats also passed the original limits. No DSP or threshold was changed. Non-reproduction on retry does not prove a root cause; the initial failure remains part of this record.

## Listening artifact and remaining promotion gates

Generated **18 harmonic trials**: one seeded source from each original category, six pitches each, with balanced A/B/C permutations. The listener package contains 54 anonymous candidates plus 18 unshifted source references, an HTML player and blank numeric ratings. Listening-only audio uses capped RMS matching, common 0.95 peak headroom and PCM16. Raw evaluated audio remains untouched. The answer key is packaged separately; do not open it before listening.

Pack ID: `f60d9dd4b624c88e90f44d980344f9cb174a4bb2638f0e374a6dd511d8e2ce03`.

**No human ratings, four-way held-out comparison, audible peak diagnosis or product promotion has been completed.** The 18-trial pack is supplementary, not a substitute for the requested held-out four-way listening gate. The ±24-st stress pathology was not changed or requalified. Manual mode selection remains intact.

## Reproduction

Keep original and rendered audio local; do not commit dataset audio or MOS files.

```sh
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
cmake -S research/cpp_pv_rt -B build/reference -G Ninja \
  -DCMAKE_BUILD_TYPE=Release -DCMAKE_CXX_STANDARD=20
cmake --build build/reference -j 2
ctest --test-dir build/reference --output-on-failure
export BOILED_EGG_PV_CLI="$PWD/build/reference/boiled_egg_pv_rt_cli"
export BOILED_EGG_MULTIRES_CLI="$PWD/build/reference/boiled_egg_multires_rt_cli"
python -W error::ResourceWarning -m unittest discover -s research -p 'test_*.py' -v
python -W error::ResourceWarning -m unittest -v eval/test_tsm_dataset.py

# Expected exit 2 for the supplied archives: required test references are absent.
python research/audit_tsm_inputs.py \
  --ref-zip 'ref_train(1).zip' --test-zip 'test(2).zip' \
  --scores 'TSM_MOS_Scores(2).csv' --output input-audit.json --require-four-way

python research/eval_reference_profiles.py \
  --pv-cli "$BOILED_EGG_PV_CLI" --multires-cli "$BOILED_EGG_MULTIRES_CLI" \
  --ref-dir data/ref_train --catalog 'TSM_MOS_Scores(2).csv' \
  --source-commit "$(git rev-parse HEAD)" \
  --corpus-label 'ref_train exploratory; not ref_test' \
  --formants off harmonic monophonic --workers 3 --output results/reference-all-formants
python research/report_reference_peaks.py \
  --evaluation results/reference-all-formants --ref-dir data/ref_train \
  --output results/reference-peaks
python research/make_reference_profile_pack.py \
  --evaluation results/reference-all-formants --ref-dir data/ref_train \
  --formant harmonic --per-category 1 --seed 20260913 --output results/listening-18
# After an actual listener exports numeric scores from the player:
python research/summarize_profile_ratings.py \
  --answer-key results/listening-18/analyst/answer_key.json \
  --ratings listener-scores.csv --output results/listening-summary.json
```

Metrics CSV SHA256: `429204ad08f79a5358e93f27d9160ebad2100b895c9042b309866c359a875793`.
Evaluation summary SHA256: `5522e2758b3e6cf74d092241d083f4eefddd5efb5d94ad67e42f13bff6b4b762`.
PV renderer SHA256: `e14edf1efec1e740a62381e0f87400faf6f997aac83e966ed689c001af421f9d`.
Multi-resolution renderer SHA256: `9089ef3fb600b89f06305f9b56ef124496db236edd6408c770bb1f2f4f9d035c`.
