# Fixed-predictor audit: results — 2026-09-20 JST

Issue #17 / PR #38. Base main: `67ac5fc44340fe675c8a534911bdd2ac6aec853a`.
Base tree: `756661b3b9b7be265aa3915b7897ec1fc610b441`.
Protocol commit: `e9d58d414f269b124f882aee2be7574639c77bf0`.
Final measured evaluator/test code is present at
`d454651ae212144c5c16b53c3041763269967fa8`; this result document does not
change that code. Exact final CI/merge identities are recorded in PR #38.

## Decision and scope

Accept this calibrated, offline **declared-inventory audit and scorer** as a
prerequisite for future fixed-predictor experiments. Do NOT accept any predictor
as a product-quality oracle on this evidence. No external model training or
inference was performed, and no measured MOS was created. `quality_selection`
remains null even when all input checks succeed. This unit reuses the existing
TSM manifest CSV IO and comparison audio/hash contract; it does not replace the
comparison pipeline or change any DSP, ABI, state, plugin, transport or GUI.

The original OMOQDE/OMOQSE selected-checkpoint test sets cannot be called
independent of model selection: the papers' epoch-selection distance includes
test loss/correlation. This is the specific reason to audit train, validation,
selection and calibration exposure together. The primary references, author
implementation ref, remote checkpoint Git identities, preprocessing constraints
and unresolved model/code redistribution permissions are recorded in
`FIXED_PREDICTOR_PROTOCOL_2026-09-20.md`. Public test replay remains a possible
replication exercise, not independent confirmation for those checkpoints.

## Actual local execution

| Check | Result |
|---|---:|
| Existing evaluation regression with real freshly built CLI and installed R3 library | 59/59 |
| New unittest methods, including rejection subcases | 10/10 |
| Combined evaluation regression after schema fix | 69/69, skip0 |
| Retained full CLI positive controls | 4/4, exit0 |
| Retained full CLI rejection controls | 37/37, exit2 with blocked JSON and no scores |
| Fresh unchanged spectral-ON SDK, one complete CTest run | 26/26, skip0 |
| Existing tracked files checked against verified main snapshot | 267 |
| Unchanged existing files | 266; only dataset-tools workflow intentionally edited |

The local source snapshot was reconstructed from the uploaded main source
archive, verified against all 267 supplied SHA256 entries, and reproduced the
exact base Git tree. The local Git snapshot commit is NOT the remote main commit.
Evaluator/test Git blob identities were separately checked against GitHub after
upload. No old CI log is counted as a new execution.

The CTest inventory and completed log were cross-checked for 26 unique, enabled,
actually passed test names. This evaluation-only change did not require a DSP
compiler/sanitizer matrix rerun locally; the normal product CI still runs on the
PR. No new physical-device, DAW, platform, CPU-capacity or hard-realtime claim is
made. Runtime files, public headers, adapters and application sources are unchanged.

## Analytical comparison, not model performance

Each positive control uses the same complete 24-row generated grid: 3 original
synthetic source IDs × 2 **artificial** engine labels × 48/96k × output/input
ratios 0.8 and 1.25. Reference tones are 223/260/297Hz with 40ms reference length;
processed tones are generated analytically at the requested length, not produced
by a real TSM engine. Labels and predictions are explicitly `synthetic_fixture`.

| Prediction control | RMSE | Spearman |
|---|---:|---:|
| label itself | 0 | approximately +1 |
| label + 1 | 1 | approximately +1 |
| 6 - label | 2.064077679416806 | approximately -1 |
| constant 3 | 1.032038839708403 | null (undefined) |

All four CLI RMSE values agree with direct analytical calculation within 1e-12.
Independent vector controls also check fixed bias, reversed ranking, ties,
constant labels, undefined correlation, fixed-bin bias and out-of-range scores.
The +1 control shows why high correlation alone does not establish calibration.
No clipping or refitting conceals its error. Per-source/category/engine and
category×engine summaries retain each group's count; source-cluster bootstrap
is deterministic (1000 draws, seed20260920) and conditional on observed engines.
It is not a claim of natural-audio uncertainty from these synthetic examples.

