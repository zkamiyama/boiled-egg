#!/usr/bin/env bash
set -euo pipefail
if [[ $# != 2 || ( "$2" != ON && "$2" != OFF ) ]]; then
  echo 'usage: test_backend_install.sh BUILD_DIRECTORY ON|OFF' >&2; exit 2
fi
root="$(cd "$(dirname "$0")/.." && pwd)"
build="$(cd "$1" && pwd)"
staging="$(mktemp -d)"
trap 'rm -rf "$staging"' EXIT
cmake --install "$build" --prefix "$staging/prefix"
if find "$staging/prefix/include" -type f | grep -E 'research|experimental'; then
  echo 'private research headers leaked into the public SDK' >&2; exit 1
fi
expected=0; if [[ "$2" == ON ]]; then expected=1; fi
cmake -S "$root/tests/backend_install" -B "$staging/consumer" -G Ninja \
  -DCMAKE_PREFIX_PATH="$staging/prefix" -DEXPECT_SPECTRAL="$expected"
cmake --build "$staging/consumer" -j2
ctest --test-dir "$staging/consumer" --output-on-failure
