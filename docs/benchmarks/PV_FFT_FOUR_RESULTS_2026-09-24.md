# Exact length-four FFT batching — results, 2026-09-24 JST

Issue73, parent67/69/15. Base main0d3feae8bb85b39f5058eecf8d77b6869c5cd476,
tree b7802edbac925df1d58f659b21d2f0761c21d7b0. PR64/68/70/72 are already accepted.
This is an incremental cost optimization, not new formant/pitch quality research.

## Scope and decision

Only fft_plan::advance's length-four stage has new runtime code:39 lines batch
complete four-point groups when column0 and budget>=2. Roots are reused but never
replaced by mathematical shortcuts. Scalar multiplication/addition/subtraction
and two-lane SSE2 grouping remain identical. Partial and odd budgets use the old
path. At each return the complete coefficient array, cursor and return value must
match the actual predecessor, not just the final FFT output.

Immediate FFT, all other stages including the accepted length-two optimization,
normalization, scalar/SIMD selection, scheduler work/yields, FFT/window/hop and
all class members are unchanged. No new table, sample buffer or instance heap
allocation. Local register/temporary choices and machine-code size may change;
this is not a claim that every kind of memory usage is identical. Public
ABI/state/IDs/defaults/latency/tail, WSOLA, formant algorithms and GUI are unchanged.

The predeclared fixed-I/O mean-cost gate passed. Retain this as a same-output
optimization, subject to exactHEAD CI/review. Deadline qualification did NOT pass:
real deadline failures and two regressions in complete-run counts remain below.
No hardRT,96k support expansion, naturalness or vendor-superiority claim.

## Registered experiment and actual execution

Issue73 hypothesis precedes implementation. Protocol5ee5423717a010a650b1bec598da915195f1c2a1
precedes all full audio/cost measurements. Plan
cc63154f4c45c03d5ecbd0897ef1b28d1eb5b67cf7ffce5c4430bf0ec6ad0bec
was registered in Issue73 comment5800170710 before execution. It binds411 measured
source files, fresh baseline/candidate libraries, the same public renderer,
linked dependencies and inputs (419 source/binary/dependency identities),CPU0.
The final results document is added later without changing measured code.

The unchanged quality/pv_ring comparator and quality/formant_detail renderer,
fixtures, metrics and receipt validator are reused. Four known synthetic families
x48/96k x+/-12st xdetail0/1 x3repeats xold/new give192 streaming outputs. They are
regressions, not a natural-voice holdout. Cost has64settings x3 xold/new=384 outputs:
vowel120,2seconds,48/96k,mono/stereo,32/64frames,+/-12st,stream/fixed,detail0/1.
Old/new order alternates; CPU is fixed; no local builds ran during measurement.

Both complete grids passed on their first run. All576 output PCM files and576
receipts were independently read and checked for hash, real length, finite and
nonzero values, receipt equality, exact paired bytes and full-grid membership.
All288 old/new PCM/metadata pairs match; all96 acoustic pairs match. All repeated
outcomes match. No clipping, gain/lag fitting, partial-success denominator or
post-result waveform/threshold adjustment is used.

## Cost results (candidate/predecessor)

Use each setting's median of3 mean service times per input block. No per-pull
normalization or aggregation of best callbacks from different runs.

|Path|Settings|Median ratio|Maximum ratio|Faster settings|
|---|---:|---:|---:|---:|
|Fixed-I/O|32|0.9613403595|1.0705665066|30/32|
|Streaming unchanged-path control|32|0.9946454553|1.0577184953|18/32|

Fixed-I/O median is about3.87% lower service time. The two slower settings are
48k/mono/64/-12/detail1 (1.0705665) and48k/stereo/64/+12/detail1 (1.0031319).
All fixed96k settings are faster in this run (stratum median0.96357010,
maximum0.98911070). Fixed48k median0.95805937. Both the explicit fixed-I/O
median<=1/max<=1.25 goal and the unchanged pooled64 gate pass. Streaming is a
control, not an optimization claim. Do not multiply this ratio by an earlier
session's speedup to claim an unmeasured cumulative improvement.

