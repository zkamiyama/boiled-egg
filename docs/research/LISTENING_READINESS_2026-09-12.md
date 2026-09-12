# Listening readiness and peak-audit checkpoint — 2026-09-12

## Scope and status

Work resumed on `research/formant-v0.3-integrated` from verified HEAD `dd04c9388443ff3358af34b85ca5a5c880f45e71`. This checkpoint changes listening/evaluation tooling only. No DSP, public ABI, wrapper, host adapter, profile policy or product-main code was changed or promoted.

The current 1024/256 + 512/192 multi-resolution candidate remains research-only. Read `research/cpp_pv_rt/MULTIRES_RESULTS.md`, `FORMANT_RESULTS.md` and `ELASTIQUE_PITCH_RESULTS.md` for the earlier corpus results; this session did not repeat those corpus experiments.

The Roberts/Paliwal `ref_test.zip`, `test.zip` and `TSM_MOS_Scores.csv` were not available. They have been requested from the user. No substitute corpus, real four-way listening result, real peak-outlier ranking or perceptual-quality claim is reported here. Synthetic audio below tests software correctness only. The near-+24-st peak pathology is unchanged.

## Four-way blind-pack integrity fixes

`research/make_blind_multires_pack.py` previously chose the nearest percent-named render directory when an exact directory was absent. It also discarded render sample rates and checked frame count but not channel count. Either behavior could invalidate a comparison without an obvious error.

The tool now:

- joins conditions using exact Decimal numeric identity: `150`, `150.0` and `1.5e2` are equivalent, but a nearby factor is not;
- rejects duplicate/ambiguous conditions, missing target-range pairs, inconsistent category/pitch metadata, non-finite metrics, invalid selection counts and empty selections;
- rejects empty/non-finite audio and mismatched sample rates, frames or channels;
- validates every selected trial before writing listening audio, with memory bounded to one trial;
- refuses to mix new results into a nonempty output directory.

The original objective-score ranking, category selection, deterministic randomization, A–D labels, separate answer key and capped RMS matching/common headroom remain unchanged. This is not a redesign of the listening protocol. Other historical two-way/offline tools were not changed.

The selection remains a target-range diagnostic subset, not a guarantee of all six requested pitch cells or equal category counts when source availability differs. Derived TSM conditions must not be relabeled as exact ±3/±7/±12-st trials.

## Raw peak outlier audit

New tool: `research/report_peak_outliers.py`.

```sh
python3 research/report_peak_outliers.py \
  --general-metrics /data/general/metrics.csv \
  --general-renders /data/general/renders \
  --transient-metrics /data/transient/metrics.csv \
  --transient-renders /data/transient/renders \
  --multires-metrics /data/multires/metrics.csv \
  --multires-renders /data/multires/renders \
  --ref-dir /data/references \
  --output /data/peak-audit
```

Paths above are placeholders for actual evaluator outputs. Output must be absent or empty. The four-way pack uses the same six metrics/render arguments and reference directory; invoke `research/make_blind_multires_pack.py` with a separate output directory and the desired `--per-category` / `--seed`.

Input schema follows the existing realtime four-way pack. General/Transient rows use `stem, category, percent, semitones, system, env_rmse_db, onset_corr`; selected systems are harmonic and the General-derived Elastique row. Realtime multires rows use `stem, category, percent, semitones, env, onset`. This is not the historical offline `eval_multiresolution.py` output schema.

All available complete target-range conditions are audited, without the listening selector's per-category truncation. Sample peak, RMS, dBFS, crest factor, peak ratios versus reference and Transient, RMS deltas, crest delta, peak time/channel and frame/channel metadata are measured from the raw WAVs before level matching. Envelope/onset values are copied from the supplied evaluator CSVs, not recomputed. Input CSVs, references and rendered WAVs are SHA-256 fingerprinted; source audio is never rewritten.

Outputs:

| File | Meaning |
|---|---|
| `all_conditions.csv` | Every in-range four-system measurement |
| `peak_outliers.csv` | Review-flagged rows, ranked by peak ratio versus Transient, then peak |
| `excluded_stress.csv` | Out-of-range metadata; stress audio is not evaluated here |
| `summary.json` | Provenance, counts, actual pitch coverage and missing requested pitch cells |

Default flags are raw peak >1.0 or peak ratio versus Transient >1.10, plus nonzero output against a silent reference/baseline. These are investigator-review thresholds, not pass/fail quality gates. A sample above 1.0 or a larger peak does not itself prove an audible artifact. Undefined silence ratios/dB values remain null in JSON or blank in CSV; no invented floor is used. Every row starts with `artifact_assessment=not_listened` and blank listening notes.

The target boundary is 12.0 st plus the existing 0.0001-st tolerance. Coverage lists missing requested cells {-12, -7, -3, +3, +7, +12} per category using 0.0001-st matching. It reports gaps rather than inventing or resampling missing comparisons. Derived Elastique remains a TSM-plus-offline-resampling engineering diagnostic, not native Elastique pitch-shifter output.

## Local Linux validation

Environment: Linux 6.18.35 x86_64, Python 3.13.5, GCC 14.2.0, Clang 17.0.0.

The research source was retrieved from Actions run `34699431257`, artifact `10299856429` (`formant-linux-x64`), generated at commit `3113b7c571ed1b249fa87bd097409a975f81ba64`. Archive SHA-256: `d4bb62fecf256866b95fcbea2d737e46dc1dbaa9897c2ffed3fe0fbebfe45254`. The complete reconstructed `research/cpp_pv_rt` Git tree hash was verified as `90c529959f21dad1053b4683251c134bea88657d`, identical to the starting research source. Binaries were rebuilt locally, not merely taken from the artifact.

