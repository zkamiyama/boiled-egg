# DAW / host integration contract

This document defines the host-facing contract before higher-quality DSP backends are promoted into `main`.

## Two processing modes

A `boiledegg_handle` enters one processing mode after `boiledegg_reset()`:

1. **Fixed-I/O realtime mode** — `boiledegg_process_realtime()`.
   - Intended for DAW insert/plugin pitch shifting.
   - Writes exactly the requested number of samples every call.
   - Current backend requires `time_ratio == 1.0`.
   - Startup delay is deterministic zero padding.
   - Report the value from `boiledegg_get_runtime_info().realtime_latency_frames` to the host for PDC.
2. **Variable-rate streaming mode** — `boiledegg_push()` / `boiledegg_pull()` / `boiledegg_flush()`.
   - Intended for clip/source time stretching, offline renderers, preview engines and applications that can decouple input/output clocks.
   - Supports time ratios other than 1.0.

Do not mix the two modes on one handle without `boiledegg_reset()`.

## Lifecycle

Recommended plugin lifecycle:

```text
host activate(sample_rate, max_block)
    -> boiledegg_create(config)          [may allocate; not audio thread]
    -> boiledegg_get_runtime_info()
    -> report latency/tail to host

host process()
    -> boiledegg_process_realtime()      [no allocation, no lock, no I/O]

host reset/seek/discontinuity
    -> stop concurrent processing
    -> boiledegg_reset()

host deactivate
    -> stop concurrent calls
    -> boiledegg_destroy()               [not audio thread]
```

Recreate the handle when sample rate, channel count, maximum block size or backend configuration changes.

## Threading

- Separate handles are independent. A DAW may process separate tracks/plugin instances in parallel.
- One handle has one audio/streaming owner. Do not run two `process_realtime()` calls concurrently on the same handle.
- Pitch/time setters and getters may run on one control/UI thread concurrently with the audio owner.
- `boiledegg_get_runtime_info()` reads immutable data and is safe alongside processing.
- `reset` and `destroy` are lifecycle operations and require external synchronization.
- The audio path contains no mutex. ThreadSanitizer tests cover parallel instances and concurrent UI/audio parameter updates.

## Automation

`boiledegg_process_realtime()` accepts sorted `boiledegg_parameter_event` entries with a sample offset inside the current host block. This lets VST3/CLAP adapters preserve the host's event timestamps and ordering without allocation.

The current WSOLA backend **does not claim sample-accurate audible automation**. `BOILEDEGG_CAP_SAMPLE_OFFSET_EVENTS` is set, while `BOILEDEGG_CAP_SAMPLE_ACCURATE_AUTOMATION` is not. `parameter_quantum_frames` reports the current backend's conservative DSP control quantum.

A future backend may set the sample-accurate capability without changing the C event ABI.

### VST3 mapping

- Convert each `IParamValueQueue` point to a `boiledegg_parameter_event` using the point's sample offset.
- Keep points sorted by offset; for equal offsets use a deterministic parameter order in the adapter.
- Report `realtime_latency_frames` via the VST3 latency mechanism.
- Recreate/re-activate rather than mutating configuration from the audio callback.

VST3 hosts provide enough automation points for sample-accurate reconstruction; the plugin decides the internal processing granularity. This is why boiled egg exposes the capability/quantum explicitly instead of claiming more precision than the active backend provides.

### CLAP mapping

- Convert input parameter events from `clap_process.in_events` to `boiledegg_parameter_event` using the event time.
- Report latency using `CLAP_EXT_LATENCY` and tail using `CLAP_EXT_TAIL`.
- Parameter UI/control synchronization belongs in the adapter; the core setter mailbox is safe for one concurrent control writer.
- Use CLAP thread-check facilities in adapter debug builds when available.

## Latency and tail

`realtime_latency_frames` is constant for the lifetime of a handle. The fixed-I/O wrapper maintains enough internal backlog to absorb the WSOLA synthesis quantum, so the value is independent of the host block size.

For the current finite-memory pitch effect, `realtime_tail_frames == realtime_latency_frames`. After the source ends, process silence for that many frames if the host requests the tail. Tests verify that identity processing reproduces the input exactly after the reported delay, including the end of the source.

## In-place audio

Fixed realtime mode supports `input[ch] == output[ch]`. The core copies the current input segment into its preallocated FIFO before writing output. Partial/overlapping pointer aliases other than exact per-channel in-place buffers are not part of the contract.

## Error handling on the audio thread

`boiledegg_process_realtime()` always initializes the full output block for valid pointers. If the backend unexpectedly cannot sustain fixed output, it zero-fills the missing portion and returns `BOILEDEGG_REALTIME_UNDERRUN`. Hosts should keep running and record/diagnose the error rather than throw or block.

`BOILEDEGG_INVALID_STATE` indicates that fixed-I/O and variable-rate modes were mixed without reset. `BOILEDEGG_UNSUPPORTED_MODE` currently indicates an attempt to use non-1.0 time ratio in the fixed-I/O DAW mode.

## State/presets

The core intentionally does not define a binary preset format yet. Adapters should persist normalized user parameters and recreate DSP configuration through the public C API. This avoids freezing a backend-specific state serialization format before the phase-vocoder/hybrid architecture is settled.
