# RT measurement-method audit — 2026-09-14 JST

## Decision and merge scope

**Some apparent DSP CPU spikes are observer/bracket events. They cannot all be attributed to DSP computation.** A no-op trial records CPU 2,416,555 ns while its inner wall interval is only 106 ns. However, isolated wall measurements still contain long audio intervals. This finding does not justify deleting all outliers or declaring hard-realtime success.

The main-based `quality/rt-measurement-audit` branch contains standalone benchmark tooling, calibration tests, documentation and its CI only. Base main is `6374d0503f036921e6a2ec757c1a8785430d2e36`. No product source, public ABI, installed headers, existing plugins, state, root CMake/default build, latency or algorithm changes. This is a reviewable tooling change, **not promotion of the latest research DSP**. No merge into main was executed by this work.

Separately, four research workflows were hardened to propagate piped failures: research-features, research-phase-owner, research-phase-innovation and research-execution-host. Their research-branch commits are eddda9f0, d9c5b803, 711211dc and 6056767e. This does not import those workflows or the research branch into the main PR.

## What was wrong with the earlier interpretation

1. The nested CPU-start / wall-start / callback / wall-end / CPU-end pattern includes wall-clock observation inside CPU time. A long observer call or interference during that observation can inflate the CPU column without a long callback body.
2. Continuous, non-sleeping execution measures a saturated workload. Comparing its CPU time to block/rate is useful as a stress diagnostic, but is not an observed device/DAW xrun count.
3. A fixed 200-iteration warmup is not a rate/block/latency-independent definition of steady state. The new protocol processes declared latency plus at least half a second and retains all cold rows separately.
4. Unspecified GitHub Actions shell and explicit `shell: bash` differ. The former uses `bash -e`; explicit bash adds `-o pipefail`. Several research tests piped to `tee` could falsely report success. A deterministic subprocess test returns 0 for the old shell and 7 for the same failed command under pipefail. This is a latent false-green defect, **not an explanation of the previous jobs that failed before any step ran**.

CPU-only still includes its own clock boundary cost. Wall-only also has observation cost. We do not subtract a separately measured no-op percentile: quantiles and interference are not additive.

## New implementation

`bench/rt_audit` is a separate Linux C++20/23 program plus standard-library Python tools. It supports legacy nesting, CPU-only and wall-only passes; no-op and fixed-80,000-integer-work controls; saturated and absolute-periodic schedules. Input samples and result storage are prepared before measurement. CSV output, output fingerprinting and validation occur outside the inner bracket. No concurrent probes, compilations, tests or corpus rendering overlap recorded measurements.

Periodic timing uses exact accumulated frame times, not repeated truncated nanosecond periods. It preserves the original release sequence through missed deadlines without skipping or resetting late slots. Wake lateness, inner execution, outer observer-inclusive duration, release response, slack, missed-release episodes and raw maxima are separate. Late-on-entry can include OS scheduling and the previous harness iteration's work; it is not a proven scheduler-only cause.

Runs pin the first permitted CPU under the existing SCHED_OTHER policy. No realtime privilege, governor, FPU, global scheduler or machine policy change is made. This sleep-based test is not an audio driver or DAW. No-op failures invalidate this environment's ability to qualify hard realtime; they do not make recorded audio misses disappear.

Every declared matrix must finish before COMPLETE.json is published. Analysis checks receipt hashes, exact cells/repeats, row counts, clocks, warmup, status, deadline arithmetic and output-fingerprint sequences. Nearest-rank quantiles, cold maxima and all misses remain. The rolling audio fingerprint is not a cryptographic whole-WAV proof. The product may be dynamically linked: retain the actual library/source identities as well as probe executable hashes.

## Provenance and scale

Ordinary research source was restored from the verified 8401ddaa archive. The innovation variant is the prior delivered innovation-measured source, with its compile-time isolated coherence guard enabled. This is not a claim of a new exact checkout of every file on the latest research branch.

Product source was taken from that source archive only after checking Git tree identity against main for src, include, tests, adapters, cmake and tools, and exact root CMake blob identity. All those product-relevant trees match main. The surrounding archive's later research/docs are not relabeled as main. Source archives, hashes, build flags, binaries' identities and raw receipts are retained in the accompanying evidence.

- Observer matrix: ordinary/innovation, three workloads, five timing protocols, three repeats, 12,000 steady calls/run: 90 runs, **1,080,000 steady calls**.
- Periodic wall matrix: innovation/main, 48/96 kHz, stereo, 32/64 frames, six static pitches, three repeats, 3,000 steady calls/run: 144 runs, **432,000 steady calls**.
- Total: **1,512,000 steady calls plus 281,466 retained warmup calls**. All runtime status checks succeed. Output-fingerprint sequences agree across protocols/repeats within the same backend/configuration.

Research runs use Fuzzy/Harmonic, scheduled+SIMD and four formant events/callback. Main uses its existing fixed-I/O product API and no formant automation. They are separate diagnostic workloads, not an equal-function performance contest. No user recordings, native vendor engine, new audio-quality score or listening result is involved.