| Validation | Result |
|---|---|
| Blind-pack tests | 15/15 pass |
| Raw peak-audit tests | 6/6 pass |
| GCC C++20 Release, -O3 | 6/6 CTest pass |
| GCC C++23 Release, -O3 | 6/6 CTest pass |
| Clang C++20 Release, -O1 | 6/6 CTest pass |
| Clang C++23 Release, -O1 | 6/6 CTest pass |
| Clang C++20 ASan + UBSan, -O1 | 6/6 CTest pass; leak detection enabled |

Each six-test C++ suite covers PV and multires processing, allocation-free hot paths and pure-C consumers. An initial combined build invocation hit the execution timeout during Clang compilation; the completed local Clang runs above explicitly used -O1, not an unverified -O3 result.

Existing unchanged synthetic DSP evaluations also passed:

- Low-frequency multires safety: 15 conditions; maximum pitch error **2.153085 cents**, minimum target/spur **23.006126 dB**, maximum peak **0.422484**. Existing limits are 3 cents and 22 dB, with finite exact-duration output.
- High-band modulation: 12 conditions; worst 95% ripple **0.143867 dB** versus the 0.25-dB gate, worst 99% ripple **0.162141 dB**, maximum steady peak **0.201716**.
- Formant/pitch synthetic evaluator: maximum pitch error **0.00309535 cents**, linked-stereo relative RMS error **4.45020e-5**; pitch renders had exactly 96000 frames. Intended harmonic and monophonic fixtures improved versus off.

Reproduce the Python tests from the repository root:

```sh
python3 -m py_compile research/make_blind_multires_pack.py research/test_blind_multires_pack.py \
  research/report_peak_outliers.py research/test_peak_outliers.py
python3 -W error::ResourceWarning -m unittest -v \
  research/test_blind_multires_pack.py research/test_peak_outliers.py
```

For a standalone GCC build, repeat with `CMAKE_CXX_STANDARD=20` and `23`:

```sh
cmake -S research/cpp_pv_rt -B build-research-gcc20 -G Ninja \
  -DCMAKE_BUILD_TYPE=Release -DCMAKE_C_COMPILER=gcc -DCMAKE_CXX_COMPILER=g++ \
  -DCMAKE_CXX_STANDARD=20 -DCMAKE_CXX_EXTENSIONS=OFF
cmake --build build-research-gcc20 -j 2
ctest --test-dir build-research-gcc20 --output-on-failure
```

Clang runs used `clang`/`clang++` and `-DCMAKE_CXX_FLAGS_RELEASE='-O1 -DNDEBUG'`. The sanitizer build used Debug, `-fsanitize=address,undefined -fno-omit-frame-pointer -O1` for C/C++, sanitizer executable-link flags, `ASAN_OPTIONS=detect_leaks=1` and `UBSAN_OPTIONS=halt_on_error=1`.

## Small-block callback baseline: three pinned repetitions

The unchanged `boiled_egg_multires_rt_bench` was rebuilt with GCC C++20 Release. Three sequential runs were pinned to logical CPU 0, after other build/evaluation work completed. Each run covered 48/96 kHz, 32/64/128/256-frame blocks and pitch ratios 0.6674199/1.4983071, mono with harmonic formants. Each condition records 1400 callbacks after 200 warmup callbacks.

Thread-CPU p99/deadline, median across three runs (min–max in parentheses):

| Rate | Block | Pitch ~0.6674 | Pitch ~1.4983 |
|---|---:|---:|---:|
| 48 kHz | 32 | 0.471 (0.470–0.473) | 0.478 (0.478–0.479) |
| 48 kHz | 64 | 0.249 (0.242–0.305) | 0.391 (0.320–0.405) |
| 96 kHz | 32 | 0.951 (0.941–1.095) | 0.956 (0.945–1.022) |
| 96 kHz | 64 | 0.515 (0.492–0.748) | 0.508 (0.491–0.729) |

At 96 kHz/32 frames, individual repetitions exceeded a deadline ratio of 1.0. This checkpoint therefore does **not** establish reliable 32-frame realtime headroom. It is a shared-VM baseline, not a portable guarantee or a speed improvement over the previous machine. There is no hop-128/192 A/B experiment in this session. Raw wall-clock and thread-CPU rows for all 16 conditions and all three runs are retained in the session validation bundle.

## GitHub CI and commits

At tooling commit `b6774b800af26c9054a932404680c7763e99e66e`, both `ci` (run `34699732889`) and `research-listening-tools` (run `34699732890`) completed successfully. The latter now compiles and runs all 21 listening/audit tests. Research run `34699431257` at `3113b7c` also passed all GCC/Clang C++20/23, sanitizer, independent Python-formant and pitch/formant/tonal/callback jobs.

Small commits made before this documentation checkpoint:

| Commit | Change |
|---|---|
| `148ca96` | Blind-pack condition and audio validation |
| `a7c98e3` | Correct standard-envelope column transcription in preceding change |
| `3113b7c` | Blind-pack validation regression tests |
| `ec2b157` | Raw peak audit and coverage report |
| `531d26f` | Peak-audit regression tests |
| `b6774b8` | Listening/audit CI gate |

## Still required before promotion

Obtain the actual reference/test archives and MOS mapping, regenerate matching raw evaluator outputs, inspect coverage, then generate the four-way listener pack with the answer key kept separate from the listener. Audit raw peaks before RMS matching, and listen specifically for crossover coloration, high-band phase texture, pumping, sibilance, breath and acoustic/percussive transients. Do not infer actual artifacts from review flags alone.

No product profile naming decision, manual/Auto policy change, formant-policy merge, product-main merge or wider-range promise is made by this checkpoint.
