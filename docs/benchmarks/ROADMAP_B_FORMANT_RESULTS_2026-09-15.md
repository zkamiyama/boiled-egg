# Roadmap B: calibrated listening and formant reference audit — 2026-09-15

## Delivery and roadmap

The existing roadmap is #15, with A/#16, B/#17, C/#18, D/#19 and E/#20.
It was checked and updated, not duplicated. A was already merged through #21.
This resumption verified PR22 head576ebb2ae863a97e04247548ee73a17ab948587c and
merged its13 evaluation/CI/documentation files using the expected head. Main is
**da66001ea2381a938f227a36fe0319d0dc429945**. Product DSP/API/ABI/plugin/default
behavior and feature PR8/9/10 are unchanged. Main product and comparison-contract
workflows succeeded after merge. Infrastructure merge is not audio-quality promotion.

New **PR23 / quality/formant-reference-audit** adds independent formant evaluation.
Validated code checkpoint8c7a37d6a9981e081f4f6b0af46e2c4f9bebeb23; protocol9512ae51
preceded rendering. The current record is documentation only. B is still open:
Signalsmith/native-zplane acquisition, full stereo/time alignment, natural-formant
qualification, listener observations and real-host tests remain. C/D/E are not
marked complete, and new transient-detector research is not substituted for them.

## Fresh baseline and listening-panel verification

Downloaded PR22 CI artifact10401671928: ZIP CRC/SHA256 and132 source hashes verified.
Built product CTest12/12 and the reused f8e5ef2 spectral dependency CTest23/23
(198 dependency source hashes verified). Existing evaluation tests57/57 and the
real WSOLA/R3 integration1/1 pass. An initial manual test invocation omitted the
required RB_LIBRARY environment variable and failed setup; its log is retained.
The correctly configured rerun passes without code/threshold changes.

The existing Off-only panel was frozen: WSOLA, PV General, PV Transient, direct
offline R3; mono44.1k; duration.8/1.25 and pitch-7/+7st. Fresh exact-operation
440Hz evidence passes16/16. This does not requalify the earlier failed stereo,
FFmpeg or R2 calibration cells. Those historical results are not relabeled.

The actual supplied20 references then produce320/320 valid raw FLOAT outputs,
with exact length/rate/channels, finite samples, and unchanged sources/binaries.
Raw peak max1.4306933879852295;83/320 exceed1 and are not limited. This is reused
development material, not new independent natural audio.

An80-trial/320-choice anonymous pack was generated and its gain transforms and
integrity verified. One common attenuation per trial applies to all candidates
and the original orientation audio; no per-system gain matching or fitted alignment.
Organizer identity/key is separate. Pack ID:
`ee6b734eaf98ee733d9b189fcb851d7c0b89b1b3ab57b2cae7d8d3c148cd15a0`.
The actual zero-submission report has explicit_ratings=0, quality_selection=null.
No invented scores, listening conclusion, manual-browser or DAW qualification.

## New formant audit

Two continuous resonance contours,110/220Hz excitation,48/96k,six shifts and
8 configurations produce384 outputs. PV General/Transient each retain distinct
Off/Harmonic/Monophonic policies. Direct R3 uses its own Off/Preserved names;
Preserved is not relabeled as a vendor Monophonic/Harmonic distinction.

For harmonic k the source coefficient is S(k)E(k*F0). Off ideal keeps that
coefficient at k*F0*p. Preserved ideal has S(k)E(k*F0*p) at the new frequency.
This is an independently constructed harmonic/filter abstraction, not a natural
voice, chord or general polyphonic model. Analyze the prespecified central
0.25..1.75seconds with Hann FFT and disjoint +/-4Hz harmonic neighborhoods;
score150..6000Hz. Only the relative-contour METRIC removes a mean log gain.
Raw audio is not normalized, aligned, padded, trimmed or limited. Mean partial
gain, raw RMS/peak and out-of-harmonic energy remain separate diagnostics.

Eight tests cover ideal/gain/wrong-envelope, read-only/invalid input, deterministic
fixtures, named policies, complete grids and failed receipts. All384 output
metadata and measurement records pass. There is no invented formant quality cutoff
or automatic authorization of blind listening; Candidate remains Off-only.

