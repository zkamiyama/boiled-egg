# Roadmap B: stereo/time qualification and resumption — 2026-09-16 JST

## Decision and scope

Roadmap #15 and stages #16–#20 already existed when this session resumed. Stage A
and the initial calibrated-listening pipeline were already merged through #21/#22;
verified main is da66001ea2381a938f227a36fe0319d0dc429945. Do not duplicate those
issues or claim their implementation as new. This session adds the remaining
stereo/local-time diagnostic in draft #24, stacked on the formant audit #23.
The roadmap and #17 checklists have been updated with actual evidence and blockers.

No product DSP, C ABI, RAII, plugin/UI/state, default or main changes. No native
zplane output, Signalsmith run, human listening scores, live DAW test or new
algorithm adoption. Evaluation code being correct does not make every candidate
pass its stereo controls. The frozen experiment found failures and retains them.

## Implementation

Protocol commit dafe1cd2 predates the actual new renders. Implementation4b18116b,
calibration tests273c8a35, CIb6ce735d are separate commits. Code checkpoint:
b6ce735d4001e7dc157731e0a5ef56ef48d13cc5. This result record changes documentation.

Reuse eight named configurations from the existing formant runner: PV General/
Transient each Off/Harmonic/Monophonic; direct offline R3 Off/Preserved. Vendor
Preserved is not relabeled as either of our formant policies. The measured PV
source remains pinned to f8e5ef2cbce84f396597860a408b4a3084796115. All reference
code is evaluation-only; external libraries are not included or product-linked.

New stereo grid:48/96k, two-second audio, T=1,p=1; T=.9/1.1,p=1; T=1,p=+/-7st.
Four inputs: broadband/tonal R=-.375L; silent right; alternating4ms bursts; those
bursts channel-exchanged. Input centers .30/.75/1.20/1.65 seconds. Total320 output
files. Preserve rate/channel/FLOAT/duration metadata, no fitted alignment, delay
subtraction, normalization, limiter or output correction.

The two relational checks use norm(R-gL)/norm(L), with g=-.375 or0 and the
predeclared1e-5 control. Entire output includes startup/end samples. Zero output
energy is rejected, never called perfect preservation. A separate waveform
channel-exchange residual compares exchanged output against exchanging the
original output. This is a deterministic covariance check, not an audible-stereo
score or proof that every phase-equivalent renderer must produce identical audio.

Event locations are energy centroids in fixed+/-80ms output-time windows around
T*input_center. Width5–95%, captured energy and opposite-channel leakage are also
stored. No lag search is performed. Results are descriptions of this fixture,
not full sample alignment or a universal transient-placement quality gate.

Eight additional tests independently inject sign errors, leakage, zero output,
1ms delay, missing events, shape mismatch and incomplete grids. The known delay
remains48 samples in the48k measurement; it is not fitted away. No detector truth
or corrected waveform is fed to the engines.

## Actual stereo findings: not all controls pass

All320 output metadata checks succeed, measurement errors0. Of160 proportional/
silent-channel controls,80 pass;64/80 channel-exchange pairs pass. The standalone
CLI correctly exits1. Its failed status and every raw receipt remain unmodified.

| Configuration | Proportional pass/10 | Silent-right pass/10 | Exchange pass/10 |
|---|---:|---:|---:|
|PV General Off|0|10|10|
|PV General Harmonic|0|10|10|
|PV General Monophonic|0|10|10|
|PV Transient Off|0|10|10|
|PV Transient Harmonic|0|10|10|
|PV Transient Monophonic|0|10|10|
|Direct R3 Off|5|6|2|
|Direct R3 Preserved|3|6|2|

PV's largest proportional residual is0.0004577814, not the1e-5 target. This is a
strict relative waveform residual, not an established audibility threshold or
an automatic DSP-bug diagnosis. The post-hoc localization of that one worst PV
case finds error through the middle and tail, not just the startup interval.
It changes no render or threshold and is stored separately as a diagnostic.

R3's largest proportional residual is0.00945519 with preservation. Its waveform
exchange comparison also differs in nonunity cases. These results must not be
translated directly into perceived stereo damage or a claim of vendor inferiority:
reference-channel choices or common phase changes can affect waveform covariance.
No physical or algorithmic cause has been conclusively identified in this pass.

Max absolute event-centroid displacement over these prescribed windows, ms:
General Off0.039116, Harmonic1.454067, Monophonic0.290015;
Transient Off0.139028, Harmonic1.089714, Monophonic0.357841;
R3 Off4.256267, Preserved4.667310 including channel-exchanged fixtures.
They are not delays subtracted from a comparison or a new fitted error threshold.
The reference documentation notes that feature-aware time stretching can change
local timing even when the overall duration ratio is fixed.

## Revalidated formant evidence

