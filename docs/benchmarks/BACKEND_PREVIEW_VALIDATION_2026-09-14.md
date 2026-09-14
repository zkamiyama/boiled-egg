# Backend foundation and spectral preview — 2026-09-14 JST

## Delivery and scope

Stage 1 is merged as PR #7: main `bfbb6fd0b8196a99a29f6fd4989a467deeeaf1af`.
It adds explicit backend selection/capability queries without replacing WSOLA,
changing its arithmetic or altering legacy ABI structures/profile/state meaning.
Stage 2 is draft PR #8 (`feature/spectral-backend-preview`), **not merged**.
The validated preview code is `456d091dc68d4ea17449ebf7de0b01e550edcf0f`, tree
`c7fa55c664076f585c25f61094207ff3225a9bb0`. This report-only commit does not
change measured code. Stage 3 (dynamic pitch and product adapter integration)
is not implemented by this checkpoint.

The resumed session found foundation `2bc75261` and the initial spectral preview
`67e997a4` already on their branches. It retained them and added explicit
ON/OFF CI, boundary coverage, installation/CLI tests, reproducible corpus replay
and documentation; it did not invent those inherited implementations anew.

## Public interface

`boiled_egg/backend.h` separates backend, quality, formant policy and I/O contract.
A known but uncompiled backend reports UNAVAILABLE; unsupported requests never
silently select WSOLA. Larger versioned records preserve unknown caller tails;
short size prefixes, reserved fields and invalid controls are rejected.

The preview uses the ordinary opaque product handle and C++ RAII interface,
not a separately exposed research ABI. It implements ordinary phase-locked PV,
not Fuzzy/Multi-resolution/phase-guard experiments. Formant Off/Harmonic/Monophonic
remain independent of General/Transient quality. Formant ratio/semitone setters,
sample-offset events and identity-bound extension state are available.

The preview is disabled by default. Both the CMake option
`BOILED_EGG_ENABLE_EXPERIMENTAL_SPECTRAL=ON` and the instance flag
`BOILEDEGG_BACKEND_ALLOW_EXPERIMENTAL` are required. Supported rates are exactly
44100/48000/88200/96000, mono/stereo, caller blocks 1–1024. Time and pitch are
frozen at construction, each in [0.5,2], with time*pitch<=2. Streaming supports
exact final duration; fixed-I/O requires time=1 and supplies a constant declared
delay. Only formant targets are dynamic; spectral response is frame-latched and
smoothed over a 10-ms time constant, not instantaneous samplewise warping.

Existing plugins still choose WSOLA. Legacy FORMANT_PRESERVE remains unsupported,
not remapped. The new in-memory extension-state record is not a new CLAP/VST3
serialized format. Neither backend quality nor hard-realtime capability is
inferred from build-level availability; the preview clears the hard-RT bit.

## Local and hosted validation

| Validation | Result |
|---|---|
| Exact foundation source, GCC20 | 12/12 CTests |
| Preview ON, GCC/Clang x C++20/23 | 16/16 in each configuration |
| Preview ON, Clang ASan+UBSan, leak detection | 16/16 |
| Shared preview OFF | 12/12 |
| Static preview ON | 16/16 |
| Installed C11 and header-only C++ consumers | 2/2 in shared ON, shared OFF and static ON |
| Added CLI checks | 9 ON, 8 OFF |
| Public/private API and fixed-delay tests | 216 paired conditions |
| Added empty/short/odd/boundary cases | 576 conditions, each comparing block31/257 |
| Backpressure | 200001 input frames, no accepted-input loss |
| Same-kernel real-corpus API replay | 960/960 entire WAV files identical |

Additional checks cover zero/one-sample input, repeatable reset, exact duration,
finite output, linked identical channels, no-allocation processing, parallel
instances/UI-state mailboxes, atomic rejection of malformed event batches,
256-event capacity, rejected 257-event batches and parameter-only calls.

Hosted foundation PR product CI 34808479228 passed all9 jobs: GCC/Clang20/23,
ASan+UBSan, TSan, CLAP, VST3 validator, exports and installed/static consumers.
Foundation audit34808479252 passed; its28 declared WSOLA capacity cells all pass
the pre-existing 80% budget policy, with3 repeats/1200 steady calls. Worst
state-best ratio0.2816844 and84/84 actual runs below their periods on that runner.
These are not preview performance results or portable guarantees.