All 37 rejection cases are retained in the generated summary: source/engine/
selection/calibration overlap; renamed identical reference; unknown inventory;
unreviewed aliases; empty development; duplicate/missing/extra/failed/nonfinite/
overflow predictions; missing/nonfinite labels; changed weights/preprocessing/
audio/plan; receipt mismatch; incomplete grid; zero output and both signals zero;
nonfinite audio; stereo; pitch; formant; freeze; duration mismatch; metadata;
undeclared rate; duplicate/ragged CSV; duplicate JSON key; escaped path; malformed
artifact inventory. The scorer never scores only the surviving subset.

## Observed failures and repair

Initial unconfigured existing regression: 3 errors for missing BOILED_EGG_CLI or
BOILED_EGG_RB_LIBRARY. After a fresh build and explicit paths it passed 59/59.
The early combined build/CTest command and first CLI artifact run hit container
execution limits; incomplete logs remain separate. They are not counted as
complete runs. A subsequent complete CTest run passed all 26, and the complete
final CLI grid passed all 41 runs.

Review found a real new-evaluator defect: a JSON array containing artifact-role
names escaped the initial set-membership check and raised AttributeError, exiting
1 without report.json. Commit `b0ab9124` adds a mapping-type check;
`d454651a` preserves it as rejection37. The same malformed case now exits2 and
writes a blocked report with scores=null. All 69 tests and all 41 CLI cases were
re-executed after the fix; pre-fix measurements retain their original source hashes.

## Identity and reproduction

SHA256 of final measured source:
- `eval/fixed_predictor.py`: `ffae60adea7e2669d4b3e3e5f0e1528a87cd4605fcc5418e6b1ce44f2c3edf31`
- `eval/test_fixed_predictor.py`: `bc6d064fc7dd2d313127ca925dc6d4c682c57c89b198064b8b78bc686e9e5d41`

Local final `calibration/summary.json`:
`d5d0a39ba0af7df58d8a08ce9d887d3e54a4cfe623805b186b855de89caae1eb`.
The full artifact retains each plan/CSV/raw WAV/receipt/report and hashes.json,
all attempts, exact source identities, interpreter/library versions and the
unchanged product binary hashes. CI artifacts use their own hashes/paths and
must not be relabeled as byte-identical local receipts.

From repository root, with the existing numerical dependencies installed:

```sh
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 \
  python -m unittest -v eval/test_tsm_dataset.py eval/test_fixed_predictor.py
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 \
  python eval/test_fixed_predictor.py --evidence validation/fixed-predictor
```

The second command requires a new destination and leaves a runnable synthetic
plan example at `validation/fixed-predictor/perfect/plan.json`. For actual fixed
predictions, provide the frozen plan SHA from a separate prior registration:

```sh
python eval/fixed_predictor.py --plan PLAN.json --plan-sha256 REGISTERED_SHA256 \
  --predictions predictions.csv --receipt receipt.json --output NEW_DIRECTORY
```

A hash alone does not prove preregistration chronology, corpus completeness,
correct aliases, label origin or actual model execution. Those are external
review obligations. The manifest ratio is actual output/input duration (as in
the existing importer), checked within 1e-8; it is not an inferred playback-speed
control. Pure TSM, mono, pitch0/formantOff only. Unsupported domains are blocked.

`dataset-tools` now pins NumPy2.3.5/SciPy1.17.0/SoundFile0.13.1 and tests Python
3.11/3.13. It requires exactly13 unique executed unit methods with no skips,
runs all CLI controls, and uploads full source/input/result hashes even on failure.

## Remaining work, explicitly not completed

The mounted handoff lacks ref_test.zip, test.zip, TSM_MOS_Scores.csv and model
weights. Author repository weight entries were found, but no checkpoint was
loaded. A real adapter must pin and verify preprocessing/dependencies/weights,
execute actual inference, resolve permissions and map the full development
inventory. Published test data alone do not remedy test-informed checkpoint
selection. Independent source/engine MOS data or a separately preregistered
unexposed model-selection protocol is needed for independent qualification.

No adoption decision for music/speech categories, pitch/formant/stereo/freeze,
no naturalness superiority and no native-zplane/Signalsmith comparison follows
from these calibration results. #17 and the parent roadmap remain open; #31's
historical-mode/hardware/platform work is unchanged. C1/C2/#32 are not reimplemented.
