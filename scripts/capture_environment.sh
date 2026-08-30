#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"; out="${1:-$ROOT/results/ENVIRONMENT.txt}"; mkdir -p "$(dirname "$out")"
{ date -u +%Y-%m-%dT%H:%M:%SZ; uname -a; g++ --version|head -1; clang++ --version|head -1; cmake --version|head -1; ninja --version; python3 --version; ffmpeg -version|head -1; } > "$out"
echo "$out"
