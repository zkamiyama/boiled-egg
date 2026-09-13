# Cooperative execution, SIMD and fixed-latency hosts — 2026-09-13 JST

## Decision and scope

Implemented cooperative FFT/frame execution and connected the inherited SSE2 kernel to the real DSP. Added a fixed-delay research C bridge, lock-free formant mailbox, input-sample-offset events, state handling, and actual isolated CLAP/VST3 Formant Lab modules. Callback p99 improves substantially while 1,800 paired corpus WAVs remain byte-identical. **Rare CPU deadline misses remain; hard-realtime safety is not established.**

Work remains on `research/formant-v0.3-integrated`. Product core, product C ABI, existing adapters, product state and main are unchanged. No backend was promoted, no human listening was performed, and no native-Elastique superiority or MOS transfer is claimed.

## Commits and provenance

The starting source was `c92d3c213388cdd58996ff3c09adcda94c5a9139`, containing the interrupted resumable-FFT/SSE2 and execution-API groundwork. This pass completed the runtime and host integration rather than claiming that inherited work as new.

| Commit | Change |
|---|---|
| `80eddb94` | Exact scheduling/SIMD/automation regression |
| `712d2b15` | Cooperative PV, Fuzzy, resampling and Multi-resolution runtime |
| `045d7283` | RAII, no-allocation tests, build targets and callback benchmark |
| `50cca7aa` | Explicit scheduled/SIMD CLI controls |
| `46c90435` | Fixed-delay C/C++ host bridge, mailbox, events, state and tests |
| `f83e5a0a` | Isolated real CLAP/VST3 modules and loaded-module tests |
| `817a2f1b` | Corpus replay, scheduled tonal gate and complete-grid benchmark summaries |
| `712b9b89` | Dedicated execution/host CI |
| `0321326e` | ASan-compatible test allocation interception and host README |
| `e5a166bb` | Compatibility repair for the isolated overlap-guard experiment patch |

Normal DSP/host checkpoint: `0321326e288a4d8e30bc31c9c2513c9c37422333`, tree `fb03a46d4155d80703cbfe039d2d125f4bb8b7db`. Downloaded CI artifact10315453826 from run34750434650 passed CRC/SHA256 and all **210 tracked-file hashes**, matching the measured local tree. The subsequent `e5a166bb7909a0252781e5fb5775413728804f83`, tree `6e5e3524dbd1a80e22edfea84288d25a4e14b7b0`, changes only the isolated experiment patch. Normal runtime and plugin code remain unchanged. This result-record commit changes documentation only.

All binaries and source inputs are independently fingerprinted in the delivery. Existing corpus measurements retain their actual baseline/candidate executable identities. Same-toolchain byte equality is not cross-compiler or cross-architecture identity.

## Cooperative execution contract

This is single-audio-owner cooperative processing, not a background DSP worker. Persistent C++20 coroutines are allocated during construction, never during push/pull/reset. Windowing, FFT, cepstral/formant processing, ownership/Fuzzy classification, phase synthesis and overlap-add are split into bounded chunks. FFT slices advance128 work units; most spectral loops yield every32 bins. OLA cleanup, resampling and Multi-resolution pairing are also bounded per input tick.

Formant targets latch at frame start, preventing mixed settings inside a partially processed frame. A frame-budget overrun is counted and returned as an error, not concealed by an unbounded synchronous catch-up. Input ticks govern scheduling independently of caller block partition; this is not the previously rejected high-branch stagger.

SSE2 accelerates two-complex FFT butterflies without reassociation. Scalar fallback and a forced-scalar build remain available. No AVX/NEON implementation is claimed. Numerical ordering, phase RNG and raw output are preserved. The principal improvement is workload distribution, not elimination of total work.

