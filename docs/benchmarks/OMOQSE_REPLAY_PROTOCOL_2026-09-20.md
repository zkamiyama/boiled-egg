# OMOQSE-CNN replay protocol — 2026-09-20 JST

Base main d0e435053387d1538b379b2076a79fdd10f24330. Related work: #17.
This protocol precedes model inference and examination of prediction errors.
No DSP, public ABI/state/IDs, plugin, application or default backend changes.
No predictor is made a product acceptance oracle. Correctness/anomaly tests
remain the primary gates, as requested by the user.

## Received inputs and bounded choice

Eight uploaded files are archived privately, unchanged, in the user's Drive.
CNN weights SHA256: 261336ab331254259010566ef7b9e8d03a0e65156a2381f6b6605d7d3faa659a.
Author Git blob: 6a0e03bbcb76978cb6223d31c7a566b6ff93a05d (3292618 bytes).
Author ref: zygurt/TSM@51333f70685de94c856efa46d0fb23a99d93921a.
Use only its OMOQSE CNN 2020-08-23_15-11-52 checkpoint in this unit.
GRU/DE/normalization and DNSMOS files are archived, not substituted or scored.
ViSQOL 3.3.3 source archive is preserved; local Bazel and downloadable build
dependencies are unavailable. No alternate implementation is called ViSQOL.

The exact author Eval_OMOQ_CNN.py (Git blob
933251efda052dae7c2a567f210573de02e2ee04, SHA256
154816c4752cba2e3e0cafd6f45fb0d7eb337d30ab5bb2258dbcfa4b47b876ad)
is an external, hash-checked dependency. Extract only its Net AST class; do not
execute its top-level dataset loading, pickle IO or output code. Load the exact
checkpoint on CPU with weights_only=True after hash verification. Never fall
back to unrestricted pickle. Do not ship weights or author source in boiled-egg.
Code/model redistribution clearance is unresolved; execution here is a bounded
research replay, not a legal clearance or commercial integration decision.

## Preprocessing and reproducibility boundary

Read author OMOQSE/Evaluation_Input_Features.py and OMOQSE/OMOQ.py. The former
peak-normalizes and uses signed threshold comparisons (not abs) for edge trimming.
Preserve those semantics, record the removed samples, and do not quietly fix them.
Compute 128 MFCCs plus first delta (width9, order1); explicitly fix FFT2048,
hop512, Hann window, centered reflect padding, 128 Slaney mel bands, power2,
fmin0/fmaxNyquist, DCT2/ortho, lifter0, dB ref1/amin1e-10/top_db80.
Use native 44100 Hz mono test audio, no resampling, gain fitting or DTW.
Reject empty/nonfinite/silent/stereo audio before peak normalization. Reject
insufficient frames for delta; match author's left zero padding below 53 frames.

Author collate_fn_CNN_NChannels re-seeds NumPy from entropy on every call and
selects 53 frames; the evaluator averages16 predictions. Replace ONLY crop
randomness with per-file RandomState seeds derived from SHA256(seed20260920,
processed WAV SHA256). Retain the exclusive upper start bound from the author.
Save all16 starts and predictions. Same seed/file must give the same results
regardless of manifest ordering. CPU1 thread, deterministic Torch operations;
process one crop at a time to match author's eval batch size1.

Lock Python3.11, Torch2.10.0+cpu, librosa0.11.0, NumPy2.3.5, SciPy1.17.0,
SoundFile0.13.1; record actual interpreter patch and transitive versions.
This is a declared deterministic/modern-library compatibility replay, NOT
bit-exact reproduction of the historical training environment or original
entropy-selected predictions. Any feature-default incompatibility is retained
as a limitation, not corrected after seeing MOS. No training or recalibration.

## Fixed complete data and metrics

Reuse existing import_tsm_dataset/tsm_dataset IO and fixed_predictor metrics.
Uploaded test.zip SHA256 fe7aa424d7bbf9c6145633c083083401641cabe3fb775839764b7282c759528d;
ref_test.zip d7930be5a56fb8aa5ef919f123f624d698be71c4b5810f6e2eb07008637a35f9;
TSM_MOS_Scores.csv 423db29274b79a78a51a842b864a8cf3084b269d21d332edf8b1445de2eefaf6.
Use all240 processed files /20 named references /3 dataset method labels,
4 conditions per method/source. Do not exclude extremes by result. Preserve
actual duration ratio and original TSM field separately. Primary labels: MeanOS
(the existing importer choice); preserve MeanOS_RAW without mixing scales.
The supplied source labels group named reference recordings; aliases/other
clips and full development provenance remain unverified.

Bind a JSON run plan to its separately recorded hash before execution; bind
manifest, model/source, adapter, preprocessing, runtime files and environment.
Require nonempty exact240 grid for this replay, unique item IDs and raw hashes.
Keep row-level failures and refuse aggregate scoring on incomplete runs.
Report raw RMSE/MAE/bias/Pearson/Spearman/fixed-bin calibration, per-source,
per-dataset-method, and descriptive source-cluster intervals via existing code.
Compare with fixed constant3 baseline, not a fitted baseline. No MOS clipping.
Run a second identical pass; require all240 predictions/crop schedules to match.

Independent-use status must remain BLOCKED. Published OMOQ checkpoint selection
used test loss/correlation (documented in FIXED_PREDICTOR_PROTOCOL_2026-09-20.md).
Call the existing inventory auditor with selection exposure and incomplete
coverage; do not weaken it to make the data qualify. Replication diagnostics
must be distinctly named and cannot become independent scores. quality_selection
remains null. No category/engine ranking is promoted to product adoption; no
pitch/formant/stereo/freeze or naturalness superiority claim follows.

## Controls and stop conditions

Before real-data scoring test bad/changed weights and source, malformed/mutated
plan, wrong model identity, partial/duplicate grids, nonfinite/silent/stereo
input, input mutation, unsupported scope, pre-existing output directory and
failed inference. Failures must leave evidence, not surviving-subset scores.
Verify preprocessing against author loop semantics on positive/negative edges,
feature dimensions, 53-frame boundaries, deterministic crop bounds/padding,
constant/bias/rank controls using existing metric tests. Network test must use
the real uploaded weights, assert exact checkpoint key/shape loading and compare
wrapper output to the same external author Net on identical crops. Synthetic
signals validate the execution path only, never measured MOS.

Freeze protocol changes as a new experiment if changes are needed after observing
scores. Preserve failures and code/measurement hashes. Only calibrated adapter,
tests and documentation may merge after final-HEAD CI and review; no datasets,
weights, private Drive URLs or third-party source enter the public repository.
