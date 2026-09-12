# Fuzzy-PV retry: held-out evaluation and exact optimization — 2026-09-13 JST

## Decision

The causal Fuzzy-PV implementation is functional and reproducibly tested, but it has **not earned replacement of Multi-resolution or product promotion**. On the exact six-pitch grid, it slightly improves the broad-envelope diagnostic relative to Transient; Multi-resolution remains substantially stronger on the onset diagnostic. There are no human listening results. The median-filter optimization reduces Fuzzy p99 callback time by about 32% without changing any of the 1,200 replayed Fuzzy WAVs. Nevertheless, 96 kHz stereo/32-frame callbacks still exceed their deadline in this VM. These conclusions concern this causal adaptation, not the full published FPV method.

No product core, public product ABI, wrappers, state format, adapters or main branch were modified. No automatic profile selection was introduced. The isolated overlap-guard experiment was not applied. The existing extreme-upshift pathology remains outside the primary +/-12-semitone target.

## Source provenance and implementation

The retry found existing Fuzzy implementation, tests, resumable evaluation and listening tools at branch HEAD `fcae6c8bfe6083ebbfa943d9cb9181b40c78900b`; these were resumed, not overwritten or claimed as newly invented during the retry.

| Retry commit | Change |
|---|---|
| `f71cc1d6f1b26f74d1f95cd7dbdc5e7a3d935912` | Exact source replay with per-file SHA256 checksums |
| `464139ee9949ad699a5127775115ff1d855a7d66` | Bounded rolling time/frequency medians in `fuzzy_phase.hpp` |
| `f215aa515f8bfb6101729b2f35d2d02e66fb64c2` | Independent full-sort oracle regression |
| `03557edc3c06447aa836991e56f5631b1ea74ad7` | Byte-exact corpus replay tool |
| `dc153c3315eac17876b42f42b061db82ffebb27c` | Replay failure, tamper and block-size tests |

The validated code tree at `dc153c3` is `3459862783ae0a9a7dba7d4c046acc30a306421e`; the local tracked tree matched it exactly. The subsequent report commit changes documentation only.

The starting source replay `f71cc1d6` was built before optimization and used for the complete corpus. The optimized DSP is the one tested at `f215aa5`; later code commits add only replay tooling/tests. Original evaluation provenance was preserved, not relabeled after optimization.

The inherited implementation draws on Damskagg and Valimaki, *Audio Time Stretching Using Fuzzy Classification of Spectral Bins*, Applied Sciences 7(12), 1293 (2017), DOI `10.3390/app7121293`. It is explicitly a **causal research adaptation**, not a faithful reproduction: trailing nine-frame time median, bounded frequency median, shared linked-channel phase rotation, deterministic per-instance noise phase perturbation, and protection of tonal peak lobes. It does not implement the paper's full transient magnitude suppression/compensation and transient-center lookahead.

Two explicit modes remain available: `fuzzy-noise` without local onset resets, and `fuzzy` with the additional local soft-reset ablation. Off/Harmonic/Monophonic formant policies remain independent. Stationary unity reconstruction, silence, channel linkage, reset and block partitioning are tested.

The optimization maintains sorted time windows by replacing the outgoing ring value, and slides a sorted frequency window with one eviction/insertion per bin. All loops remain bounded; no processing allocation is introduced. Extra preallocated sorted-history storage is 18,468 bytes at FFT1024 or 36,900 bytes at FFT2048, excluding vector overhead. It does not alter classification values, phase policy or the existing resampler.

## Missing inputs resolved and comparison scope

The supplied `ref_test(1).zip` contains **20 mono references at 44.1 kHz**. Every one of the **240** supplied processed files exactly matches a row of the **5,520-row** score catalog, and all required reference names are now present: **240/240 paired, zero missing**. `audit_tsm_inputs.py --require-four-way` exits 0. Processed methods are Elastique/FuzzyTSM/NMFTSM, 80 each.