Opt-in scheduled execution requires **time=1, static pitch in[0.5,2], configured hop>=64**. Changing pitch after input starts or requesting another time ratio is rejected. Immediate scalar remains the compatible default. CLI flags are `--execution immediate|scheduled` and `--simd off|on`. Offline flush/reset may finish pending lifecycle work and must not be mistaken for bounded host-callback tail draining.

## Fixed latency and host automation

New headers: `boiled_egg_research_host.h` and its movable C++ RAII wrapper. This is an isolated research ABI. Construction selects a manual profile, a static pitch, centered/scaled analysis and execution policy. The bridge emits one output frame per input frame: an initial zero prefix followed by the fixed delayed DSP output. Silence input drains the tail; the host path does not call offline flush.

Fuzzy/Transient/Fuzzy-noise have **2,688 samples at48k (56ms)** and **5,248 at96k (54.667ms)** of fixed output delay. General and Multi-resolution have their own construction-time values. The delay is independent of formant changes, SIMD and caller block partition. This is an actual output delay, not the older research latency query's conservative input-lookahead hint. It is not low-latency monitoring qualification.

Up to256 sorted events per block are validated before DSP/output mutation. Invalid offsets, sizes, nonfinite values or ordering are rejected; duplicate offsets use the last value. The target arrives before that input sample, but **spectral response is frame-latched and smoothed with a10ms time constant**, not an instantaneous sample-resolution formant warp. UI/state requests use lock-free uint32 latest-value mailboxes, consumed once at block start before timestamped events. Lifecycle reset/deactivate/destroy requires exclusion. An internal underrun faults the handle until reset instead of silently changing delay.

The separate **Formant Lab** CLAP/VST3 plugins expose only a +/-12-semitone formant parameter, Fuzzy/Harmonic, float32 stereo. **Plugin pitch and time are fixed at1.** The standalone bridge supports other static pitches; dynamic pitch/time automation is not implemented here. IDs and the versioned16-byte little-endian target-state record are distinct from product IDs/state.

CLAP latency and VST3 `getLatencySamples()` report the fixed output delay. Actual loaded-module tests exercise offset automation, state restore, in-place processing and sample equality to the C bridge. CLAP additionally tests its finite tail with an impulse. No manual DAW project test,64-bit audio path,AU/AAX,macOS or Windows validation is claimed.

Pinned dependencies: CLAP `195b42a004144fab0b3cf95e9c067187d15365b7` and VST3 SDK `9fad9770f2ae8542ab1a548a68c1ad1ac690abe0` with recorded submodules. Build instructions and limitations are in `research/host_adapters/README.md`.

## Exact audio and quality validation

The supplied archives audit as240/240 processed/reference pairs,20 mono44.1k references,zero missing. Training references are not pooled. The exact -12,-7,-3,+3,+7,+12 grid across five profiles and three formant modes gives **20x6x5x3=1,800 paired conditions /3,600 WAV renders**.

Baseline: exact c92 source, immediate scalar, block256. Candidate: scheduled SIMD, block32. Both centered/scaled. Every output has the expected frame count, rate and channels. **1,800/1,800 entire WAV files are byte-identical**, maximum sample difference0. The CSV preserves hashes and unchanged objective diagnostics; raw audio is not normalized or limited.

The existing low-tone/high-band gate was rerouted through the actual scheduled CLI with unchanged thresholds: **270 cases,0 failures**. Worst low-tone error2.153085cents, minimum target/spur22.816859dB, worst high-band p95 ripple0.145946dB below0.25dB. These are equivalence and limited quality checks, not new perceptual rankings. No native or derived-Elastique result is invented by this pass.

## Callback measurements and negative evidence

Linux x86_64 shared VM, GCC14.2 Release, CPU0 affinity. Our compiler/corpus loads finished before timing. Each cell has200 warmup plus1,200 measured callbacks. Three repeats rotate/interleave variant order. Thread-CPU and wall timings remain separate. Complete-grid validation rejects missing/duplicate cells rather than selecting favorable runs.

