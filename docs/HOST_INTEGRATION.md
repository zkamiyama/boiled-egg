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
    -> serialize against the current process call
    -> boiledegg_reset()                 [realtime-safe, parameters preserved]

host deactivate
    -> stop concurrent calls
    -> boiledegg_destroy()               [not audio thread]
```

Recreate the handle when sample rate, channel count, maximum block size or backend configuration changes.

## Threading

- Separate handles are independent. A DAW may process separate tracks/plugin instances in parallel.
- One handle has one symbolic audio/streaming owner. Do not run two `process_realtime()` calls concurrently on the same handle.
- The symbolic audio owner **may migrate between operating-system threads between non-overlapping calls**. boiled egg has no thread affinity requirement; this matches hosts that redistribute plugin instances across a worker pool.
- Pitch/time setters, getters and parameter-only mailbox flushes may run on one control/UI thread concurrently with the audio owner.
- `boiledegg_get_runtime_info()` reads immutable data and is safe alongside processing.
- `boiledegg_reset()` is allocation-free/lock-free and may be called by the sole audio owner between process calls. It preserves requested user parameter values and clears DSP history/latency state.
- `destroy` is the lifecycle operation that always requires external synchronization.
- The audio path contains no mutex. ThreadSanitizer tests cover parallel instances, worker migration, audio-thread reset, and concurrent UI/audio parameter updates.

## Automation

`boiledegg_process_realtime()` accepts sorted `boiledegg_parameter_event` entries with a sample offset inside the current host block. This lets VST3/CLAP adapters preserve the host's event timestamps and ordering without allocation.

The current WSOLA backend **does not claim sample-accurate audible automation**. `BOILEDEGG_CAP_SAMPLE_OFFSET_EVENTS` is set, while `BOILEDEGG_CAP_SAMPLE_ACCURATE_AUTOMATION` is not. `parameter_quantum_frames` reports the current backend's conservative DSP control quantum.

A future backend may set the sample-accurate capability without changing the C event ABI.

### Parameter-only flushes

Some hosts deliver parameter changes when there is no audio block. boiled egg therefore supports both forms below:

```c
boiledegg_apply_parameter_events(handle, events, count);

// Equivalent host-facing form:
boiledegg_process_realtime(handle, NULL, NULL, 0, events, count);
```

For a parameter-only flush every event must have `sample_offset == 0`. The complete batch is validated before any mailbox value is published, so a malformed later event cannot partially apply an earlier one. A zero-frame flush does not select the fixed-I/O or streaming processing mode.

### VST3 mapping

- Convert each `IParamValueQueue` point to a `boiledegg_parameter_event` using the point's sample offset.
- Keep points sorted by offset; for equal offsets use a deterministic parameter order in the adapter.
- A zero-sample VST3 process call that only carries parameter changes maps to zero-frame `boiledegg_process_realtime()` / `boiledegg_apply_parameter_events()`.
- Report `realtime_latency_frames` through the VST3 latency mechanism and request a host restart when the plugin configuration changes that value.
- Recreate/re-activate for sample-rate/channel/max-block/backend changes rather than mutating configuration from the audio callback.
- VST3 parameter queues describe linear changes between points. Until the active backend advertises `BOILEDEGG_CAP_SAMPLE_ACCURATE_AUTOMATION`, an adapter must not advertise the core as sample-accurate; it may conservatively resample a host ramp at `parameter_quantum_frames` if needed.

### CLAP mapping

- Convert input parameter events from `clap_process.in_events` to `boiledegg_parameter_event` using the event time.
- Map the CLAP params `flush` callback to `boiledegg_apply_parameter_events()` with zero-offset events.
- Map `clap_plugin.reset` directly to `boiledegg_reset()`. CLAP calls reset on the audio thread while active, which is why the core reset path is explicitly realtime-safe.
- CLAP's symbolic audio thread may be backed by a different OS thread over time; boiled egg permits this as long as calls on one handle never overlap.
- Report latency using `CLAP_EXT_LATENCY` and tail using `CLAP_EXT_TAIL`.
- Parameter UI/control synchronization belongs in the adapter; the core setter/mailbox path is safe for one concurrent control writer.
- Use CLAP thread-check facilities in adapter debug builds when available.

## Latency and tail

`realtime_latency_frames` is constant for the lifetime of a handle. The fixed-I/O wrapper maintains enough internal backlog to absorb the WSOLA synthesis quantum, so the value is independent of the host block size.

For the current finite-memory pitch effect, `realtime_tail_frames == realtime_latency_frames`. After the source ends, process silence for at least that many frames if the host requests the tail. Tests cover identity alignment and ±12-semitone impulse decay through the reported tail, with an additional guard region required to remain effectively silent.

A transport reset starts the deterministic startup latency again. The host should therefore continue using the same PDC value; only the internal delay line/history is cleared.

## In-place audio

Fixed realtime mode supports `input[ch] == output[ch]`. The core copies the current input segment into its preallocated FIFO before writing output. Partial/overlapping pointer aliases other than exact per-channel in-place buffers are not part of the contract.

## Error handling on the audio thread

`boiledegg_process_realtime()` always initializes the full output block for valid pointers. If the backend unexpectedly cannot sustain fixed output, it zero-fills the missing portion and returns `BOILEDEGG_REALTIME_UNDERRUN`. Hosts should keep running and record/diagnose the error rather than throw or block.

`BOILEDEGG_INVALID_STATE` indicates that fixed-I/O and variable-rate modes were mixed without reset. `BOILEDEGG_UNSUPPORTED_MODE` currently indicates an attempt to use non-1.0 time ratio in the fixed-I/O DAW mode.

## State / projects / presets

The core does not freeze a backend-specific binary preset format. Instead it exposes `boiledegg_parameter_state`, currently containing normalized time and pitch ratios. Adapters can serialize those primitive values into their own stable project-state schema and later restore them with `boiledegg_set_parameter_state()`.

This deliberately separates **user state** from **DSP history**:

- user parameters survive `boiledegg_reset()`;
- DSP history, FIFO state, transient/phase history and latency progress do not;
- a restored project should create/activate the correct DSP configuration, restore `boiledegg_parameter_state`, then start processing from a clean reset state.

For CLAP, state save/load belongs in the adapter's main-thread state extension. For VST3, the adapter can place the same primitive values in the processor/controller state stream. The adapter, not the core, owns file-format versioning and parameter IDs visible to the host.
