# Roadmap A and reference calibration — 2026-09-15 JST

## Decision and issue tracking

The approved project review is now roadmap #15 with dependency-linked issues:
#16 comparison contracts, #17 candidate comparison/listening, #18 staged product
integration, #19 research only evidenced gaps, #20 host/platform/distribution.
This work implements the first comparison-contract stage and starts the direct
reference-calibration prerequisite of #17, in main-facing PR #21. It does not
finish the roadmap, adopt a new DSP backend or close the listening/native gaps.

Branch: quality/comparison-contract-v1, based on main
bfbb6fd0b8196a99a29f6fd4989a467deeeaf1af. Product DSP/public C ABI/plugin/state
code is unchanged. The known WSOLA/PV/automation implementations are reused,
not reimplemented. Research alternatives are not promoted by this PR.

## Implementation

`comparison_contract.py` standardizes duration=output/input frames, pitch=
output/input frequency, explicit engine/quality/formant selection, float32 WAV,
unchanged rate/channels and finite samples. Primary controls stay in [.5,2].
Expected length is floor(N*T+.5), with a predeclared0/1-frame rounding allowance.
No arbitrary tolerance, fitted shift, extra resampling, trim/pad, output gain
fitting or limiting is used by the comparison harness.

The old FFmpeg fallback passed T as tempo, reversing the intended time change.
The explicit FFmpeg adapter now uses1/T and requests pcm_f32le. All filter
options are recorded. FFmpeg's realtime Rubber Band wrapper is not relabeled
as the direct CLI's offline pass. Unavailable engines and unsupported policies
are rejected; no automatic fallback. The runner defaults to product-only unless
external systems are explicitly requested. Old implicit selection/overwrite
behavior is intentionally not retained.

Each fresh case retains input/output hashes, exact command, executable/version
and resolved-library identity, stdout/stderr and a success/failure receipt.
Failed output is not repaired or deleted. Only a fully passing metadata grid
gets the compatible listening manifest. `verify_run` rejects missing/duplicate
cells, changed plans, escaped paths and changed outputs. Raw failed directories
must not be passed directly to the older directory-scanning blind-pack tool.
Connecting calibrated-reference eligibility to blind packs remains #17 work.

A passed metadata receipt is NOT a passed tone calibration, alignment guarantee,
formant-quality result or listening decision. This distinction is tested in CI.
The `full_library_identity` flag describes resolved ldd dependencies only, not
all possible dlopen components or the complete machine. Trusted local tools only.

The direct evaluation-only `reference_rubberband.py` independently binds the
public C API. It selects R2/R3 explicitly, verifies actual generation, performs
study+process offline, and drains the actual output. Formant flag routing is
separate; no boiled-egg Harmonic/Monophonic equivalence is asserted. No vendor
DSP source is copied and no external library is linked into the product or
redistributed. The direct library's own offline compensation is used without
fitted alignment. Direct adapter support is a #17 prerequisite, not full adoption.

## Primary experiments, fixed before their measurements

Environment: local GCC14.2, Python3.13, NumPy2.3.5, SciPy1.17.0, SoundFile0.13.1;
Debian FFmpeg7:7.1.5-0+deb13u1 and librubberband3.3.0+dfsg-2+b3. Full version,
source, executable and library hashes are in the delivery. These are installed
versions, not a claim about the latest available release.

Tone grid:2-second440Hz at48/96k,mono/anti-phase stereo. Thirteen operations:
T=.5/.8/1/1.25/2 without pitch; T=1 at +/-3/7/12 semitones; .8/+7 and1.25/-7.
The global dominant-frequency peak is measured after a fixed250ms exclusion
at each end; no search is restricted to the expected target frequency. Gate5
cents and duration allowance1frame were fixed in the script before measurement.
All primary runs use Formant Off. Formant fidelity and dynamic automation are
not calibrated by this grid.

| Configuration | Passed metadata | Passed metadata+dominant frequency | Maximum absolute cents |
|---|---:|---:|---:|
|Main WSOLA CLI|52/52|52/52|0.812166|
|PV General preview CLI|52/52|52/52|0.002877|
|PV Transient preview CLI|52/52|52/52|0.001774|
|FFmpeg Rubber Band realtime filter|52/52|13/52|71.891501|
|Direct offline Rubber Band R2|52/52|24/52|38.911794|
|Direct offline Rubber Band R3|52/52|52/52|0.000216|

All312 tone outputs have exactly the expected frame counts, despite a one-frame
allowance. The FFmpeg calibration report remains false,169/208 passing across
its four requested configurations. The separate R2/R3 report also remains false
because R2 has failures. No threshold or score direction was changed to approve
those references. R3 passes this limited operation grid and becomes the next
reference candidate, not a generally qualified or superior audio algorithm.

The dominant spectral peak is not always a unique carrier/F0 estimate: periodic
phase discontinuities can produce displaced strong components. These failures
are scoped to the exact input/options/library versions and this diagnostic, not
claims that all Rubber Band versions/modes have an incorrect musical pitch.
They are not a zplane comparison or a percent improvement in perceived quality.

Two negative controls actually render the old faults: requested T=1.25 with
tempo1.25 gives76800 frames instead of120000 for the96000-frame input; the correct
tempo.8 with no explicit codec emits PCM16. The verifier rejects both. Corrected
.8/1.25 operations give1.6/2.5seconds of float32 from the2-second input.

## Actual-source metadata failures are retained