## Deadlines: independent observations, not a speedup certificate

|Fixed-I/O rate|80% criterion settings before/after|Actual period misses before/after|Runs with every callback in-period before/after|
|---|---|---|---|
|48k|14/16 ->15/16|38 ->49|32/48 ->30/48|
|96k|6/16 ->4/16|127 ->108|14/48 ->12/48|

The80% criterion takes the best of3 per-run maximum period ratios within a
setting, then tests each setting separately. The actual full-run counts do not
use those selected best values. The worst setting's best maximum ratio is
48k1.3826505 ->1.252269;96k2.555646 ->3.242658. The48k miss count and both complete-run
counts worsen despite lower mean cost. Retain these outcomes. This is an unpaced
shared environment; do not label every spike an interruption or promise hardRT.
Streaming callback periods are recorded but not qualified as fixed-I/O deadlines.
All services, per-run p99/max, short final periods, creation and flush remain raw.

## Correctness and negative controls

The actual immutable predecessor FFT source/header are SHA-checked and compiled
in a second namespace. The added length4 test covers4992 entry/partial-boundary
cases, including column0/1 and stage crossing. All earlier full-prefix, immediate,
zero/signed-zero,zero-budget,noallocation and shared-plan independent-cursor
controls are executed against this newer predecessor too. No expected output is
substituted from the candidate. An altered predecessor is rejected by CMake.

Local verified unique/executed counts, skip0:
- GCC/Clang C++20/23:9CTest each.
- Explicit SIMD-disabled build:9; Clang ASan/UBSan/leaks:9.
- TSan shared immutable plan with independent cursors:1.
- Existing public formant/ring controls:13.
- Fresh full SDK spectralON26/OFF13; relocated shared C11/C++5 each.
- Existing comparator/provenance Python controls:11; chained source-audit tests:28.

Only three existing files change:fft.cpp, the audit entrypoint and its workflow.
All earlier strict scopes stay unchanged. The new scope first validates the
complete predecessor chain, then permits only the exact old/new fft.cpp hashes;
all other src/include and protected adapters/eval/research must match. Unknown
references, extra/missing/changed runtime files and protected-tree edits are
negative controls. Old executables/export/fullCSV/PCM comparisons are not removed.

A workflow transcription omitted -lm in an uncommitted Git tree. Exact local/remote
tree comparison detected it; it was corrected before commit/ref update. No measured
source or runtime binary changed and no CI failure was hidden. Final source has
412 files:401 unchanged from the404-file base,3 modifications and8 additions.

## Identities and reproduction

Baseline SDK ELF SHA256:
f74b4d6e4ba81d8a8b93d0f628df9c093d02c4d7a8f92bf26857e4b577279913
Candidate SDK ELF SHA256:
ad5854496999f5a20298f101771065950434a35492b7f33426b3dd42b1ab74e9
Old fft.cpp SHA256:
bf6a0c99952c1983f611488f5cb029c77d5dd5858c86f122853f79a70a870b5c
New fft.cpp SHA256:
fe63eae1e8113c71d40a0da519108ad6be723d4bcf48ce3f1297899077f18333

Build outside source. Obtain the exact pinned predecessor source and compile its
SDK separately. Build quality/pv_ring for the common public renderer/candidate,
quality/pv_fft_four with BE_FFT_REFERENCE_SOURCE for controls. Use
quality/pv_fft_four/experiment.py prepare to bind a NEW plan; register its hash,
then run --mode quality and --mode cost into new directories. Do not attach these
measurements to rebuilt libraries. Full commands, hashes and individual timings
are in the retained local evidence. Final exactHEAD CI/artifact/review/main results
are recorded in the PR and Issue73; native CI quality checks do not certify the
local performance numbers on a different machine. No vendor execution or Drive writes.
