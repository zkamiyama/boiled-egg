# Real OMOQSE-CNN compatibility replay — 2026-09-20 JST

Related work: #17; PR #39. Base main d0e435053387d1538b379b2076a79fdd10f24330,
tree7c7bc82e14568a747d8034f75254fddf64e5b24e. This report does not alter the
measured adapter at484ad9c9e77065a6e8001c018512d0be695a2dc7.

## Decision

Accept the hash-bound **execution/replication adapter and its controls**, not
this predictor as a product-quality gate. The real uploaded CNN checkpoint now
executes on all240 received processed audio files. A second identical run is
bit-identical at prediction/crop-receipt level. Scores are diagnostic predictions,
not newly measured human MOS. No model was trained, fitted, selected by these
results or recalibrated. Correctness, anomaly, compatibility and performance
tests remain primary product gates under the user's latest instructions.

Independent qualification is BLOCKED. Existing audit code continues to reject
selection exposure, incomplete development coverage and unreviewed aliases.
`quality_selection=null`, `scores=null`, `independent_validation=false` are
retained; descriptive metrics are explicitly `replication_diagnostics`.
Full development provenance has not been established. Conservative denial of
independence is not a claim that a complete training inventory was reconstructed.

## What actually ran

The immutable external author Net is extracted from Eval_OMOQ_CNN.py after an
exact SHA256 check; its top-level dataset/unpickle/output code is not run.
Uploaded CNN weights are hash-checked and loaded with Torch weights_only=True,
strict state keys/shapes and finite-tensor checks:36 tensors,821457 parameters.

Author ref: zygurt/TSM@51333f70685de94c856efa46d0fb23a99d93921a.
Author script blob933251efda052dae7c2a567f210573de02e2ee04,
SHA256154816c4752cba2e3e0cafd6f45fb0d7eb337d30ab5bb2258dbcfa4b47b876ad.
CNN checkpoint blob6a0e03bbcb76978cb6223d31c7a566b6ff93a05d,
SHA256261336ab331254259010566ef7b9e8d03a0e65156a2381f6b6605d7d3faa659a.

Actual environment: Python3.13.5, Torch2.10.0+cpu, librosa0.11.0,
NumPy2.3.5, SciPy1.17.0, SoundFile0.13.1; CPU1thread with deterministic
Torch operations. Full installed-package versions and14 runtime file/binary
hashes are retained with the local evidence. No new SDK binary was built.

The exact profile is `omoqse-cnn-modern-reflect-seeded-v1`. It replaces the
author's per-call entropy reseeding with hash-derived per-WAV seeds and fixes
modern MFCC/delta defaults. It preserves the author's signed leading trim and
no-op trailing trim. It does not silently repair either behavior. All16 crop
starts, crop predictions, feature hashes and removed-sample counts are saved.
Native44100Hz mono input is used, without resampling, gain/lag fitting or DTW.

**This is not bit-exact historical reproduction.** Historical librosa feature
compatibility has not been independently established, and original random crops
are not recoverable. The results describe this named compatibility profile,
not a claim about the paper's reported test performance.

## Complete fixed grid and comparison

The existing importer was reused, with the received archive hashes recorded in
the protocol. All240 processed files map to20 named reference recordings and
3 dataset method labels,80 outputs each. Exact CSV MeanOS is the primary label;
MeanOS_RAW and the original TSM field remain separately preserved. Actual
output/input duration ratio is not overwritten by the CSV TSM field.

No speech/music category inference is invented: category is `unannotated`.
Source groups are the dataset's reference names, not proof that recording aliases
or alternate clips have been independently resolved. No survivor-only scoring.

| Diagnostic | Actual CNN compatibility replay | Fixed constant3 control |
|---|---:|---:|
| RMSE |0.809168530697399|1.0448174483292922|
| MAE |0.6380422567910204|See full baseline receipt|
| Signed bias |0.009699700046603865|See full baseline receipt|
| Pearson |0.6280018088852646|Undefined/null|
| Spearman |0.6302531293946074|Undefined/null|

Fixed prediction-bin bias MAE is0.05843268431551756; maximum absolute item error
is2.297417158901691. Zero predictions lie outside the checkpoint's1..5 output
scale. Neither high correlation nor near-zero aggregate bias establishes
accurate per-method prediction.

### Predictor errors by dataset method, NOT audio-engine quality rankings

| Dataset method | n | RMSE | MAE | Signed prediction-minus-label bias |
|---|---:|---:|---:|---:|
| Elastique |80|0.7310610324956319|0.5867077307647839|-0.33363732886891817|
| FuzzyTSM |80|0.6676633509025885|0.5059289271535724|-0.29621007094077767|
| NMFTSM |80|0.9919861641378424|0.8214901124547049|+0.6589464999495074|

The opposite-signed errors partly cancel in the aggregate. This is a reason not
to use the overall bias as a product-acceptance argument. It does not isolate
causal model bias from differences in source/operation/label distributions, and
it does not rank the engines' naturalness. Per-source and method/source details
are retained; unannotated material is not relabeled to manufacture category tests.

Descriptive95% source-cluster intervals (existing scorer,1000 draws,
seed20260920) are RMSE[0.7267505763,0.8829215653], MAE[0.5587475442,0.7190505388],
bias[-0.1310832523,0.1438518549]. They are conditional on these observed methods,
reference-name grouping and selected test set; not independent generalization
bounds or new human-listening uncertainty.

## Repeatability and review repair

Protocol72a2942 preceded inference. Environment amendment9a298cf corrected a
clerical Python3.11 mention to the actual3.13.5 BEFORE inference. No model or
threshold was adjusted after seeing errors.

