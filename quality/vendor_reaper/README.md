# Actual REAPER-hosted elastique comparison

This adapter runs the complete user-provided REAPER application through public
Lua/API/render actions. It does not implement elastique, call its private library
outside REAPER, or distribute the vendor's binaries. It is a finite-file offline
comparison, not a live audio callback or hardware benchmark.

## What is pinned

The supplied runtime is REAPER7.80/linux-x86_64 and must enumerate elastique3.3.3
Pro Normal, Pro Preserve Formants (Most Pitches), and Soloist Monophonic under the
expected IDs. Names and version are checked, not inferred from an ordinal. Unknown
versions/modes fail; do not silently map them to an available engine. The supplied
Windows3.4.5 SDK demo is a different archived binary and is not used here.

Use REAPER under a valid license or its allowed evaluation terms. Backing up the
installer is not a license to reset or extend evaluation. Use one persistent,
dedicated configuration for this experiment and preserve its trial/license state.
Do not use your normal working-project instance. This script deletes the tracks
inside its own newly started project and replaces them with each next test item.
It does not change installed licenses or user projects.

## Reproduction

Linux with the vendor's GUI dependencies is required. A virtual X server is enough
for offline rendering; no physical device is implied. The current adapter uses
DISPLAY=:97. Start Xvfb there when no such display exists; do not terminate another
user's display. Start the supplied REAPER normally with a dedicated cfgfile once,
complete any normal evaluation/startup interaction, close it, and keep that same
configuration file. Never remove license/evaluation data as part of a retry.

Build the existing SDK with explicit spectral support, and store all build and
measurement output OUTSIDE the source directory:

```sh
cmake -S . -B /tmp/be-vendor-sdk -DCMAKE_BUILD_TYPE=Release -DBOILED_EGG_ENABLE_EXPERIMENTAL_SPECTRAL=ON
cmake --build /tmp/be-vendor-sdk -j2
python -m pip install numpy==2.3.5 scipy==1.17.0 soundfile==0.13.1
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
python quality/vendor_reaper/study.py prepare \
  --reaper /absolute/path/REAPER/reaper \
  --sdk /tmp/be-vendor-sdk/boiled_egg_backend_cli \
  --out /absolute/new/plan
# Record the printed plan SHA before measurement.
python quality/vendor_reaper/study.py run \
  --plan /absolute/new/plan/plan.json --sha RECORDED_SHA \
  --profile /absolute/persistent/profile/reaper.ini \
  --out /absolute/new/results
```

Each output directory must be new. Plans bind the actual input files, measured
source, SDK executable/shared library/dependencies and REAPER executable/libSwell/
elastique3 module. The original installer archives and the loaded runtime file
snapshot are retained separately in evidence. The latter is a post-run snapshot,
not a claim that all host OS libraries were locked before execution. Rebuilds or
measurement-code changes require a new plan and run. Do not edit a recorded plan
to attach old outputs to a new binary. Source archives differ from Git history.

The fixed first grid is5 synthetic families x2rates x3pitch settings x8named
engines x3repetitions=720. REAPER270 files and current SDK450 files are distinct
paths. The preserved-envelope diagnostic is an explicitly defined analytical
filter shape, not a unique ideal voice or MOS. Actual vocals, other preservation
presets, stereo, time stretching, automation, freeze and latency qualification
need separate experiments. Centroid is not onset. Do not rank general naturalness
from these synthetic observations or count repetitions as independent sources.

## Failure and evidence contract

Each host job saves API readback, its actual project and FLOAT WAV. Gains are1,
fades0, rate/pitch/mode explicit, no FX, normalization, dither, or render tail.
The host's requested bounds crop its output to the stated duration; that differs
from an unbounded raw streaming engine. Length is not proof of a particular
latency compensation algorithm. A valid WAV cannot excuse host failure: successful
process exit and complete batch counters are both required. Partial or invalid
outputs remain evidence, never a successful subset. The current batch is small
and bounded; this is not a robust general-purpose long-file job/cancellation API.

Saved measurements keep raw peak/RMS and separate pitch/amplitude/unexplained
energy, two envelope targets and fixed event windows. No gain or lag fitting,
normalization, limiting, model MOS or hidden algorithm substitution is performed.
The tests intentionally reject missing/duplicate grids, invalid identity, silence,
wrong output format, missing events, shifted tones and failed host completion.

```sh
PYTHONPATH=quality/vendor_reaper:eval python -m unittest -v test_vendor test_comparison_contract
```

There are32 unique tests after the process-completion guard. The workflow tests
these calibrations without proprietary software. Its success is NOT a REAPER
render or vendor-quality result. Actual external runs are separately identified
in docs/benchmarks/REAPER_NATIVE_RESULTS_2026-09-22.md and Issue58.

Official API and evaluation terms:
https://www.reaper.fm/sdk/reascript/reascripthelp.html
https://www.reaper.fm/purchase.php
