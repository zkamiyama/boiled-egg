# Roadmap B: operation-calibrated exploratory listening

Parent roadmap #15, implementation task #17, prerequisite PR #21 / #16.
This change starts the calibrated-registry to blind-pack connection. It does not
complete formant/host/listening qualification or promote a product backend.
No product DSP/API/plugin source changes. Reuse comparison_contract.py and the
evaluation-only direct Rubber Band adapter, not a competing DSP implementation.

## Frozen implementation scope

Compare explicit WSOLA, existing opt-in PV General/Transient, and direct offline
Rubber Band R3 (with R2 and FFmpeg retained as calibration controls). No automatic
engine fallback. First pack is **Formant Off only**. Vendor preservation is not
silently mapped to boiled egg Harmonic or Monophonic. Signalsmith/native zplane
remain separate #17 items, not relabeled substitutes.

An evidence registry binds the complete candidate configuration, executable or
library plus resolved dependencies, wrapper hashes, exact rate/channels and exact
requested T/p pair. Reuse the fixed two-second440Hz /5-cent operation diagnostic;
require finite FLOAT WAV metadata and linked anti-phase relation where stereo.
Full calibration results retain failed cells. An exploratory request can use only
its own passing cells, never an untested interpolated configuration or a failed
pitch/time pair. This exact-operation coverage is not whole-corpus quality or
sample-accurate alignment certification.

## Pack rules

Freeze sources, requested operations and candidate panel BEFORE rendering. Require
all selected candidates to have matching passed calibration cells. Any failed or
missing actual render means no listener pack, with raw files and failure receipts
retained. Verify input/output/probe/configuration/evidence hashes and complete grid
again before publishing. Do not fill missing output, fit delay, resample, or select
a per-source winning mode. Root must be new; no destructive overwrite.

Keep listener audio/anonymous choices separate from organizer identity, commands,
raw-output hashes and gain records. Re-encode presentation WAVs to remove embedded
metadata. Apply at most one common peak-safe attenuation per trial to all choices
and original orientation audio, NEVER per-candidate loudness fitting. Raw output
is untouched; presentation PCM transformation is independently verified.

UI follows the existing multi-choice player pattern but has BLANK ratings. Export
only explicitly answered choices; no default MOS, auto-filled score, synthetic
listener or reference-quality claim. Original source is orientation, not ideal
transformed audio. No given transformed reference; this is exploratory listening,
not a certified ITU test. Scores are submitted with a pack identifier.

## Predeclared experiment

Calibration at44.1/48/96k,mono/stereo for the 13 operations already in
calibrate_external.OPERATIONS. Candidate panel for first actual pack: WSOLA,
PV General, PV Transient, R3 offline. Operation subset for the actual20-source
regression: T=.8/1.25,pitch0 and T=1,pitch-7/+7. All20 sources remain historically
used development/regression data, not unknown holdout. Full files are processed;
no crop or hidden time alignment. 4 candidates x20 x4 =320 primary natural renders
if all gates pass. Playback can be split into predetermined batches; no listening
responses are assumed. External/synthetic runs are separate from natural audio.

Leave actual listener/host evidence and full formant/alignment checks open in #17.
#18 integration and #19 DSP research depend on that decision rather than on the
number of files generated. Stable main and draft spectral stacks are not merged
as a side effect of this evaluation work.

Primary method references:
https://breakfastquay.com/rubberband/integration.html
https://www.itu.int/rec/R-REC-BS.2132/en
