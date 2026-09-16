# Objective-first spatial qualification

Roadmap #15/#17, Issue #25, draft PR #26. Correctness and a reproduced numerical
invariant defect can be repaired without waiting for listener responses. This is
not a claim that a single metric replaces human preference or certifies all music.

## Three distinct layers

1. Analytical targets and metamorphic invariants: duration, pitch trajectory,
   channel ratios, silent channels, exchange covariance, same-state block
   partition, reset and allocation/thread contracts. Use calibrated negatives
   and fixed thresholds, not candidate-dependent score fitting.
2. Artifact diagnostics: separate relative waveform error, interchannel level
   and phase, common-phase-invariant channel-vector distance, envelope and timing.
   A projector cannot detect common-mode coloration; a single spectral average
   cannot rule out a localized transient error. Never silently fit gain or lag.
3. Perceptual estimators: OMOQDE/OMOQSE are relevant to TSM; ViSQOL and Zimtohrli
   have their own reference/alignment assumptions. Before using a learned score
   as a gate, freeze its model and validate on genuinely held-out source and
   algorithm groups. Predicted MOS is not a new listener submission. No such
   model was run or trained in this patch.

Primary method references are in PROTOCOL.md. AMENDMENT.md retains the rejected
first predictor, its exchange failure, and the final pooled-increment design.

## Build the actual candidate

This branch stores an explicit patch. Merely checking it out does not replace
its default DSP. Use a disposable copy of the pinned public spectral preview:

```sh
# In the preview worktree at f8e5ef2cbce84f396597860a408b4a3084796115:
git apply /absolute/objective-branch/quality/objective_audio/pooled_static_stereo.patch
cmake -S . -B build -G Ninja -DCMAKE_BUILD_TYPE=Release \
  -DBOILED_EGG_ENABLE_EXPERIMENTAL_SPECTRAL=ON
cmake --build build -j2
ctest --test-dir build --output-on-failure
# Build a separate UNPATCHED copy as the comparison baseline.
```

Do not stack `static_stereo.patch` and `pooled_static_stereo.patch`. The former
is a rejected pilot. The final patch changes only static multichannel, non-Fuzzy
PV: one bounded rotation is applied to the original complex channel vectors;
interframe phase increments are combined on the circle with spectral-power
weights. Mono, dynamic timeline and ordinary WSOLA arithmetic are unchanged.

The paired study expects each backend CLI's shared SDK beside its executable:

```sh
python -m unittest discover -s quality/objective_audio -p 'test_*.py' -v
OPENBLAS_NUM_THREADS=1 python quality/objective_audio/study.py \
  --baseline /absolute/original/boiled_egg_backend_cli \
  --candidate /absolute/patched/boiled_egg_backend_cli \
  --suite confirmation --output results/confirmation --workers 2
# --suite replication for the declared synthetic regression;
# --suite mono --refs /absolute/20-reference-folder for actual mono compatibility.
```

The original stereo/time audit is a separate pinned dependency from
894476d1c5a44cd0c2c9ff1cccb34e0fca792f5c. The dedicated workflow checks out both
sources explicitly. It applies the patch, runs the full preview CTest, spatial
regression, metric calibration and old audit with its unchanged 1e-5 controls.
Compiler and ASan/UBSan jobs exercise the patched DSP, not only a dummy helper.

## Performance is a separate result

`static_capacity.cpp` measures static pitch .5/1/2 at 48/96k, two qualities,
three policies and 32/64-frame blocks. Compile against the chosen installed or
build-tree SDK. Run each pitch with repeat arguments 1,2,3 and feed each group
of three CSVs to the pinned `quality/dynamic_pitch/summarize_bench.py`.

Warmup is declared latency plus .5 seconds; timing is wall-only; generation and
hashing are outside the bracket. The state-best criterion is not WCET and does
not stitch an uninterrupted run from minima. Preserve raw misses/maxima, real
complete-run counts and the measured added cost. Do not rebuild a measured
library in place while a study is running.

The final report records 72/72 capacity settings within the unchanged 80% budget,
but increased CPU cost; this is not a speed optimization or automatic promotion.

## Publication boundaries

The committed metric suite has eight tests. A later supplementary same-target
artifact diagnostic was blocked by the connector during publication. That file,
its six tests and a post-hoc unity audit are explicitly local-only in the delivery,
not in checkout/CI. They are not dependencies of the committed study or workflow.
The blocked write was not retried through another path or action.

No source recordings, external engines, font files or generated listening scores
are committed. Original/raw failures and scoped negative evidence are retained.
