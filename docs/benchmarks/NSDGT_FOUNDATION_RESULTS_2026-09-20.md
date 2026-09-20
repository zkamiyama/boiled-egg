# NSDGT numerical foundation: results — 2026-09-20 JST

Issue44 / PR50. Base main c8ffe65a24d21e627a3558883497daeb853473de,
tree8db4ba61f000175de9118d60bdee2a2de4a9d7d5. The research sequence is
44 -> 45 -> 46, with47 conditional on measured deficiencies, then separate
48 (NRT product) and49 (bounded-lookahead RT) promotion tracks. Parent19/15,
quality17 and default WSOLA defect41 remain separate. No recurring background
execution is implied by this issue sequence.

## Completed numerical unit, not an audio-quality improvement

An isolated C++20/23 analysis/dual-synthesis library, explicit complex C-callable
research entry, numerical runner/controls and CI were added. All308 preexisting
files are unchanged. Product defaults/ABI/state/IDs/latency/tail, plugins,
transport and GUI were not changed. The existing float FFT is linked unchanged
as a numerical primitive; this is not a new product backend or installed ABI.

SELEBI arXiv:2602.16421v1 II.B/C motivates fixed frequency channel count M and
variable windows/hops. The inverse here is the painless diagonal dual for
W_j<=M. Finite zero extension and centered local phase origin are explicitly
defined in the protocol; they are not the paper's periodic boundary convention.
No external GPL source was copied. SELEBI masks/window scheduling/PVDR phase
propagation and paper-condition TSM remain Issue45, not completed here.

## Mathematical meaning and implementation limits

For local coordinate t=r-floor(W_j/2), coefficients use
C[j,k]=sum x[a_j+t]*g_j[r]*exp(-i*2*pi*k*t/M), placing t in FFT slot t modulo M.
Input indices outside[0,L) are zero, not periodically wrapped. Arbitrary valid
real windows (including asymmetric/signed controls) are supplied explicitly.
The normalized inverse FFT is weighted by g_j[r]/D[l], where
D[l]=sum_j g_j[l-a_j+floor(W_j/2)]^2. Standard coefficient frame bounds are
M*min(D), M*max(D); ratio=max(D)/min(D). Normalized coefficient energy equals
sum D[l]*|x[l]|^2. Float window products/FFT and double overlap/diagonal have
ordinary rounding; exact identities refer to the mathematical operator.

Synthesis receives coefficients and schedule, never the original input. It is
not an identity shortcut. Zero mathematical input is legal; reconstruction of
nonzero input as all-zero is an evaluator failure. Erasing coefficients must
produce zero; scaling coefficients by1/4 must scale synthesis. Arbitrary edited
coefficients need not be a consistent spectrogram. A*S is a projection, not
identity on every coefficient array; idempotence and Hermitian controls check
that distinction. A good unmodified roundtrip does not guarantee perceptual
quality after coefficient modification.

NRT allocation is intentional. L1..288000, power-of-two M16..16384,
W2..M, at most4096 frames/8388608 complex coefficients. Windows satisfy finite
|g|<=1 and validated offsets; analysis input is finite/bounded componentwise1.
Uncovered samples, minD<1e-8 or condition>1e6 are rejected without adding epsilon.
Invalid dimensions, offsets, capacities and budgets are errors. Caller buffers
must be valid/disjoint/stable; reported failure leaves output/info untouched.
Memory estimate bounds explicit peak-live internal arrays conservatively, not
caller storage, allocator overhead or whole-process RSS. No hard-RT/noalloc or
same-instance lifecycle concurrency claim follows.

## Preregistered complete experiment

Protocol commit f4cfab538806cef939341a13b9f8905d5e95050b predates tests/grid.
Plan b26b0cf3d1ac5f870af5801aa1b35f8807d40aa7d9a8060e0e1c9d44501a1c80
was registered in Issue44 comment5748375453 before all measurements.
It binds288 generated input/schedules, measured source/unchanged FFT,
new ELF and linked dependencies, numerical environment and full grid.

Rates22050/48000/96000 are fixture metadata, M1024/2048/4096 respectively.
Lengths17,1001,floor(rate/8)+1. Eight signals: first/middle/last impulses,
real61Hz tone,DC,complex uniform noise(seed20260920),complex chirp,zero.
Four schedules: fixed long Hann, smoothly varying lengths, abrupt long/short
Hann/sqrt-Hann, irregular deterministic hops with Hann/rectangular windows.
All include both endpoint centers. These are numerical stress schedules,
NOT SELEBI onset detection or audio-quality conditions.

288 cells x3 fresh analysis/synthesis executions =864 pairs, all complete.
36 cells are zero controls (108 pairs);252 are nonzero (756 pairs).
Every cell's coefficient and output byte hashes match across3 repeats.
All864 saved complex-output references were read back and SHA256 checked.
Inputs/windows are retained in NPZ without pickle. Full large coefficients are
not archived: their hashes are stored and they are regenerated from retained
inputs. Complete small direct-DFT coefficients/reference/input are retained.
Do not call three repeats independent source observations or MOS trials.

