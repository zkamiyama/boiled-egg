# Reference-profile implementation and validation — 2026-09-13 (JST)

## Scope and source provenance

This checkpoint adds reference-only evaluation, a blind-listening player and rating import, raw peak review, regression tests and CI. **No C++ DSP, product ABI, host adapter, state format or main-branch implementation was changed. No research backend was promoted.** Manual profile selection and orthogonal formant policy remain unchanged.

The session began from research branch HEAD `73b85283953c009be6ea8e7083dd96c8b1586ad3`, not the older handoff HEAD. The initial local source replay was `d0160627f55b56b9ae7d2bc49c6e5ba0ca7ac356`. The complete final validation snapshot is `a370f521e63b8ffb857f916a5905c4b31e9e70ee`; every file in `research/cpp_pv_rt` was byte-identical between the built source and this snapshot. Replay archives include commit/tree IDs, tracked files and SHA256 checksums. Concurrent additive input/vote and peak-audit changes on the same branch were preserved and included in the final tests.

The real-corpus evaluator records `c4745070ecccf6699e71a4f43a9b2a5347f11c7a`, the then-current evaluator checkpoint, and the actual renderer hashes. Its evaluator and DSP files are unchanged in the final snapshot. Later commits added audits, tests and CI only.

## Supplied data: exact join, not a replacement held-out set

The uploaded reference archive contains **88 training references**. The uploaded processed archive contains **240 test renders**, all matched by exact `test_name` to the **5,520-row** MOS CSV. Those 240 rows require **20 different references**, of which **zero** are present in the training archive. The processed subset contains 80 Elastique, 80 FuzzyTSM and 80 NMFTSM files.

`audit_tsm_inputs.py --require-four-way` correctly exits **2** with `0/240 paired; 20 references missing`. This is an expected input-readiness block, not a software test failure. The missing input for the original comparison remains `ref_test.zip`.

The 88 available sources are evaluated separately. Catalog `ref_loc` categories are preserved: **31 solo, 27 music, 30 voice**. They are not inferred from audio or reassigned using held-out filenames. All sources are 44.1 kHz: **13 mono and 75 stereo**. Music is not silently split into mix/polyphonic subclasses. No MOS values are applied to newly rendered audio, and no derived-Elastique baseline is fabricated from these unmatched files.

## Implemented tools

`eval_reference_profiles.py` evaluates the exact six-pitch grid for General, Transient and Multi-resolution, with explicit off/harmonic/monophonic formant choices. It preflights sources, checks finite samples, rates, channels, exact duration, catalog/source/renderer hashes and grid completeness, and publishes only complete output through a staging directory. Envelope/onset metrics are measured separately per channel and then averaged, avoiding antiphase downmix cancellation.

`make_reference_profile_pack.py` chooses a seeded source sample within each original category, includes every requested pitch, balances all six A/B/C label permutations per source, and separates `listener/` from `analyst/`. The local HTML player exports four 1–5 ratings: overall, attack, formant naturalness and stability. The unshifted reference is a source/timbre reference, not a pitch-matched hidden anchor. Playback files use capped RMS matching, common 0.95 peak headroom and PCM16; raw evaluation WAV files are never normalized or limited.

`summarize_profile_ratings.py` validates pack IDs, complete score fields, labels, listener IDs and duplicates. Only complete A/B/C triplets enter comparisons, with equal listener weight. Partial coverage remains explicit. Blank templates produce `not_listened`, null scores and no automatic promotion decision. This rating format is separate from the existing four-way vote tools.

`report_reference_profile_peaks.py` remeasures raw audio and reports source/profile/pitch, peak ratios, RMS deltas, envelope/onset and peak locations without calling a review flag an audible defect. The concurrently added `report_reference_peaks.py` additionally requires CSV peak/RMS to agree with the fingerprinted WAVs. Both were exercised on the real evaluation and yielded **261 flagged profile rows** under the same numerical thresholds.

CI `research-reference-profiles.yml` builds the real C++ renderers and runs all research Python unit tests under Python 3.11 and 3.13. Tests cover real rendering, missing/duplicate grids, tampering, metadata mismatches, antiphase metrics, path escape, blind-key separation, balanced randomization, empty/partial/invalid ratings, silence handling and actual player-JavaScript CSV export through Node.

## Real-audio evaluation

Harmonic formant policy only in this real-corpus pass; time ratio 1.0; block 256; pitches **−12, −7, −3, +3, +7, +12 semitones**. The float32 pitch controls, renderer hashes and source hashes are recorded in the evaluation manifest.