The existing384-output study was rerun without changing its metric, oracle,
configuration or thresholds:2 contours x2 fundamentals x2 rates x6 pitch shifts
x8 configurations. All metadata/measurements are valid. The oracle changes the
harmonic excitation pitch with an independently specified continuous filter;
Off and preserved targets differ intentionally. Central .25–1.75s only, mono,
steady state. Relative contour removes one metric scalar; raw gain/leakage/peaks
are separately retained. This is not natural polyphonic formant qualification.

Mean retained-envelope error at48k/96k, dB:
- PV General Off11.077/11.077; Harmonic5.655/5.582; Monophonic5.724/5.650.
- PV Transient Off11.209/11.209; Harmonic5.917/5.848; Monophonic6.019/5.951.
- Direct R3 Off13.140/12.804; Preserved8.206/7.262.

These reproduce the earlier analytical conclusion: preservation helps the
specified retained contour but substantial ideal error remains. An Off engine
is not defective simply because it shifts the envelope. No universal quality
ranking or native-zplane result follows from these means.

## Fresh exploratory listening pack

Reused the PREVIOUSLY declared independent mono/Off panel: WSOLA, PV General,
PV Transient, direct R3; T=.8/1.25 and p=-7/+7st. This is not a subset selected
after observing the new stereo failures. First calibrate all16 exact operations
on the same binaries. All16 pass. Then process the actual20 supplied mono44.1k
references:320/320 raw metadata receipts pass, with no padding/trim/gain fitting.
The historical source set is development/regression material, not a fresh holdout.

Generated80 anonymous trials/320 choices. Pack ID:
baac591889fbf78c8f18c16baaccc73d2b1e6e401af9375567858d0dc8737531.
One common attenuation per trial applies to all choices and original orientation
audio; raw outputs remain unchanged. The organizer/key is separate. Every
presentation PCM transform and pack identity was verified. New stereo/formant
audits do not grant this or any other additional listening eligibility.

Actual submissions0, explicit ratings0, quality_selection=null. The collector
contains no default ratings. No browser usability, human hearing or quality
selection result is claimed. A packet prepared for listening is not listening.

This session generated1040 primary evidence outputs:320 new stereo/time,
384 revalidated formant,16 exact-operation calibration and320 natural-panel
outputs. Presentation copies and software-test renders are not independent
cases, and reruns of prior experiments are not novel dataset evidence.

## Local/hosted verification and source identity

Local GCC14.2 root product12/12 CTests; pinned opted-in PV23/23. Existing eval
suite59/59 and new+inherited formant suite16/16, no skips. This is the recorded
scope, not a repeat of all historical research or every compiler/sanitizer build.
No DSP source changed and no fresh callback benchmark was needed or claimed.

All seven triggered workflows at the code checkpoint succeeded:
ci35019435970, comparison-contract35019435922, calibrated-listening35019435915,
formant-reference-audit35019435984, stereo-time-reference-audit35019435952,
research-pv35019435946 and dataset-tools35019435938.

The NEW workflow verifies calibration and complete diagnostic evidence. It
explicitly does not assert that external engines pass every relational control.
Candidate failures are present in its artifacts. At48k its80 relational controls
have37 passes, and32/40 exchange pairs pass. These counts differ from local build
counts; environments/binaries are separately fingerprinted. Do not merge or
replace observations. Existing product gates were not relaxed.

Downloaded CI artifact10416957433 ZIP SHA256:
643f44a739074f7d31d9116cbaabcefc8105bee626bb1841665fd26a873a3fff.
CRC and143 tracked source hashes verified. All141 locally present tracked files
match; the two initially absent local files were this study's workflow/protocol,
not computational source. Downloaded-source16/16 tests pass. Initial resumption
also verified139 hashes from artifact10403742097. Raw384+320 outputs and receipts
were individually checked against their recorded hashes after all processing.

Local references: Rubber Band3.3.0+dfsg-2+b3, libsndfile1.2.2-2+b1, NumPy2.3.5,
SciPy1.17.0, SoundFile0.13.1. This is not a latest-version performance claim.

## Reproduce and next B work

```sh
# Build the separately pinned opt-in PV source and main WSOLA, then:
OPENBLAS_NUM_THREADS=1 python -m unittest discover -s eval/formant_audit -p 'test_*.py' -v
OPENBLAS_NUM_THREADS=1 python eval/formant_audit/stereo_time.py \
  --spectral /absolute/boiled_egg_backend_cli \
  --reference /absolute/librubberband.so.2 --output results/stereo-time
# Exit1 is expected when any retained relational control fails; inspect summary.
```

See CALIBRATED_LISTENING.md and LISTENING_OBSERVATIONS.md for panel rendering and
explicit ratings. Delivery separates listener audio from the organizer key and
from implementation/measurement evidence. No external SDK/library/font is included.
Original recordings remain untracked and are used only in the supplied private
listening material.

Next B work is to classify the stereo differences and collect actual listening
observations, then choose a documented use-case decision. Signalsmith, native
zplane, fresh licensed audio and real-host qualification remain unfinished.
Do not return to unrelated DSP research or promote all research branches merely
because the new evaluation code's CI is green.

Official contract: https://breakfastquay.com/rubberband/integration.html