First plan SHA256:
973103a36d9652a6874165374193ca8b298ef5bb8b68e68db9202259e0e16290.
Registered in Issue17 comment5745278709 before real-data execution.
First adapter SHA256:
995f9534144e01334d50d021feb8924805840c151e4bfeca8a77eb78f0a64655.
Both original runs passed240/240 and had identical prediction/crop receipts.

Fault injection then reproduced a new failure-receipt defect: an injected
NaN model return could escape to JSON serialization. This was NOT an observed
NaN from the real checkpoint. The adapter now validates16 finite, in-scale
returns before storing them. The regression also covers infinity and missing
crop returns. The original failing log/source are kept separately.

Revised plan SHA256:
615c5b4019df4a5a58705bc3ad3ca86fd7549e49cb0146e2f1e512e4daad0c05.
Registered in Issue17 comment5745308147 BEFORE the revised runs.
Final measured adapter SHA256:
ae21e9e41f2d6842c54be4e767f9b99f3200e1c389cfbd8f1d8df6ee8918d73d.

The final two runs again passed240/240 each. All4 runs have identical rows,
16crop starts and crop predictions. Each prediction CSV SHA256 is
1ba485adc62ea8cdc9326b32951fc0ffbde620080fed49b34267715e67fd0be1.
The same fully fixed input manifest has SHA256
9d5c2a6e647f60f8fd094c23d2e4e6eeaac97b13cf21d91f0c028dec0ae2b5db.
Do not attach old reports to the revised source; both original and revised plan,
source and report identities are retained. The repair does not change successful
inference math, preprocessing, dataset, crop policy, metrics or thresholds.

## Executed tests and scope

- Final local unit suite:28/28,skip0 (15 new +13 existing importer/auditor tests).
- Real-checkpoint adapter/direct-author-Net same-crop comparison passes. This
  checks wiring, not an independent second implementation of the neural network.
- Literal author trim loops and explicit feature profile comparisons pass.
- Duplicate/partial grids, bad scope/plan/runtime/model/source, empty/silent/
  nonfinite/stereo audio, input mutation, inference failure and overwrite are
  covered by negative tests. An initial time-limited unit attempt is retained
  as incomplete, not counted as a pass.
- Retained CLI controls:1 positive pass and6 rejections (wrongplan SHA,
  duplicate item, changed weights, silent output, prohibited independent purpose,
  existing-output protection). Five bad-input cases leave blocked JSON; overwrite
  leaves the original result unchanged instead of replacing it with a failure.
- All271 pre-existing main files are byte-unchanged. Only new evaluator/preparer,
  tests, environment/protocol/results and separate workflow are added.
- No SDK/compiler/sanitizer/GUI/physical-device test is relabeled as newly run
  locally. Normal repository CI is checked separately in the PR.

At head eb51abf57b2cebbcad07aa52ffee8047bdde6637 all6 PR workflows passed:
omoqse-replay35469616596; dataset-tools35469616628; ci35469616610;
comparison-contract35469616575; calibrated-listening35469616608;
research-pv35469616605. Final report-HEAD and merge CI identities must be checked
and recorded in PR39, not inferred from these earlier successful runs.
The new workflow downloads the exact public checkpoint/source, verifies hashes,
requires28 unique executed tests with no skips and uploads source/log hashes.
CI does not have the private240 audio set; full natural-audio replay is local.

## Drive archive and remaining work

All8 received model/source files were saved privately, without conversion, and
read back through authenticated Drive raw downloads. Sizes/SHA256 match8/8;
ViSQOL source ZIP CRC passes. A private input manifest and the exact author Net
source are saved with the models. Public repository/CI artifacts do not bundle
weights, third-party source, user audio or private Drive IDs/URLs.

CNN inference is completed in this limited profile. ViSQOL, GRU, DE and DNSMOS
are archived but NOT executed in this unit. ViSQOL's source is present, while
local Bazel/build dependencies are unavailable; no substitute is called ViSQOL.
OMOQDE normalization .p is not an excuse to use unrestricted pickle.
Model/code redistribution and commercial-use clearance remain unresolved.

Next research should first establish historical feature reproduction and/or
compare an independently fixed established metric on appropriate controls.
Full source/engine/selection provenance and unseen confirmation remain unfinished.
This result is not independent predictor validation, product adoption, a new
human MOS experiment, native-zplane pitch comparison, or quality qualification
for pitch/formant/stereo/freeze. #17 and the parent roadmap remain open.

## Reproduction

External data and weights remain separately supplied. With the fixed environment:

```sh
export OMOQSE_AUTHOR_SOURCE=/path/to/Eval_OMOQ_CNN.py
export OMOQSE_CNN_WEIGHTS=/path/to/OMOQSE_CNN.pth
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python -m unittest -v \
  eval/test_omoqse_replay.py eval/test_tsm_dataset.py eval/test_fixed_predictor.py
python eval/prepare_omoqse_replay.py --ref ref_test.zip --test test.zip \
  --scores TSM_MOS_Scores.csv --weights "$OMOQSE_CNN_WEIGHTS" \
  --author "$OMOQSE_AUTHOR_SOURCE" --output NEW_EXPERIMENT_DIRECTORY
# Record the resulting plan hash independently BEFORE inspecting predictions.
python eval/omoqse_replay.py --plan NEW_EXPERIMENT_DIRECTORY/plan.json \
  --plan-sha256 REGISTERED_SHA256 --output NEW_RESULT_DIRECTORY
```

New preparation may produce a different plan hash due to recorded preparation
script identity. Preserve and externally register it; do not overwrite a prior
plan or claim its earlier preregistration. The historical reports retain their
own plan hashes and exact source files.