The held-out catalog's `ref_loc` category is `objective` for these 20 sources; it is retained. The separate `review_category` is the existing filename map for voice/solo/polyphonic/mix, used for listening coverage, not an audio classifier. The earlier 88 training references are not substituted or pooled into this evaluation.

Time ratio is 1.0; original render block is 256. The five DSP profiles are General 2048/256, Transient 1024/256, existing Multi-resolution 1024/256 + 512/192, Fuzzy-noise 1024/256 and Fuzzy 1024/256. All three formant policies are evaluated.

| Grid | Conditions | DSP WAVs | Derived-baseline WAVs |
|---|---:|---:|---:|
| Exact -12, -7, -3, +3, +7, +12 semitones | 120 | 1,800 | 0 |
| Measured Elastique ratios within +/-12 semitones | 60 | 900 | 60 |
| Measured ratios outside the target, stress only | 20 | 300 | 20 |
| **Total** | **200** | **3,000** | **80** |

All **3,080/3,080** outputs were finite and had exact reference frame counts, sample rates and channel counts. A separate readback verified every source/render hash and remeasured Peak/RMS against the CSV, using the evaluator's float64 RMS arithmetic.

The derived baseline is the supplied pitch-preserving Elastique TSM output followed by exact-length **Fourier resampling**. It is **not native Elastique pitch-shifter output**. Its measured ratios are not relabeled as the exact six-pitch grid. No supplied MOS label is transferred to any newly rendered signal; FuzzyTSM and NMFTSM files are inventoried, not treated as matched native pitch baselines.

## Objective results

Harmonic policy, exact 120 conditions; candidate minus Transient. Lower envelope-error delta and higher onset-correlation delta are better.

| Candidate | Mean envelope delta, dB | Mean onset delta | Envelope wins | Onset wins |
|---|---:|---:|---:|---:|
| General | +0.614237 | -0.173989 | 22/120 | 2/120 |
| Multi-resolution | +0.000149 | +0.019594 | 49/120 | 99/120 |
| Fuzzy-noise | -0.008695 | +0.000271 | 72/120 | 65/120 |
| Fuzzy | -0.011260 | +0.000555 | 77/120 | 62/120 |

Directly against Multi-resolution, Fuzzy's mean envelope delta is -0.011408 dB, but its mean onset delta is -0.019039 and it wins only 21/120 onset comparisons. These small envelope differences do not establish perceptual superiority. The current tests do not settle breath, sibilance, cymbal texture or transient naturalness; those need listening.

The measured-ratio target subset independently reproduces the earlier Multi-resolution result: mean envelope delta versus derived Elastique **-2.244228 dB**, 59/60 envelope wins; onset delta **-0.016780**, 30/60 onset wins. Fuzzy's corresponding deltas are -2.247697 dB and -0.030443, with 26/60 onset wins. Do not combine this subset's denominators with the exact-grid results.

### Raw peak inspection

On the harmonic exact grid, Fuzzy's maximum sample peak is **1.621937**, versus Multi-resolution **1.753434** and Transient **1.749154**. However, Fuzzy's 95th-percentile peak ratio versus Transient is **1.143889**, and 12/120 conditions exceed 1.1 times Transient. A lower absolute maximum does not mean every condition is improved.

Across all three formant policies and both target grids, the raw audit flags **1,119/2,700 DSP rows** for sample peak above 1.0 or ratio above 1.1 versus Transient. The separate stress grid flags **157/300**. These are requests for inspection, not confirmed audible defects. No raw waveform was normalized or limited; sample peaks are not reconstructed true peaks.

Extreme-upshift stress remains unsafe: harmonic maxima include **17.397017** for Multi-resolution and **8.881354** for Fuzzy. This retry does not fix, promote or guarantee that range.

## Correctness, replay and quality gates

Local environment: GCC14.2, Clang17, Python3.13.5, NumPy2.3.5, SciPy1.17.0, SoundFile0.13.1, Linux x86_64. Logs and exact executable hashes are retained in the validation bundle.