## Results against fixed numerical gates

|Quantity|max observed|fixed limit|
|---|---:|---:|
|Complex sample max error / input peak|3.7239787043e-7|3e-6|
|Relative L2 reconstruction error|1.5222799714e-7|3e-6|
|Coefficient error, normalized by windowed-input L1 bound|6.6676725087e-7|3e-6|
|Native synthesis vs independent complex128 synthesis / input peak|5.3115709514e-7|3e-6|
|Normalized coefficient/frame-diagonal energy relative error|8.6265883396e-8|5e-6|

All gates pass without any threshold adjustment. Mathematical zero returns
exact zero. Imaginary residual for real-input fixtures is retained, maximum
6.1075809299e-8 absolute; it is not silently discarded. The independent large
grid reference uses complex128 FFT/inverse, while small controls use explicit
complex exponential sums, including odd/even/asymmetric/negative windows.

Across accepted schedules: minD1.2501915369, maximum condition7.1327761136,
maximum absolute dual weight0.7998773175. These are observed values, not claims
that arbitrary schedules are well-conditioned. Holes and near-zero-window
counterexamples reject in controls. Largest analytical internal storage estimate
in this grid10,696,768bytes; whole measurement-process peakRSS140,432KiB is
separate and includes Python/numerical libraries/results.

Median across288 per-cell three-repeat median analysis+synthesis call times:
0.000947162seconds, maximum cell median0.013792019seconds. Calls include internal
plan construction/allocation/FFT and dual computation; Python reference analysis
and output serialization are outside that interval. The first pair is separately
retained in rows(0.000130987seconds). These are differently sized numerical cases,
not a realtime callback capacity/cost qualification or a product benchmark.

## Tests and execution provenance

Actual local checks:
-55 unique Python methods,skip0 (11new +44existing scoped evaluator controls).
-GCC/Clang C++20/23:12 enabled/executed CTests each.
-Clang ASan/UBSan/leaks:12/12.
-GCC TSan independent-call test:1/1. Not shared-instance lifecycle qualification.
-Fresh unchanged spectral-ON SDK: inventory/JUnit-checked26/26,skip0 (15.66s).

Controls include direct DFT/exponential synthesis, all74 real/imag canonical
basis impulses of an odd37-sample signal, complex linearity, coefficient erasure,
scaling, inconsistent-coefficient projection, conjugacy, endpoint/one-sample
C11 call, malformed windows/centers/buffer sizes, nonfinite samples,
coverage/budgets, missing/duplicate rows, injected amplitude/phase/zero faults,
invalid numeric receipts, failure JSON and no-overwrite.

No acoustic candidate was optimized in this unit. The initial test-side budget
negative allocated a needlessly large sentinel; it was reduced before the full
grid and native tests rerun. The mathematical kernel/gates were unchanged.
No observed unit or full-grid numerical failure was reclassified as success.
Container git network DNS was unavailable, so the source was restored from the
prior saved source archive and its308-file Git tree matched the remote base.
An attempted interactive execution was unsupported and did not start a process;
subsequent builds/tests used completed synchronous commands. These environment
limitations are not SDK failures or unexecuted test passes.

## Hashes and continuation

Measured ELF SHA256:
bf6eca0fe752e4408816d4919f71c3d5503bf9f5c08386fc228660a58eb61f82
Kernel source SHA256:
1c6b099d827cd66c098faceabe5a0c326e9a2f1a4cdb759e28b0c036ca2903fc
Runner SHA256:
6d08a72653bcf6302bf5c495d12049c7e2f9c6d534f0f9b0cb5098bfbe33d81f
Python test SHA256:
6c71fa648602824e075369a5dc421c94017a0811d8343998db9615744188c5dd

The measured source snapshot predates final CI/result documents; exact measured
source hashes are retained in its plan. Later documents do not relabel a rebuilt
binary. CI executes its own full plan/grid and stores its own source/ELF/timing
identities. Final HEAD, checks, reviewed diff and merge are recorded in PR50 and
Issue44, not assumed by this results commit.

Reproduce with build/evidence directories OUTSIDE the source tree:

```sh
cmake -S research/nsdgt -B /tmp/be-nsg -DCMAKE_BUILD_TYPE=Release
cmake --build /tmp/be-nsg -j2
export PYTHONPATH=eval OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
python eval/nsdgt_foundation.py prepare --library /tmp/be-nsg/libnsdgt.so --output /tmp/be-nsg-plan
# Register the printed plan hash before the new measurement.
python eval/nsdgt_foundation.py run --plan /tmp/be-nsg-plan/plan.json --sha256 REGISTERED_SHA --output /tmp/be-nsg-results
```

Next executable research unit is45: freeze the actual paper/reference conventions,
licenses/unknowns, onset window/hop schedule and phase propagation, then compare
paper-condition TSM before46's48/96k pitch/compression extension. This foundation
alone does not improve bass/attack quality, fix41, or qualify pitch/formant/stereo,
Freeze, naturalness, NRT product jobs or bounded-lookahead realtime.
