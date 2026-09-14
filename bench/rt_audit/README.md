# Real-time measurement audit

Standalone Linux tooling, not part of the installed library or any audio callback.
This directory does not promote the research DSP or alter product ABI, profiles,
state, plugin IDs, latency, or default builds. Its C++ protocol and Python receipt
checks are correctness gates; a fast result on a shared runner is not an RT certificate.

## Build and run

```sh
cmake -S bench/rt_audit -B build/audit -G Ninja -DCMAKE_BUILD_TYPE=Release
cmake --build build/audit -j2
ctest --test-dir build/audit --output-on-failure
python -m unittest discover -v -s bench/rt_audit -p 'test_*.py'
python bench/rt_audit/run_matrix.py --probe main="$PWD/build/audit/rt_audit_probe" \
  --matrix observer --count 12000 --output results/observer
python bench/rt_audit/analyze.py results/observer --output results/observer-summary.json
```

The default backend is the current shipping fixed-I/O C API with static pitch.
`-DRT_AUDIT_RESEARCH=ON -DBOILED_EGG_SOURCE_ROOT=/path/to/research-worktree`
uses a compatible research host API instead. That mode requires the later host
bridge sources, not the historical research directory on main. It drives Fuzzy /
Harmonic / scheduled-SIMD and four formant events per callback. The product
backend has no corresponding formant automation: do not interpret the two labels
as equal-function performance or quality competitors.

Use `--matrix periodic --count 3000` for 48/96 kHz, 32/64-frame, six-pitch repeated
fixed-release runs. Do not run compilers, corpus rendering, tests or multiple
probe processes concurrently with a measurement. Record the source revision,
compiler flags, linked-library hashes and hardware outside the executable-hash
receipt too; the default product library may be shared.

## What is measured

`legacy` deliberately reproduces CPU-start / wall-start / work / wall-end /
CPU-end nesting. Timer work is inside that CPU bracket. `cpu` and `wall` are
separate passes with only the selected clock around the declared work. The
selected timer still has its own boundary cost; no control percentile is
subtracted. The outer MONOTONIC interval includes setup and observer work.

Saturated runs are continuous throughput/stress trials. CPU time exceeding
`block/rate` is a **CPU-period exceedance**, not an observed DAW xrun. Periodic
runs use absolute MONOTONIC releases, exact accumulated frame times and the
original next release as the deadline. They report entry lateness, callback wall
time, release response and missed-release episodes separately. Late slots are
neither skipped nor rebased. Lateness may include scheduler delay and the prior
iteration's harness overhead; it is not automatically an OS-cause attribution.

Warmup extends beyond the declared latency plus half a second of processed
samples. Every cold row remains in the CSV and report. Inputs/result buffers are
prepared before timing. Logging, hashes and finite-output checks occur outside
the inner bracket. The outer protocol still has overhead and is not a real audio
device, interrupt or DAW scheduling path. No SCHED_FIFO, governor, FPU-mode or
machine-wide scheduling change is made. The selected CPU and policy are recorded.

## Evidence and interpretation

A declared plan fixes variants and repeats. Every trial has CSV/metadata hashes;
`COMPLETE.json` is published only for a completed matrix. Analysis rejects missing
or duplicate cells, inconsistent clocks/deadlines, runtime failures and changed
output-fingerprint sequences. The per-sample rolling output fingerprint is not a
cryptographic WAV proof. Quantiles use nearest rank. Raw maxima, cold starts,
miss counts and consecutive miss episodes are preserved without outlier removal.

A bad no-op control means the environment/measurement cannot qualify hard RT;
it does **not** prove every audio miss is noise or license dropping those misses.
Observer overhead can explain some apparent DSP spikes while genuine long wall
intervals remain. A production acceptance run needs a declared hardware/OS/host
support envelope, verified observer controls, device/host scheduling traces and
repeated audio runs. Objective equivalence, ABI/no-allocation tests and listening
remain separate DSP promotion gates. Passing this tooling's CI does not pass them.

CI explicitly selects `shell: bash` so test failures survive `| tee`. The shell
regression demonstrates why `bash -e` alone can falsely return success. No noisy
shared-runner timing maximum is relabeled as a deterministic correctness gate.
