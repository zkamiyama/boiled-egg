#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"; cd "$ROOT"
./scripts/doctor.sh
for preset in release static cxx23 clang asan; do cmake --preset "$preset"; cmake --build --preset "$preset" --parallel 2; ctest --preset "$preset"; done
./scripts/check_exports.sh build/release/libboiled_egg.so
./scripts/test_install_consumer.sh build/release
./scripts/test_install_consumer.sh build/static
python3 eval/generate_corpus.py
python3 eval/run_synthetic.py --cli build/release/boiled_egg_cli
python3 eval/run_bench.py --bench build/release/boiled_egg_bench
python3 eval/summarize.py
./scripts/capture_environment.sh