Headline table values are the **worst pitch of the per-cell three-repeat median CPU p99/deadline**.1 is the deadline; these medians do not erase raw outliers.

### Core push/pull

Matrix48/96k,mono/stereo,32/64frames,six pitches,Transient/Fuzzy/Multi-resolution,four variants:576cells/repeat.

| Stereo configuration | Immediate scalar | Scheduled+SIMD |
|---|---:|---:|
| Fuzzy48k/32 | 0.349 | 0.132 |
| Multi-resolution48k/32 | 0.485 | 0.134 |
| Fuzzy96k/32 | 1.360 | 0.419 |
| Multi-resolution96k/32 | 2.264 | 0.337 |
| Fuzzy96k/64 | 0.765 | 0.285 |
| Multi-resolution96k/64 | 1.243 | 0.358 |

Median paired p99 reductions across48cells/profile: Transient71.52%,Fuzzy57.55%,Multi-resolution72.05%. Median average-CPU changes:+2.37%,-0.67%,+5.54%. Work is distributed, not free.

**4/432 raw candidate cell/repeats still had p99 above deadline**; largest raw p99 ratio2.645 and largest individual CPU sample50.389x deadline. These occur in the first repeat's early48k cells. Their cause is unproven, not dismissed as established environmental noise. An interrupted548-row earlier run is retained separately and excluded by complete-grid validation.

### Fixed-delay bridge with dense formant automation

Separate matrix:48/96k,mono/stereo,32/64frames,six static pitches,three profiles,two variants:288cells/repeat. **Four sample-offset formant events occur every callback**, plus a mailbox request every64callbacks. Initial formant ratio0.75. This measures actual constant-output bridge processing, not just FFT kernels.

| Stereo configuration | Immediate scalar bridge | Scheduled+SIMD bridge |
|---|---:|---:|
| Transient96k/32 | 1.119 | 0.238 |
| Fuzzy96k/32 | 1.452 | 0.462 |
| Multi-resolution96k/32 | 2.315 | 0.373 |
| Transient96k/64 | 0.589 | 0.168 |
| Fuzzy96k/64 | 0.733 | 0.291 |
| Multi-resolution96k/64 | 1.231 | 0.350 |

Across518,400 measured callbacks per variant, CPU-deadline misses fall **6,175→196**; wall-deadline misses6,197→200. Candidate still has2/432 raw cell/repeats with p99>1; maximum raw p99=1.447308 and maximum individual CPU ratio=9.256206. Scheduler overruns and FIFO underruns are0, but those are not CPU deadline counters. **Hard-realtime safety is not established.** All complete raw repeats, miss counts and maxima are retained.

## Software tests and failures retained

| Validation | Result |
|---|---|
| GCC C++20/23 Release |19/19 each |
| Clang C++20/23 Release |19/19 each |
| Core ASan+UBSan with leak detection |19/19 |
| Forced scalar build |19/19 |
| Python research plus legacy |178+6=184,no skips |
| Scheduling/SIMD/automation exact comparisons |240 |
| Fixed-delay waveform comparisons |90 |
| Loaded CLAP/VST3 comparisons |18 each |
| Normal adapter+core CTest |21/21 |
| ASan+UBSan adapter+core,leak detection |21/21 |
| New bridge TSan,two audio owners plus UI/state |Passed |
| Normal Steinberg validator |47 passed,0 failed |

Coverage includes pure C layouts/consumers, zero/short input, in-flight reset, partition invariance, rejected ratio changes, aligned allocation interception and processing/flush/reset no-allocation checks. Loaded plugin processing allocates zero in the tested calls.

The first ASan loaded-CLAP test found a **test-interposition mismatch**: runtime nothrow new paired with custom malloc/free delete. Matching nothrow overloads fixed the test harness. Full21-test sanitized validation then passed with leak and allocation checks on; no DSP/plugin workaround or sanitizer suppression was added.

