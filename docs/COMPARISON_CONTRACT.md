# Comparison contract and product-candidate roadmap

The owner-approved roadmap is tracked by #15: #16 comparison semantics, #17
candidate evaluation/listening, #18 staged product integration, #19 gap-driven
DSP research, #20 host/platform/distribution qualification. The algorithm list
in #1 is not a guaranteed increasing quality ladder. Existing #8/#9/#10 product
work should be reviewed, not rewritten or merged together with research results.

This change implements #16 and begins reference calibration for #17. Product
DSP, C ABI, plugins and stable defaults are unchanged. It is evaluation tooling,
not a new backend or quality promotion. External code is never linked into the
product. The direct Rubber Band adapter loads an explicitly supplied, trusted
local library only; that GPL/commercially licensed library is not distributed here.

## Three distinct outcomes

1. A **render receipt** verifies request/metadata: requested duration direction,
   unmodified rate/channels, finite float32 WAV, and a declared rounding allowance.
2. A **calibration report** additionally tests operation semantics on a frozen
   synthetic grid. Failure does not become a successful reference just because
   the runner itself works correctly.
3. **Product-quality selection** additionally needs matched modes, alignment,
   formant/stereo/natural material checks and listening/host evidence. Neither a
   receipt nor a calibration is that decision. There are no new MOS/native-zplane
   results in this change.

Do not feed failed raw output directories to the old directory-scanning blind
pack tool. `verify_run` checks a successful full comparison before downstream
use. The new runner only publishes the compatible five-column render manifest
when every requested cell passes metadata checks. Connecting a calibrated
reference registry to blind-pack eligibility is remaining #17 work. Calibration
eligibility must still be checked separately; the runner's `passed` is not an
automatic sound-quality or alignment approval.

## Explicit semantics

`duration_ratio = output_frames / input_frames`; `pitch_ratio = output_frequency /
input_frequency`. Primary ranges are [.5,2] and +/-12 semitones. Output frame
expectation is floor(input_frames*duration_ratio+.5); the default allowance is
one frame for engine rounding, not a permission to crop or synthesize missing
samples. There is no arbitrary tolerance override, fitted shift, DTW, extra
resampling, gain fitting, normalization, limiter or automatic engine fallback.
Inputs are nonempty mono/stereo WAV PCM16 or float32 at44.1/48/88.2/96k. Outputs
must be float32 WAV with the same rate and channel count.

The old FFmpeg fallback confused duration with playback speed. The explicit
adapter passes `tempo=1/duration_ratio`, `pitch=pitch_ratio`, and `pcm_f32le`.
It records all filter options including formant and stereo linkage. FFmpeg's
Rubber Band wrapper uses the library's realtime API; it is not the direct CLI's
offline study pass. A real-output length/frequency failure remains a failed
reference case, not something silently repaired by padding or picking another
engine. Missing executables/filter capabilities are rejected before comparison.

The old CLI-runner fallback behavior is intentionally removed. The default
`--systems` now selects only boiled egg. Request FFmpeg explicitly:

```sh
python eval/run_external.py --corpus /absolute/reference-folder \
  --cli /absolute/build/boiled_egg_cli --systems boiled_egg ffmpeg_rubberband \
  --time 1.25 --pitch 0 --output results/explicit-comparison
```

Each output run/case directory must be new. Receipts, commands, stdout/stderr and
failed raw outputs stay available. Incomplete/duplicate grids and tampered
outputs cannot pass `verify_run`; a failed run exits nonzero and has no successful
listening manifest. Existing scripts that relied on implicit fallback/overwrite
must select systems and new output directories explicitly.

`Engine(kind='spectral', ...)` is available to the calibration driver for the
existing opt-in backend CLI; `run_external.py` deliberately exposes only the
main CLI and FFmpeg selections in this first change. Harmonic/Monophonic and
quality are independent for spectral. FFmpeg/direct-reference `preserved` is a
vendor option, not an assertion that it equals either boiled egg policy. No
unsupported formant choice is silently downgraded to Off.

