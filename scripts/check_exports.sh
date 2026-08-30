#!/usr/bin/env bash
set -euo pipefail
lib="${1:-build/release/libboiled_egg.so}"
[[ -f "$lib" ]] || exit 2
bad="$({ nm -D --defined-only "$lib" || true; } | awk '{print $3}' | grep -Ev '^(boiledegg_|$)' || true)"
[[ -z "$bad" ]] || { echo "$bad" >&2; exit 1; }
echo "C ABI export surface OK"