Separately, the sanitized SDK validator's own registration self-tests leaked5,082bytes/79allocations before testing our module. Its failed log is retained. Build-time SDK tools were completed with LSan disabled; **all actual loaded-module/core CTests ran with detect_leaks=1 and no suppression**. Normal validator47/47 success is a separate result, not a claim that the SDK tool's sanitized self-tests are clean.

### Isolated overlap-guard compatibility

At0321326e, existing `research-experiments` run34750434675 failed its50% variant: the old experiment patch changed immediate-path phase/hops but omitted the new cooperative path. New execution and fixed-delay exact-output tests correctly failed. This was deterministic, not timing noise. The75% variant passed because its tested target hops were unchanged.

Commit e5a166bb extends **only the isolated patch** to use the actual analysis stride and the same capped next hop in both paths. Ordinary DSP/plugin code and measured audio remain unchanged; overlap guard is not enabled or promoted. Clean local50% and75% configurations each passed20/20 CTests without skips or relaxed thresholds.

## Hosted CI

At `e5a166bb7909a0252781e5fb5775413728804f83`:

- Dedicated execution/host run **34750788489:4/4 jobs passed**, including Python3.11/3.13, scheduled270-case quality, descriptive callbacks, actual pinned CLAP/VST3 modules and new TSan coverage.
- Existing-product run **34750788490:9/9 jobs passed**, separate from the new research modules.
- Isolated-experiment run **34750788518:8/8 jobs passed**, including the previously failing50% variant.

The preceding same-runtime dedicated run34750434650 also passed. Its source artifact10315453826 was downloaded and independently verified as described above. Initial failures are preserved, not erased. Local raw timing samples are not replaced with hosted-CI samples.

## Reproduction and remaining work

```sh
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
cmake -S research/cpp_pv_rt -B build/execution -G Ninja \
  -DCMAKE_BUILD_TYPE=Release -DCMAKE_CXX_STANDARD=20
cmake --build build/execution -j2
ctest --test-dir build/execution --output-on-failure
export BOILED_EGG_PV_CLI="$PWD/build/execution/boiled_egg_pv_rt_cli"
export BOILED_EGG_MULTIRES_CLI="$PWD/build/execution/boiled_egg_multires_rt_cli"
python -W error::ResourceWarning -m unittest discover -v -s research -p 'test_*.py'
python -W error::ResourceWarning -m unittest -v eval/test_tsm_dataset.py
python research/check_execution_quality.py --build "$PWD/build/execution" --output scheduled-tones.json
"$BOILED_EGG_PV_CLI" in.wav out.wav --time 1 --profile transient --mode fuzzy \
  --pitch-semitones -7 --formant harmonic --formant-semitones 3 \
  --timing centered --rate-policy scaled --execution scheduled --simd on --block 32
for r in 1 2 3; do
  build/execution/boiled_egg_execution_bench "$r" > "core-$r.csv"
  build/execution/boiled_egg_host_bench "$r" > "host-$r.csv"
done
python research/summarize_execution_bench.py --kind host \
  --csv host-1.csv host-2.csv host-3.csv --output host-summary.json
```

For full replay, independently build c92 and pass its directory as `--baseline` to `check_execution_corpus.py`, with `--candidate`, `--ref-dir`, `--catalog`, `--output`. Keep original audio/MOS local. Delivered validation contains source, patches, measurements, hashes and logs, not the source corpus or external SDK sources.

Remaining work: investigate timing tails on controlled hardware, reduce fixed latency while retaining exact timing, validate dynamic pitch/time maps, exercise real DAW sessions and collect blind listening. No native-Elastique parity, full384k/8-channel capacity, extreme+24st safety, sample-instant spectral response or cross-platform plugin qualification is asserted.

Official host-contract references:
[1] https://steinbergmedia.github.io/vst3_doc/vstinterfaces/classSteinberg_1_1Vst_1_1IAudioProcessor.html
[2] https://github.com/free-audio/clap/tree/1.2.10/include/clap/ext
