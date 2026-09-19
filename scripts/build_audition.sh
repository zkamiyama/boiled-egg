#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
cmake -S sdk/transport -B build-transport -DCMAKE_BUILD_TYPE=Release
cmake --build build-transport --parallel 2
ctest --test-dir build-transport --output-on-failure
cmake -S . -B build-sdk -DCMAKE_BUILD_TYPE=Release \
  -DBOILED_EGG_ENABLE_EXPERIMENTAL_SPECTRAL=ON -DBOILED_EGG_BUILD_TESTS=OFF
cmake --build build-sdk --target boiled_egg_backend_cli --parallel 2
printf '\nReady: python run_audition.py --demo\n'
