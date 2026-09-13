# Formant Lab — isolated research host integration

This is **not the product plugin or a promoted backend**. CLAP and VST3 use new
identifiers and a separate state format. Existing `adapters/`, product ABI and
`main` are unchanged. Linux x86_64 is the tested platform; float32 stereo only.

The plugin exposes one automatable **Formant** parameter, -12 to +12 semitones.
Its DSP is the Fuzzy/Harmonic research backend with centered/scaled analysis,
cooperative scheduling and optional SSE2 acceleration. **Pitch and time remain
fixed at 1 in this plugin.** The standalone C bridge can be constructed with a
static pitch in [0.5,2] and a manually selected profile; it cannot change pitch
or time during processing. This is not the full product's automation surface.

## Build and test

Use the pinned public SDK revisions from `research-execution-host.yml`:
CLAP `195b42a004144fab0b3cf95e9c067187d15365b7` (1.2.10), VST3 SDK
`9fad9770f2ae8542ab1a548a68c1ad1ac690abe0` with its recorded submodules.
Build the VST3 integration in **Release**; the loaded-module test uses its
Release package directory. Keep SDK sources outside the repository.

```sh
cmake -S research/host_adapters -B build/lab -G Ninja \
  -DCMAKE_BUILD_TYPE=Release \
  -DCLAP_ROOT=/absolute/path/to/clap \
  -DVST3_ROOT=/absolute/path/to/vst3sdk
cmake --build build/lab -j 2
ctest --test-dir build/lab --output-on-failure
```

Outputs are `build/lab/boiled_egg_formant_clap.clap` and
`build/lab/VST3/Release/boiled egg Formant Lab.vst3`. The SDK validator runs at
build time. Loaded-module tests exercise actual CLAP/VST3 ABI calls and compare
samples against the independent C bridge. They do not replace manual DAW tests.

## Fixed delay and automation contract

For Fuzzy, Transient and Fuzzy-noise the C bridge's delay is 2,688 samples at
48 kHz (56 ms), and 5,248 samples at 96 kHz (54.667 ms). General and
Multi-resolution have their own fixed construction-time delays. Do not confuse
this real output delay with the older research `latency_frames()` lookahead
hint. Query `boiledegg_research_host_latency_frames()` for the bridge.

The host is notified through CLAP latency and VST3 `getLatencySamples()`.
Formant changes do not change the delay. Initial output is zero for the declared
delay, then exactly one output frame is returned for each input frame. This is
not a low-latency live-monitoring qualification. Feed silence to drain the host
bridge; do not call the offline engine's synchronous `flush()` in a host callback.

Events are validated before DSP mutation: at most 256 relevant events per block,
sorted offsets in `[0,frames)`, finite valid ratios, last value at duplicate
offsets wins. The target is delivered before that input sample. **The audible
spectral change is frame-latched and smoothed with a 10-ms time constant**, not an
instantaneous sample-resolution envelope warp. The process API and CLI preserve
manual profile selection and independent Harmonic/Monophonic formant policies.

## Threads, state and failures

Each instance has a single audio owner. Different instances can run in parallel.
The UI/state path uses lock-free `uint32_t` latest-value mailboxes; processing
performs one bounded exchange at block start, then timestamped automation takes
precedence. Target snapshots are atomic UI/state values, not historical audio
samples. Reset/deactivate/destroy require lifecycle exclusion; no background DSP
worker thread exists.

Plugin state is a versioned 16-byte little-endian record containing only the
formant target, with separate magic from product state. Invalid state/events are
rejected rather than silently truncated. No host adapter calls the allocating
constructor from the processing callback. Processing loops are preallocated;
input silence and exact planar in-place buffers are supported. A bridge internal
underrun faults the handle until reset and never silently changes its delay.

## Performance and remaining work

Scheduling spreads the same calculation across input ticks and preserves
numerical order. SSE2 accelerates FFT butterflies without reassociation; other
platforms have a scalar fallback. There is no AVX/NEON implementation in this
change. Dynamic pitch/time maps, lower fixed latency, end-to-end UI host-thread
stress, a 64-bit audio path and cross-platform host testing remain separate work.

The measured p99 improvement does not erase rare deadline misses. Preserve raw
maximum timing and miss counts as well as medians; see the dated execution report.
No new listening results, native Elastique comparison or perceptual promotion
claim is made.
