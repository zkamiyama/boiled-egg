# Fixed-predictor validation: bounded first unit — 2026-09-20 JST

Base: main 67ac5fc44340fe675c8a534911bdd2ac6aec853a, tree
756661b3b9b7be265aa3915b7897ec1fc610b441. Issue #17, parent #15.
This protocol precedes implementation/calibration measurements. No DSP, public
ABI, plugin, transport, application or project-license changes are in scope.
C1/C2/#32 are already merged; historical research branches are not re-merged.

## Primary-source review and an important rejection

Roberts/Paliwal OMOQDE (arXiv:2006.06153v1, section II.D, p7) and
Roberts/Nicolson/Paliwal OMOQSE (arXiv:2009.02940v1, section II, pp4–5)
choose the best epoch using a distance containing training, validation **and
test** loss/correlation. Consequently the published TSMDB test subset is not
independent of model selection for those selected checkpoints. Replaying it is
useful replication, not independent qualification. Merely freezing weights now
cannot undo that exposure. Development inventory must include selection and
calibration data, not only gradient-training data.

Primary references:
- https://arxiv.org/abs/2006.06153
- https://arxiv.org/abs/2009.02940
- https://arxiv.org/abs/2006.00848
- https://github.com/zygurt/TSM/tree/51333f70685de94c856efa46d0fb23a99d93921a
- https://github.com/google/visqol
- https://github.com/google/zimtohrli

Author repository ref verified above. OMOQSE checkpoint entries exist:
CNN/2020-08-23_15-11-52/OMOQ.pth (Git blob
6a0e03bbcb76978cb6223d31c7a566b6ff93a05d, 3292618 bytes), and
GRU/2020-08-31_19-48-48/OMOQ.pth (blob
d91b2c253557a37ac0856241321b593ca7854208, 7893373 bytes), under
OMOQSE/models. These are remote Git identities, NOT locally verified SHA256
weights or executed models. OMOQSE/Evaluation_Input_Features.py (blob
fcb619de4d99c173031f70993ba6699dacaf89f2) sums channels, peak normalizes,
trims, and uses 128 MFCCs and deltas; exact library defaults/version, framing,
checkpoint compatibility and preprocessing reproduction remain to be locked.
Do not silently repair author preprocessing and call it the original model.

The dataset paper describes separate source/engine sets; that alone does not
establish independence from later model selection. Paper beta is playback speed,
whereas this repository's ratio is output duration / input duration. The paper
reports CC BY 4.0 for the dataset; model/code redistribution permissions have NOT
been cleared here. No weights, data or author code are copied into this project.
ViSQOL documents codec/VoIP-oriented MOS-LQO and Apache-2.0 source; Zimtohrli
focuses on compression/similarity. Neither is qualified here for intentional TSM,
pitch, formant or stereo. No candidate wins by being newer or easier to run.

## Available material and bounded deliverable

The uploaded handoff contains the exact 267-file main source archive and old
validation/package evidence. The archive reproduces the main Git tree. It does
not contain ref_test.zip, test.zip, TSM_MOS_Scores.csv, or model weights. Old
logs are historical, not current execution. Container direct Git networking is
unavailable; GitHub connector reads/writes work.

Reuse eval/tsm_dataset.py manifest CSV reading/writing and
comparison_contract.py SHA256/audio inspection. Do not replace the existing
comparison or listening pipeline. Existing fit_mos_proxy is a small ridge triage
model, not OMOQ: its source-only CV also selects ridge on the reported folds.
It must not be relabeled as fixed-predictor independent validation.

Implement one offline fixed-prediction audit/score CLI, plus negative controls,
CI and a result record. No external inference/training is claimed in this unit.
A subsequent adapter must execute its real model and emit bound predictions.

## Fixed contract

The preregistered JSON plan is pinned by an externally supplied SHA256. It locks
model implementation, weights, preprocessing and inference environment files;
evaluation/development CSV hashes; expected row count; task, rates and ratio
range; label origin; and inventory-completeness/alias-review declarations.
Predictions have a receipt binding the plan, CSV and model-artifact hashes.
Hashes establish recorded identity, not the truth of a provenance declaration or
that the declared model really executed. The latter remains adapter review work.

Use explicit original-recording source_id (all clips/ratios/derivatives share it),
canonical engine_id (aliases/versions cannot evade the chosen family grouping),
category, and reference/processed SHA256 with existing manifest item_id and
paths. No filename-based source inference or automatic engine classification.
Development rows include train, validation, selection and calibration stages.
Check source IDs AND reference hashes AND engine IDs against evaluation rows.
Unknown/incomplete inventory blocks independent use; empty development is not
proof of no training. The audit cannot discover undeclared or mislabeled sources.

Strictly finite, mono, pitch0st, formant Off TSM only. Rates come from the frozen
plan within the existing 44.1/48/88.2/96k audio contract. Positive duration ratio
only; no speed0/freeze. Verify actual WAV hashes, channels, rates, duration ratio,
finite/nonempty data and RMS > 1e-8 on BOTH signals. No gain/lag fit, DTW, clipping
or resampling is added by the scorer. Reject silent/zero outputs, missing labels,
missing/duplicate/extra predictions and failed inference; retain failure evidence
and never score a conveniently surviving subset.

Metrics on unmodified predictions: RMSE, MAE, signed bias, Pearson and Spearman;
undefined correlations are null, never perfect or fabricated zero. Calibration
uses fixed prediction-bin boundaries 2,3,4 on the nominal 1–5 scale, retaining
out-of-range prediction counts and raw errors. Report per source, category,
engine and category/engine. Source-cluster percentile 95% bootstrap intervals
for RMSE/MAE/bias, 1000 draws, seed20260920; fewer than 3 sources gives no CI.
Intervals are conditional on the observed engines, not unseen-engine population
confidence or new listening uncertainty. Do not refit calibration on this set.
quality_selection remains null; a clean audit is not naturalness qualification.

## Calibration/stop conditions fixed before measurements

Generated 48/96k nonzero tones, explicit synthetic labels/predictions only.
Exercise perfect prediction, fixed bias, reversed ranking, constant predictions,
source/engine/selection leakage, unknown inventory, changed hashes, missing,
duplicate and failed predictions, silent/nonfinite audio and unsupported scope.
Analytical metric controls must agree within 1e-12 (correlation where defined).
All forbidden cases must be blocked with nonzero CLI status and saved reasons.
Complete valid fixtures must not be blocked. Bootstrap repeats must be identical.
Generated labels are NOT measured MOS, and this is NOT TSMDB replacement data.

Run relevant existing Python evaluation regressions, count actual tests/skips,
and verify every pre-existing runtime/header/application file unchanged. New CI
must exercise nonempty tests and publish source/input/result hashes. A failure
in a control blocks merging this unit; an unavailable model/dataset blocks model
qualification, not completion of the calibrated audit. Changes to this protocol
after observing confirmation data require a separately identified experiment.
