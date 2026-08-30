#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"; DST="$ROOT/third_party/eval-only"; mkdir -p "$DST"
git clone --depth 1 https://github.com/Signalsmith-Audio/signalsmith-stretch.git "$DST/signalsmith-stretch" || true
git clone --depth 1 https://github.com/breakfastquay/rubberband.git "$DST/rubberband" || true
echo 'Evaluation-only baselines fetched under third_party/eval-only/'