## Timing and provenance limits

The runner records executable SHA256, version/help/capability output, requested
settings, source/output hashes and resolved shared-library hashes from `ldd`
when available. `full_library_identity` means the resolved ldd dependency set
was recorded; it cannot attest unknown dynamic plugins, microcode or every
system resource. Only trusted local tools should be supplied to the probe.

Output is inspected as emitted. In particular, the current legacy boiled egg
CLI already caps an overlong result internally; this is recorded as an engine
behavior, not hidden as evaluator trimming. The spectral CLI checks its exact
stream length. FFmpeg's filter output is left untouched. Alignment is marked
unverified; metadata equality alone must not authorize waveform-aligned scores.

The direct C-API adapter uses Rubber Band's own offline study/process/end handling.
It requests R2/R3 explicitly and checks the actual engine generation. It does
not call the Rubber Band CLI, which can have other defaults and output handling.
Its library/adapter hashes are recorded, and it remains evaluation-only. The
full steady-tone calibration currently exercises Off, not formant fidelity.

## Reproduce calibration and software checks

```sh
python -m pip install numpy==2.3.5 scipy==1.17.0 soundfile==0.13.1
cmake -S . -B build -G Ninja -DCMAKE_BUILD_TYPE=Release
cmake --build build -j2
ctest --test-dir build --output-on-failure
PYTHONPATH=eval python -W error::ResourceWarning -m unittest -v test_comparison_contract
BOILED_EGG_CLI="$PWD/build/boiled_egg_cli" \
  python -W error::ResourceWarning eval/test_comparison_integration.py
BOILED_EGG_RB_LIBRARY=/usr/lib/x86_64-linux-gnu/librubberband.so.2 \
  python -W error::ResourceWarning eval/test_reference_rubberband.py

# These commands return failure when ANY requested calibration case fails.
# Inspect the saved JSON/CSV; do not lower thresholds to make a reference pass.
python eval/calibrate_external.py --cli "$PWD/build/boiled_egg_cli" \
  --output results/external-calibration
python eval/calibrate_reference.py \
  --library /usr/lib/x86_64-linux-gnu/librubberband.so.2 \
  --output results/direct-calibration
```

The frozen primary tone grid is two-second440Hz,48/96k,mono/anti-phase stereo,
T=.5/.8/1/1.25/2 without pitch, T=1 with +/-3/7/12st, and .8/+7,1.25/-7.
A global dominant-frequency peak is measured after a fixed250ms exclusion at
each end. The detector does not search around the requested pitch. Five cents
is a declared calibration diagnostic, not a universal perceptual limit. Periodic
phase discontinuities can put the strongest spectral component off target even
when another frequency estimate suggests the carrier frequency. Such rejection
must not be generalized to every Rubber Band version/mode or labeled a native
zplane accuracy result.

CI's integration test verifies truthful successful/failed receipt accounting and
negative-control detection. Consequently CI can pass while a recorded FFmpeg
calibration report is `passed=false`; the reference remains unqualified. R3
operation checks have their own affirmative tests. No test is skipped because
an explicitly required external engine is unavailable.

## Next roadmap gate

Complete #17's calibrated mode registry, Signalsmith reference, direct-library
formant/natural/stereo/alignment qualification and blind-pack connection before
claiming a matched product-quality comparison. Preserve historical failure
receipts. Collect actual listener/host observations; no responses means only
pack preparation, not completed subjective validation. Then review staged
product integration independently from experimental phase/HPSS alternatives.

Primary integration references:
- https://ffmpeg.org/doxygen/trunk/af__rubberband_8c_source.html
- https://breakfastquay.com/rubberband/integration.html
- https://breakfastquay.com/rubberband/usage.txt
- https://github.com/breakfastquay/rubberband/blob/v3.3.0/rubberband/rubberband-c.h