The supplied20 mono44.1k reference WAVs, unchanged and fingerprinted, were rendered
through main and FFmpeg at T=.8/1.25, pitch0:80 outputs.78 pass metadata checks.
Both failures are FFmpeg's Solo_flute_2:

| T | Expected frames | Actual frames | Error |
|---|---:|---:|---:|
|.8|142541|139572|-2969|
|1.25|222720|218152|-4568|

Neither full comparison run publishes a successful listening manifest. No crop,
pad or alternate renderer is substituted. These are metadata experiments only;
no perceptual or source-relative audio-quality scores were calculated here.

A separately labeled post-hoc follow-up rendered these two flute requests through
both direct offline generations:all4 have exact length. That isolates an
integration/mode-dependent difference in this example, not a proof of the precise
internal cause or general direct-engine quality. Raw FFT/tone exploratory probes
and an interrupted earlier calibration are retained outside the primary counts.

Primary count:208 executable tone outputs+104 direct-reference tone outputs+
80 actual-source metadata outputs=392. Negative controls, four post-hoc flute
outputs, smoke/unit/CI repeats and the interrupted run are not additional primary
evidence. Original/reference audio and generated audio are excluded from the
portable delivery; their receipts and hashes are retained. Raw WAVs remain in
the working evaluation directories and can be regenerated from the actual inputs.

## Existing defects exposed and repaired

Adding the legacy dataset test reproduced onset0.9987337906777962 against its
unchanged0.999 identity gate. `_corr` used in-place mean subtraction on `asarray`
views, modifying caller/overlapping feature arrays. The already proven fix and
two regressions from the explicit-ramps branch were backported, not reinvented.
All3 tests fail before and pass after; thresholds and DSP are unchanged. The new
primary calibration tools do not import this old evaluator, so their recorded
computational identities are unchanged by the backport. Old historical scores
are not retroactively certified with the new evaluator.

The existing research-pv workflow also referenced absent branch-only Python
filenames (`eval/make_final_research_pack.py` first). Its compile step failed
before tests. It now asserts required base tools and compiles all tracked Python
under eval/research instead of naming nonexistent files. No existing actual
file is omitted, no failure is converted to success and no test threshold is
relaxed. Explicit bash pipefail and read-only contents permissions are retained.
The original failures and subsequent successful runs are separately recorded.

## Verification and hosted CI

Local:20 contract unit tests+1 real FFmpeg/product integration+4 direct-library
tests+3 inherited dataset tests =28 tests, no skips. Default product GCC Release
CTest passes12/12. The actual integration test verifies correct failure accounting
and deliberately preserves a false FFmpeg calibration report. Its green result
must not be interpreted as FFmpeg passing the five-cent reference gate. Direct R3
has separate affirmative operation tests. Earlier unclosed test-file handling was
fixed before committed integration tests; its initial warning log is retained.

Validated code checkpoint314888140acc98373a51ba3dc2d6924a9fca0b53, tree
ea61e3b5f0b31a457ad23436c84d98d612dc5239. All4 PR workflows completed successfully:
- comparison-contract34963240764:Python3.11/3.13,28tests each, actual tools and product12/12.
- product ci34963240752:9jobs, GCC/Clang20/23, ASan/UBSan,TSan, C/C++ install, CLAP/VST3.
- research-pv34963240770:existing research C++/sanitizer and corrected Python compilation/tests.
- dataset-tools34963240759:existing dataset checks.

Downloaded artifact10393923960 ZIP SHA256:
fd7ec219d2ce328e9aed3be5973666a996d6c03da7f1785e723a7fdf8a440c56.
CRC and all119 tracked hashes verify. Its synthetic merge2246f0eb9904ed97f8e1aa5854ef293d7d8b0553
has the same tree as the code checkpoint.72 computational source files match the
local measured files byte-for-byte; run_external.py has only one extra blank line
and its parsed AST is identical. That minor provenance difference is recorded,
not relabeled as byte identity. The downloaded source rebuild passes12/12 CTests
and rerun20unit+3legacy+4direct tests. Hosted integration artifacts remain separate
from the local full-grid observations.

The main source baseline was recovered from a previously downloaded archive:
110 tracked hashes and tree7626b64092205f70ecce28dc61957c2dfdf851f8 verify against
main bfbb6fd0. The spectral measurement build uses the verified198-file f8e5ef2
explicit-ramp archive, not an unrecorded current branch. No DSP changes were made
in either measured source.

## Meaningful commits and next step

2c9f920e contract;08d0ccfd explicit runner;7befecb7 frozen executable calibration;
5ba6995f unit tests;88a10f76 real integration;00ec1fa3 initial CI;67b97c2b direct
reference; c60c316c direct grid;670fa308 direct tests;63aae4a7 reference CI;
b23c9810 contract/roadmap docs;a2996532 legacy evaluator backport;31488814 tracked
Python compile gate. This results commit is documentation only.

See docs/COMPARISON_CONTRACT.md for commands and policy. #16 can move from
implementation to review/merge; #17 now has an explicitly calibrated R3 starting
point, but still needs Signalsmith, matched formant/alignment/stereo/natural tests,
blind-pack eligibility and actual listener/host observations. #18/#19/#20 remain
later gates; no new detector/HPSS research was started. Main integration status
is authoritative in PR21 and the roadmap issue, not inferred from these measurements.

Primary interface sources:
https://ffmpeg.org/doxygen/trunk/af__rubberband_8c_source.html
https://breakfastquay.com/rubberband/integration.html
https://breakfastquay.com/rubberband/usage.txt
https://github.com/breakfastquay/rubberband/blob/v3.3.0/rubberband/rubberband-c.h