**88 × 6 × 3 = 1,584 renders**, representing 528 paired conditions. Every render was finite and had the expected sample rate, channel count and exact frame count: **1,584/1,584**.

| Candidate vs Transient | Mean envelope-error delta, dB (lower is better) | Mean onset-correlation delta (higher is better) | Envelope wins | Onset wins |
|---|---:|---:|---:|---:|
| General | +0.548853 | −0.168329 | 77/528 | 5/528 |
| Multi-resolution | +0.000804 | +0.017757 | 202/528 | 457/528 |

The Multi-resolution envelope mean is effectively tied with Transient in this diagnostic, not uniformly better. Its onset diagnostic improves in 86.6% of conditions. These are engineering measurements, **not listening preferences or a native Elastique comparison**.

| Original category | Conditions | Multi-resolution mean envelope delta vs Transient | Mean onset delta | Onset wins |
|---|---:|---:|---:|---:|
| music | 162 | −0.000056 dB | +0.017340 | 139/162 |
| solo | 186 | +0.001656 dB | +0.018737 | 159/186 |
| voice | 180 | +0.000697 dB | +0.017119 | 159/180 |

Do not pool these multichannel training-reference measurements with the earlier 20-reference held-out results.

## Raw peak review

Review thresholds are raw sample peak >1.0 or peak ratio vs Transient >1.1. They are inspection flags, not clipping in the floating-point files and not automatic artifact verdicts. True-peak reconstruction is not part of this audit.

| Profile | Maximum sample peak | Conditions above 1.0 | Peak ratio vs Transient >1.1 | Flagged rows (union) |
|---|---:|---:|---:|---:|
| General | 1.616645 | 72 | 72 | 121 |
| Transient | 1.415421 | 64 | 0 | 64 |
| Multi-resolution | 1.411207 | 65 | 11 | 76 |

All three absolute maxima are `Synth_Bass_1`, −3 st. The worst Multi-resolution/Transient peak ratio is **1.451576×**, `Shaker_01`, +12 st; its raw peak is only 0.410251 and RMS difference is +0.402799 dB. The 95th-percentile Multi-resolution/Transient peak ratio is **1.048909×**. This illustrates why a relative peak flag alone cannot establish an audible failure.

## Validation performed

Local Linux toolchains: GCC 14.2.0, Clang 17.0.0, Python 3.13.5, NumPy 2.3.5, SciPy 1.17.0 and SoundFile 0.13.1.

| Validation | Result |
|---|---|
| GCC C++20 / C++23 Release | 6/6 CTests in each configuration |
| Clang C++20 / C++23 Release | 6/6 CTests in each configuration |
| Clang ASan + UBSan, leak detection | 6/6 CTests |
| Exact final source snapshot, all research Python tests | 111/111, no skips |
| Real-CLI integration inside the Python suite | 54/54 renders: 3 profiles × 6 pitches × 3 formant policies |
| Pure C and allocation-free processing | Included in the six CTests for each build |
| Multi-resolution low-tone gate | Max 2.153085 cents; min target/spur 23.006126 dB |
| High-band modulation gate | Worst p95 ripple 0.143867 dB, below 0.25 dB |
| Synthetic PV pitch gate | Max absolute error 0.003095 cent |
| Linked-stereo formant fixture | Relative relationship error 4.4502e−5 |
| Full reference corpus | 1,584/1,584 finite, exact duration |
| Real peak remeasurement and strict CSV/audio cross-check | Both completed |
| Generated blank ratings | `not_listened`; zero completed triplets |

These validate the research backend and tools. TSan, CLAP smoke and Steinberg VST3 validation were not rerun locally in this session; no product/main/ABI/adapter code was edited.

### Callback measurements

Three sequential repeats of the unchanged Multi-resolution benchmark, pinned to CPU 0 after this session's corpus/build loads finished. Matrix: 48/96 kHz, 32/64/128/256 frames, mono harmonic, pitch ratios approximately 0.667 and 1.498 (±7 st). The following are median thread-CPU p99/deadline ratios across the three repeats:

| Rate / block | Downshift | Upshift |
|---|---:|---:|
| 96 kHz / 32 frames | 0.698 | 0.707 |
| 96 kHz / 64 frames | 0.368 | 0.365 |

The maximum median across the 16-condition matrix was 0.707. Each raw repetition and both CPU/wall measurements are retained. This is a shared-VM, mono, representative-pitch diagnostic, **not a portable real-time guarantee or a full ±12-st CPU guarantee**.

