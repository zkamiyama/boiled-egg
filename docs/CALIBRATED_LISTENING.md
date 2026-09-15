# Calibrated exploratory listening (roadmap #15 / #17)

This is the next evaluation step after PR #21. It connects exact-operation
calibration to complete raw panels and anonymous presentation. Product DSP,
C ABI, default profiles, plugin state/GUI and main are not changed.

## What is and is not authorized

A successful metadata receipt establishes finite float32 WAV, expected duration,
rate and channel count. The new evidence adds a two-second440Hz global dominant-
frequency check (5 cents), and, for stereo, x_R=-0.5*x_L relative RMS error<=1e-5.
Every tested rate/channel/T/p/candidate configuration is recorded separately.
Failed cells remain failed even when their output file has the correct length.

These are **operation diagnostics**, not a general audio-quality rating or a
stereo perceptual tolerance. The strict stereo diagnostic includes startup/end
samples and is not the settled-tone interval. A failure requires investigation;
it does not establish that a small residual is audible. Do not reduce the gate
post hoc to qualify a preferred engine. The first real-source pack was declared
mono/Formant Off before these results; it does not silently omit a failed stereo
panel. Untested rates, policies, controls and changed binaries cannot inherit a
nearby calibration. Existing formant candidates will need their own B-stage study.

Full sample-alignment/formant/real-host qualification remains pending. The purpose
is explicitly `operation-calibrated exploratory listening`, not a certified
listening standard, product promotion, native zplane comparison or realtime test.
No waveform-aligned error scores may be inferred from these metadata gates.

## Explicit configuration

Supply trusted local tools/libraries only. External code is evaluation-only and
must never be linked into the product. Example panel.json (edit absolute paths):

```json
[
  {"name":"wsola","kind":"boiled_egg","path":"/absolute/build/boiled_egg_cli"},
  {"name":"pv_general","kind":"spectral","quality":"general","path":"/absolute/preview/boiled_egg_backend_cli"},
  {"name":"pv_transient","kind":"spectral","quality":"transient","path":"/absolute/preview/boiled_egg_backend_cli"},
  {"name":"r3","kind":"rubberband_direct","path":"/absolute/librubberband.so.2","generation":3,"block":4096}
]
```

The product branch containing this tool does not build the opt-in PV by itself;
use the already implemented spectral-preview/dynamic/ramp source for that
explicit executable. There is no fallback when it is unavailable. The direct
reference reuses `reference_rubberband.py` offline study/process, never the FFmpeg
realtime wrapper. An actual generation check prevents R3 silently becoming R2.

```sh
python -m pip install numpy==2.3.5 scipy==1.17.0 soundfile==0.13.1
python eval/calibrated_listening.py calibrate --panel panel.json --output results/calibration
```

A mixed calibration panel can also include explicit R2 and FFmpeg controls. A
failed aggregate report stays false. Downstream selection can use an exact
passing subset only when that requested panel/operations were declared in advance;
it cannot treat all conditions or every mode of that engine as qualified.

Create requests.json containing the **full original source paths**, e.g.:

```json
{"sources":["/absolute/references/source.wav"],"operations":[[0.8,0],[1.25,0],[1,-7],[1,7]]}
```

```sh
python eval/calibrated_listening.py render --panel panel.json \
  --calibration results/calibration --requests requests.json --output results/panel
python eval/calibrated_listening.py pack --run results/panel \
  --calibration results/calibration --output results/listening
```

Each output must be a new directory. Inputs and dependencies must remain in place
while rendering/verifying. Do not overwrite calibrated build artifacts. A runtime
interruption leaves a plan and partial raw receipts but no successful summary;
this tool does not yet resume partial runs. Keep them as interrupted evidence and
restart into a new directory. Do not fake a complete report or discard failed
cells. `verify_panel` rejects missing/duplicate cells and changed raw/evidence.

The current and recorded dependency probes are retained; comparison uses config,
file/adapter hashes and numerical-library versions, not ASLR addresses in `ldd`.
This is file provenance, not cryptographic vendor attestation or a record of every
OS/microcode state. The organizer records the renderer's mode and library identity.

## Listener versus organizer

`listener/` contains only generated trial IDs, operation instructions, original
orientation audio, anonymous A/B/... choices and a player. `organizer/` contains
candidate identities, source names, raw hashes, calibration references and gains.
Keep the organizer files away from listeners until scoring. Share only the
listener subdirectory as the blind pack; source recordings stay outside git.

WAVs are decoded and re-encoded as float32 to remove embedded engine tags. One
common gain per trial caps the largest sample peak at0.95; the SAME gain is applied
to every candidate and its original. No per-system RMS normalization, fitted
delay, trim/pad, resampling or limiter. Presentation PCM is verified against the
explicit float32 gain transform; original evaluation files are never modified.
Relative loudness remains a possible perceptual cue. Sample-peak headroom is not
a true-peak guarantee. Start playback at low volume.

The original is an orientation reference, not an ideal pitch/time-transformed
waveform. The player has blank 1..5 naturalness/attack/sustain ratings. Export
includes only explicit responses and a pack identifier. `validate_answers`
rejects wrong-pack, duplicate, unknown and nonfinite/out-of-range answers. Zero
responses remain zero; this change intentionally makes no synthetic MOS or
adoption decision. The simple independent players do not provide sample-synchronous
switching; browser playback was not used as a phase-alignment measurement.

## Verification

```sh
PYTHONPATH=eval python -W error::ResourceWarning -m unittest -v test_calibrated_listening
BOILED_EGG_CLI=/absolute/build/boiled_egg_cli \
BOILED_EGG_RB_LIBRARY=/absolute/librubberband.so.2 \
BOILED_EGG_LISTENING_RESULTS=results/integration \
  python -W error::ResourceWarning eval/test_candidate_integration.py
```

The first test suite uses clearly labeled doubles for accounting only. The
second actually renders WSOLA and offline R3; missing binaries fail rather than
skip. The CI workflow runs both on Python3.11/3.13 with the unchanged product
CTest. It uses generated audio only, not the private natural corpus.

Reference integration guidance:
https://breakfastquay.com/rubberband/integration.html
No-given-reference listening-method context:
https://www.itu.int/rec/R-REC-BS.2132/en
