#!/usr/bin/env bash
set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"; cd "$ROOT"
printf 'boiled egg development environment\n'; printf '%-18s %s\n' repo "$ROOT"
for cmd in cmake ninja gcc clang python3 ffmpeg; do printf '%-18s %s\n' "$cmd" "$(command -v "$cmd" 2>/dev/null || echo MISSING)"; done
missing=0; for cmd in cmake ninja python3; do command -v "$cmd" >/dev/null 2>&1 || missing=1; done
python3 - <<'PY' >/dev/null 2>&1 || missing=1
import numpy, soundfile
PY
exit "$missing"
