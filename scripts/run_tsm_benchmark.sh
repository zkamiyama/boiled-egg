#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BUILD="${BUILD:-$ROOT/build/release}"
DATASET="${DATASET:-$ROOT/data/external/tsm_test}"
RESULTS="${RESULTS:-$ROOT/results/tsm_test}"

REF_ZIP="${REF_ZIP:-/mnt/data/ref_test.zip}"
TEST_ZIP="${TEST_ZIP:-/mnt/data/test.zip}"
SCORES="${SCORES:-/mnt/data/TSM_MOS_Scores.csv}"

cmake --preset release
cmake --build --preset release
ctest --preset release

python3 "$ROOT/eval/import_tsm_dataset.py" \
  --ref-zip "$REF_ZIP" \
  --test-zip "$TEST_ZIP" \
  --scores "$SCORES" \
  --destination "$DATASET"

python3 "$ROOT/eval/run_tsm_benchmark.py" \
  --dataset "$DATASET" \
  --cli "$BUILD/boiled_egg_cli" \
  --results "$RESULTS"