After merge, main product run34812101238 also passed9/9 jobs. Preview PR runs
34812138329 (existing product CI),34812138361 (existing measurement audit), and
34812138464 (new explicit preview CI) all passed. The last has6 jobs: GCC/Clang
ON/OFF, ASan+UBSan and TSan. It also tests static builds, installed consumers and
CLI controls. Existing product host CI does not mean the new preview controls
have been wired into those plugins.

No new native-zplane benchmark, listening test, dynamic-pitch certification,
48/96-kHz preview capacity study or cross-platform host qualification is claimed.

## Real-audio routing replay

Used the supplied20 test references, all mono44.1k, not substitute training audio.
Each source has General/Transient x Off/Harmonic/Monophonic x six pitch shifts
(-12,-7,-3,+3,+7,+12,time1) plus two time ratios(.5,2,pitch1):
20 x2 x3 x8 =960 pairs /1920 generated WAVs. The public SDK caller uses block32;
the directly called private reference uses block256. Output was not normalized,
limited, fitted-aligned or re-scored as MOS. All samples, durations, rates and
channel counts were checked; maximum sample difference is0.

The reference is the SAME private DSP kernel built separately, not an independent
quality algorithm. The result establishes API-routing/partition equivalence,
not perceptual superiority or correctness of all signal-processing choices.
Output audio is temporary and not included in the deliverable.

Comparisons SHA256: `43748399742520990ec8a215b8cfee1bce285069dfcecb84b617e325509bc735`.
Public CLI SHA256: `f270f8a60f58fbe24aefb3a3d6b945ef4ff550434cbf55988352064ee7480f4f`.
Direct private CLI SHA256: `c1681ab0683904676b09182c6015ace3087874cbb7c016cd02498ae51dc85780`.
Loaded public library SHA256: `b513cc324ac4730d74e661aeec90c009bee96b28d8f014cd20eb84bfa05b6870`.
The replay runner's original JSON records executable hashes but not dynamic-library
dependencies; the shared-library binding is therefore retained in the separate
measured_provenance.json. Runtime sources/library were unchanged during replay.

## Source replay and evidence

Initial preview artifact10334716271 from34810109475:134 source hashes verified.
Foundation artifact10333932656 from34808479252:110 hashes verified, tree
7626b64092205f70ecce28dc61957c2dfdf851f8 equals foundation head2bc75261.
Final preview artifact10334704362 from34812138464:144 source hashes verified,
all matching the measured local source. Its synthetic PR-merge commit is
ef300a9497e39d091442a684733ba3c46b1e1a99; the tree matches456d091d exactly.
Archive CRC and outer checksums passed. Local toolchains were GCC14.2 and Clang17.
The14-file private DSP manifest records unchanged imported source bytes.

The evidence bundle retains exact source, install/examples, logs, CSV/JSON and
checksums. User source audio/MOS and external SDK sources are not redistributed.

## Reproduction

```sh
# Use the preview branch, not main, for this explicit opt-in build.
cmake -S . -B build-preview -G Ninja -DCMAKE_BUILD_TYPE=Release \
  -DBOILED_EGG_ENABLE_EXPERIMENTAL_SPECTRAL=ON
cmake --build build-preview -j2
ctest --test-dir build-preview --output-on-failure
scripts/test_backend_install.sh build-preview ON
build-preview/boiled_egg_backend_cli --list-backends
build-preview/boiled_egg_backend_cli input.wav output.wav \
  --backend pv --allow-experimental --quality transient --time 1 \
  --pitch-semitones -7 --formant harmonic --formant-semitones 3 --block 32
python quality/backend_preview/replay_corpus.py \
  --refs /absolute/ref_test --public "$PWD/build-preview/boiled_egg_backend_cli" \
  --oracle "$PWD/build-preview/boiled_egg_pv_oracle_cli" --output results/replay
```

Next unresolved integration work is dynamic pitch with a sound continuous timeline
and fixed host delay, then existing product adapter events/state and adoption
validation. The current static-pitch preview rejects unsupported operations rather
than quietly changing latency, freezing a UI knob or selecting a different engine.