| Validation | Result |
|---|---|
| GCC C++20 and C++23 Release | 9/9 CTests each |
| Clang C++20 and C++23 Release | 9/9 CTests each |
| Clang ASan+UBSan, leak detection | 9/9 CTests |
| Research Python plus legacy dataset tests | 139 + 6 = **145 passed**, no skipped tests |
| Rolling medians versus independent full-sort oracle | **1,151,160 bit-identical membership values** |
| Optimized Fuzzy corpus replay at block32 versus original block256 | **1,200/1,200 entire WAV files byte-identical** |
| Pure C consumers and allocation-free processing | Included in the CTests |
| Reset, linked/antiphase stereo, silence, exact duration and partition invariance | Passed |
| 48/96 kHz tones with explicit window scaling | **162 cases, zero failures** |
| Existing Multi-resolution low/high-band gates | Passed; high-band worst p95 ripple **0.143867 dB** |

The exact replay covers both Fuzzy modes, all three formant policies, exact pitches, measured target ratios and stress ratios. It is an optimization equivalence test, **not proof that the original sound is good**.

### Important rejected configuration: fixed FFT1024 at 96 kHz

A deliberately unscaled 96 kHz test produced **18 failures out of 81 cases**, six low-tone failures for each of Transient, Fuzzy-noise and Fuzzy. The 55 Hz/-12-semitone case reached about **1,124 cents** error. This is retained as negative evidence, not hidden by loosening thresholds.

The passing 48/96 kHz quality matrix explicitly uses **FFT1024/hop256 at 48 kHz and FFT2048/hop512 at 96 kHz**. Fuzzy modes then have maximum measured error 2.153085 cents, minimum target/spur ratio 22.918007 dB, and maximum high-band p95 ripple 0.007548 dB across the tested cases. These are limited synthetic gates, not universal quality guarantees. No default configuration was silently changed.

## Callback measurements

Three alternating baseline/optimized repetitions, same VM, CPU0 affinity, after our corpus/build workloads. Each repetition covers 144 cells: 48/96 kHz, mono/stereo, 32/64 frames, six target pitches, and Transient/Fuzzy-noise/Fuzzy. The benchmark uses the explicit quality-tested window scaling above and Harmonic formants. It records thread-CPU and wall timing after warmup; 1,400 measured callbacks per cell.

The median p99 CPU-time reduction across the 48 paired cells per mode is **32.10% for Fuzzy** and **32.46% for Fuzzy-noise**. The legacy Transient control changes by 1.03%. Below, each number is the worst across six pitches of the per-cell median p99/deadline over three repetitions, for Fuzzy.

| Rate / channels / block | Before | Optimized |
|---|---:|---:|
| 48 kHz / mono / 32 | 0.435 | 0.267 |
| 48 kHz / stereo / 32 | 0.508 | 0.362 |
| 96 kHz / mono / 32 | 1.530 | 0.996 |
| 96 kHz / mono / 64 | 0.797 | 0.533 |
| 96 kHz / stereo / 32 | 2.020 | **1.408** |
| 96 kHz / stereo / 64 | 0.985 | 0.802 |

A value above 1 exceeds the callback deadline. All six 96 kHz stereo/32-frame Fuzzy cells still exceed it; mono/32 has negligible headroom in the worst case. This is a shared-VM diagnostic, not a portable hard-realtime claim. The new storage and classification work remain costs relative to ordinary phase locking. No CPU threshold was relaxed.

At code checkpoint `dc153c3`, hosted `research-fuzzy` run **34723219649** passed Python3.11 and3.13; the scaled tonal job runs once under3.13. `research-pv` run **34723219665** passed all seven jobs, including compiler/sanitizer/quality and existing callback gates. Product `ci` run **34723219652** completed successfully, including TSan, CLAP, VST3 validator and package/consumer checks. These product checks do not exercise a promoted Fuzzy product backend: no such promotion occurred.

