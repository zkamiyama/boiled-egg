#!/usr/bin/env bash
set -euo pipefail
sudo apt-get update
sudo apt-get install -y build-essential clang cmake ninja-build git pkg-config python3 python3-venv python3-pip ffmpeg sox espeak-ng libsndfile1 libsndfile1-dev meson
python3 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements-dev.txt