## Direct observer evidence

File `ordinary-noop-saturated-legacy-96000-32-+7-r1.csv`, row index2352 (after warmup):

| Recorded interval | Value |
|---|---:|
| CPU bracket | 2,416,555 ns |
| Inner empty-work wall bracket | 106 ns |
| Outer observation interval | 2,418,376 ns |
| Nominal 32/96k period | 333,333 ns |

There is no DSP call in this trial. The large event lies outside the inner empty workload. The result is evidence of observation/bracket contamination, not proof of a specific physical timer, VM or kernel mechanism. Another no-op trial has CPU1,762,885ns with inner wall31ns. CPU-only no-op also has rare spikes, so merely removing the nested wall read does not remove every timer/environment tail.

All saturated wall-only no-op trials have zero period exceedances in 72,000 steady calls. Periodic no-op trials nevertheless have **4,776 release misses**, of which **4,763 are already past their deadline on entry**. This distinguishes observed response failures from callback-body cost. It does not isolate whether each late entry came from the kernel or prior harness work.

Fixed-count integer and isolated audio wall trials still have long intervals. Therefore the experiment does not establish that all previous or new audio spikes are measurement artifacts. No old maxima are erased or retroactively marked as passes.

## Periodic audio results

Below: worst pitch of the per-cell three-repeat median inner-wall p99 divided by block/rate. Counts aggregate 54,000 steady calls per row. `Release misses` includes wake/harness/observer effects; it is not an actual audio-device xrun count. All raw maxima, including the 72.187ms main wall sample, are retained.

| Backend | Rate/block | Worst median p99/period | Inner wall above period | Release misses | Already late on entry |
|---|---|---:|---:|---:|---:|
| Main product | 48k/32 | 0.821 | 93 | 825 | 672 |
| Main product | 48k/64 | 0.361 | 35 | 419 | 374 |
| Main product | 96k/32 | 1.430 | 687 | 3458 | 2485 |
| Main product | 96k/64 | 0.764 | 120 | 2178 | 1998 |
| Innovation research | 48k/32 | 0.284 | 48 | 574 | 503 |
| Innovation research | 48k/64 | 0.309 | 83 | 1142 | 1031 |
| Innovation research | 96k/32 | 0.810 | 265 | 3512 | 2968 |
| Innovation research | 96k/64 | 0.507 | 105 | 659 | 482 |

The same environment also affects the already-existing main product. That observation argues against a universal zero-outlier shared-VM gate; it does not prove the research implementation is qualified. Saturated and periodic results are not pooled as interchangeable distributions. We did not fit a new threshold to obtain a pass.

## Validation and readiness

The unchanged main product passes 9/9 local CTests in GCC14.2 and Clang17, C++20 and23. The separate audit builds under the same four configurations; each passes 36,023 deterministic timer/release/warmup calibration checks and real fixed-I/O smoke. Python has 13 passing calibration/integrity/shell tests. Clang ASan+UBSan with leak detection passes the audit calibration and real processing smoke. Test-source blobs were checked against GitHub after upload.

At audit code checkpoint **1338a0a5b88b842f0668c8af08bf52f424089592**, hosted run **34798350846 passes all five jobs**: GCC/Clang x C++20/23 and sanitizer. They use explicit bash/pipefail. Timing smoke checks correct execution, not noisy shared-host performance qualification.

At research hardening checkpoint **6056767e609306d9babea29415b981077eb7879c**, run **34798207251 passes all four jobs**, including Python3.11/3.13, the scheduled quality run, TSan and actual loaded CLAP/VST3 modules. These runs succeeded after hardening; this does not prove pipefail caused recovery of the earlier step-less failures. Those earlier failures' original causes remain unknown.

Merge decisions must be scoped:

- **Main tooling PR:** source/ABI/default behavior unchanged; local tests and the new hosted correctness gate pass. This is suitable for code review as an independent merge, not an all-research merge.
- **Research DSP promotion:** still requires its explicit feature/quality support envelope, listening approval and host/hardware-qualified timing evidence. Neither empty-control contamination nor this tooling's green CI supplies those missing results.
- **Native zplane superiority:** not evaluated here and not invented as a promotion result.

The corrected practical acceptance process is: qualify the measuring environment with controls; use a declared audio-host/hardware configuration; preserve wall response and repeated tails; keep numerical/ABI/no-allocation correctness separate; block performance claims when controls fail. Do not hide real failures by subtracting noise, filtering samples or disabling CI gates.

## Primary references

- GitHub Actions shell/pipefail semantics: https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax
- Linux thread CPU versus monotonic clock definitions: https://man7.org/linux/man-pages/man2/clock_gettime.2.html
- Absolute sleeps and interruption behavior: https://man7.org/linux/man-pages/man2/clock_nanosleep.2.html

Reproduction commands and protocol limitations are in `bench/rt_audit/README.md`. The delivered evidence contains all raw trials, logs, code and provenance, not source audio, fonts or third-party vendor binaries.