## Listening artifacts

Two distinct harmonic packs were generated with seed20260913 and separate analyst keys:

- **24 exact-grid trials:** Transient / Multi-resolution / Fuzzy-noise / Fuzzy; one source from each of the four existing review categories, six exact pitches per source.
- **12 measured-ratio trials:** General / Transient / Multi-resolution / derived Elastique; one source per review category, three available target ratios per source. This is not an exact +/-3/7/12 four-way pack.

Listening copies use capped +/-6 dB RMS matching, common 0.95 peak headroom and PCM16. The unshifted reference is for source timbre, not a pitch-matched hidden anchor. The browser exports winner selections for overall, attack and timbre/noise naturalness. Blank exports were verified as **0/72 and 0/36 submitted criterion votes**, with correct pack identity and no invented scores. All 186 listener files passed their stored hashes; both listener ZIPs and the separate key ZIP passed CRC checks.

**No human ratings have been collected.** Keep the analyst key and validation bundle away from listeners until judging is finished.

## Reproduction and evidence identity

Build from the repository root; keep dataset and generated audio local, never commit them.

```sh
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
cmake -S research/cpp_pv_rt -B build/fuzzy -G Ninja \
  -DCMAKE_BUILD_TYPE=Release -DCMAKE_CXX_STANDARD=20
cmake --build build/fuzzy -j 2
ctest --test-dir build/fuzzy --output-on-failure
export BOILED_EGG_PV_CLI="$PWD/build/fuzzy/boiled_egg_pv_rt_cli"
export BOILED_EGG_MULTIRES_CLI="$PWD/build/fuzzy/boiled_egg_multires_rt_cli"
python -W error::ResourceWarning -m unittest discover -v -s research -p 'test_*.py'
python -W error::ResourceWarning -m unittest -v eval/test_tsm_dataset.py
python research/check_fuzzy_quality.py --cli "$BOILED_EGG_PV_CLI" \
  --rates 48000 96000 --scale-window --output results/fuzzy-tonal
python research/run_fuzzy_batches.py \
  --pv-cli "$BOILED_EGG_PV_CLI" --multires-cli "$BOILED_EGG_MULTIRES_CLI" \
  --ref-dir data/ref_test --test-dir data/test --catalog data/TSM_MOS_Scores.csv \
  --source-commit "$(git rev-parse HEAD)" --formants off harmonic monophonic \
  --workers 2 --output results/fuzzy-corpus
# Interrupted runs require explicit --resume with identical inputs/config/code.
# Full-sort versus optimized replay requires the ORIGINAL saved corpus:
python research/check_fuzzy_replay.py --evaluation results/original-fuzzy-corpus \
  --ref-dir data/ref_test --cli "$BOILED_EGG_PV_CLI" \
  --source-commit "$(git rev-parse HEAD)" --block 32 --workers 2 \
  --output results/replay.json
```

Original corpus metrics SHA256: `086059f3260752498805d5efccc1178ac2dab0f20c57e9db45c00a4c9dd3df27`.
Original corpus summary SHA256: `ecf31b9dccb672ca3e501372321845e94d9f6f0e103c742b1a29dad0361614a1`.
Candidate pack ID: `c61f6769cc413923324f34c8c83d4737b85e7f5472af6c8012bab5dd5521165d`.
Derived pack ID: `1a811e5c81787f9f95a3d767cdf5da4a1ed47064258de6ae78ac431f570c9896`.

The analyst bundle retains original and optimized source snapshots, input inventory, complete metrics/summary, raw peak review, replay hashes, all callback repetitions, local test logs, the successful scaled tonal results and the failed unscaled diagnostic. It does not redistribute the full 1.8 GB raw render corpus or the source MOS catalog. Rebuilding on another compiler/machine need not reproduce WAV bytes or timing; the bit-exact statement above refers to the recorded same-toolchain comparison.
