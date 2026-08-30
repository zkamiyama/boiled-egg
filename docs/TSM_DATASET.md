# Roberts/Paliwal TSM dataset benchmark

This integration evaluates boiled egg against the **test portion** of the Roberts/Paliwal time-scale-modification dataset. The local input consists of:

- `ref_test.zip` — 20 reference signals;
- `test.zip` — 240 processed signals;
- `TSM_MOS_Scores.csv` — subjective scores for the full dataset.

The audio and score files are intentionally not committed. Keep them under a local, gitignored path.

## One-command run

From a clean checkout after placing the three downloads in `/mnt/data`:

```bash
./scripts/run_tsm_benchmark.sh
```

Override locations when necessary:

```bash
REF_ZIP=/path/ref_test.zip \
TEST_ZIP=/path/test.zip \
SCORES=/path/TSM_MOS_Scores.csv \
DATASET=$PWD/data/external/tsm_test \
RESULTS=$PWD/results/tsm_test \
./scripts/run_tsm_benchmark.sh
```

## Outputs

The importer writes:

- `data/external/tsm_test/manifest.csv`;
- `data/external/tsm_test/IMPORT_REPORT.json`.

The benchmark writes:

- `results/tsm_test/baseline_metrics.csv`;
- `results/tsm_test/boiled_egg_metrics.csv`;
- `results/tsm_test/boiled_egg_metrics_with_proxy_mos.csv`;
- `results/tsm_test/mos_proxy_cross_validation.csv`;
- `results/tsm_test/summary.json`;
- `results/tsm_test/SUMMARY.md`.

## Metrics and caveats

The metrics compare time-normalized STFT, chroma, envelope and onset representations, with a small global normalized-time alignment. They are useful for regression localization, but no single metric is treated as perceptual ground truth.

The generated “proxy MOS” is a ridge model trained on the 240 labelled test signals and checked with leave-one-reference-out validation. It is explicitly an **engineering triage signal**, not the published OMOQ, not a new listening test, and not evidence of parity with any commercial product.

Acceptance of a DSP backend requires all of the following:

1. matched, randomized blind listening tests;
2. no-allocation and sanitizer gates;
3. deterministic host-block behavior;
4. transient, harmonic, stereo and anti-alias regressions;
5. callback p99/deadline measurements on representative CPUs.