### Mean retained-envelope error (same preservation objective)

24 fixture/F0/pitch conditions per rate; lower is closer to this analytical target.

|Configuration|48k|96k|
|---|---:|---:|
|PV General Off|11.077|11.077 dB|
|PV General Harmonic|5.655|5.582 dB|
|PV General Monophonic|5.724|5.650 dB|
|PV Transient Off|11.209|11.209 dB|
|PV Transient Harmonic|5.917|5.848 dB|
|PV Transient Monophonic|6.019|5.951 dB|
|Direct R3 Off|13.140|12.804 dB|
|Direct R3 Preserved|8.206|7.262 dB|

Each PV preservation policy improves over its own Off in48/48 conditions.
R3 preservation improves40/48 and worsens8/48. Substantial residual error remains:
PV Transient Monophonic reaches9.088dB at96k/110Hz/closed/+12st; direct R3 preserved
reaches18.774dB at48k/220Hz/open/-7st. No tuning followed these outputs.

Off intentionally shifts its envelope. Against the appropriate Off oracle,
PV General is about0.004dB, PV Transient0.952dB and R3 5.311/4.549dB. The11dB
retained-envelope difference for Off is not an implementation defect. Do not
combine unlike targets into a universal quality score. This limited steady mono
experiment does not establish natural-voice/stereo or native-zplane superiority.

Local Rubber Band is3.3.0+dfsg-2+b3, libsndfile1.2.2-2+b1, NumPy2.3.5,
SciPy1.17.0 and SoundFile0.13.1, not a claim of the latest vendor build. Direct
R3 study/process and compensation differ from FFmpeg realtime processing.
No third-party DSP source or library is linked into the product or committed.

## CI and exact-source audit

At8c7a37d6 all six PR workflows pass: formant-reference-audit34986094883,
calibrated-listening34986094800, comparison-contract34986094818,
product ci34986094894, research-pv34986094837 and dataset-tools34986094905.
New CI runsPython3.11/3.13,8 tests,product regression and192-case48k audit with
pinned preview source. No quality threshold was relaxed. CI does not add its
outputs to local counts or prove audible significance.

Artifact10403164672 SHA256:
`29f8bd48e1bb56bf75fc3d4e4a6fb9f224fa72e2dd04ce1f5cd1e11ddd02b311`.
CRC and138 source hashes verify.136 local files match exactly; two missing local
files were protocol/workflow only. Downloaded-source tests pass8/8. CI artifacts
retain summaries, receipts and source but omit individual generated output WAVs;
local raw outputs remain. Fresh source is included in the delivery.

This resumption's primary count:16 operation calibration +320 actual-source
outputs +384 formant outputs =720. Integration tests, presentation copies and
prior-session/CI repeats are excluded. No new DSP realtime or full sanitizer
qualification is claimed; the production DSP is unchanged.

## Reproduce and next gate

```sh
python -m pip install numpy==2.3.5 scipy==1.17.0 soundfile==0.13.1
OPENBLAS_NUM_THREADS=1 python -m unittest discover -s eval/formant_audit -p 'test_*.py' -v
OPENBLAS_NUM_THREADS=1 python eval/formant_audit/study.py \
  --spectral /absolute/pinned-preview/boiled_egg_backend_cli \
  --reference /absolute/librubberband.so.2 --output results/formants
```

Root main intentionally does not enable the spectral dependency; build its pinned
source separately. Use CALIBRATED_LISTENING.md and LISTENING_OBSERVATIONS.md for
Off-only calibration/render/pack/explicit-response collection. Preserve actual
source and executable identities; a new path/build needs new evidence.

The delivery separates listener audio from organizer key. Evidence contains
source, measurements, receipts/logs and checksums, not third-party SDKs/libraries
or fonts. Product adoption waits for B's actual observations and declared use
cases. D/new algorithms remains deferred until a concrete remaining need is shown.

Official integration semantics consulted:
https://breakfastquay.com/rubberband/integration.html
https://breakfastquay.com/rubberband/code-doc/classRubberBand_1_1RubberBandStretcher.html