### Hosted CI and the initial relative-CPU failure

The new reference-profile workflow passed both Python versions at code checkpoint `ecdbd9ccebd3a1459bbbc792e528c703eb6a9b45` (run 34717325221). Earlier canceled runs were superseded by subsequent commits.

The existing `research-pv` run 34717325217 initially failed its unchanged window/hop relative CPU gate. Transient worst p99/deadline was **0.351**, legacy hop-128 was **0.273**, and their ratio was **1.285714**, above the existing **1.25** threshold. General was 0.552. Its correctness, compiler, sanitizer, formant and tonal steps passed before that timing failure. The initial CSV artifact is preserved; no DSP or threshold was changed to conceal the failure.

The unchanged-code rerun completed successfully: all seven jobs in run 34717325217 passed, including the window/hop relative gate and Multi-resolution CPU gate (retry job 103617513418). The failure was not reproduced on that retry; this does not prove a root cause or establish hard real-time safety. The original failure is retained rather than discarded.

## Listening artifacts and remaining gates

Generated a **36-trial, three-way** harmonic pack: two sources per catalog category, six pitches per source. There are 108 anonymous candidates plus 36 unshifted references. Listener WAVs, the HTML player, manifest and blank ratings are packaged separately from the answer key. All generated file hashes were verified and both ZIPs passed archive CRC checks.

**No human listening scores have been collected.** The pack is supplementary reference-only evidence and cannot satisfy the held-out four-way General/Transient/Multi-resolution/derived-Elastique gate. That comparison still needs the missing 20 test references. No hearing-quality verdict, product profile promotion, automatic classifier or ±24-st safety claim is made.

## Reproduction

Run from the repository root. Keep user audio and generated WAVs local, never commit them.

```sh
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
cmake -S research/cpp_pv_rt -B build/reference -G Ninja \
  -DCMAKE_BUILD_TYPE=Release -DCMAKE_CXX_STANDARD=20
cmake --build build/reference -j 2
ctest --test-dir build/reference --output-on-failure
export BOILED_EGG_PV_CLI="$PWD/build/reference/boiled_egg_pv_rt_cli"
export BOILED_EGG_MULTIRES_CLI="$PWD/build/reference/boiled_egg_multires_rt_cli"
python -W error::ResourceWarning -m unittest discover -v -s research -p 'test_*.py'

# Returns exit 2 with these supplied archives: required test references absent.
python research/audit_tsm_inputs.py \
  --ref-zip 'ref_train(1).zip' --test-zip 'test(2).zip' \
  --scores 'TSM_MOS_Scores(2).csv' --output input-audit.json --require-four-way

# Use extracted reference WAVs in a flat directory; do not relabel it ref_test.
python research/eval_reference_profiles.py \
  --pv-cli "$BOILED_EGG_PV_CLI" --multires-cli "$BOILED_EGG_MULTIRES_CLI" \
  --ref-dir data/ref_train --catalog 'TSM_MOS_Scores(2).csv' \
  --source-commit "$(git rev-parse HEAD)" \
  --corpus-label 'ref_train exploratory; not ref_test' \
  --formants harmonic --workers 3 --output results/reference-profiles
python research/report_reference_peaks.py \
  --evaluation results/reference-profiles --ref-dir data/ref_train \
  --output results/reference-peaks
python research/make_reference_profile_pack.py \
  --evaluation results/reference-profiles --ref-dir data/ref_train \
  --formant harmonic --per-category 2 --seed 20260913 \
  --output results/reference-listening
# Distribute only results/reference-listening/listener/.
# After a listener exports their scores:
python research/summarize_profile_ratings.py \
  --answer-key results/reference-listening/analyst/answer_key.json \
  --ratings listener-scores.csv --output results/listening-scores.json
```

Evaluation metrics CSV SHA256: `8c01a5478f84b250c0074e6e99b7b72cdb3f3f2f5ddf492f1ce4d860a7386fc7`.
Evaluation summary SHA256: `5974b8f85d195575f513c18e8de7f38e1531e406452ead048dc4b09552a2caba`.
Listener pack ID: `0778064995b334ac5051971f405dc78734523c07af906664016bc4aad7a856d6`.

The accompanying analyst validation bundle retains upload inventory, per-render metrics, both peak audits, compiler/test logs, callback repetitions and the initial failed CI timing artifact. It does not redistribute the full raw evaluation corpus.
