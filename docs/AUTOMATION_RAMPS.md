# Explicit pitch and streaming time ramps (experimental spectral API)

This is the next additive stage after `DYNAMIC_PITCH_EDITOR.md`, tracked in
Issue #2 and draft PR #10. Existing WSOLA, existing event records, plugin state
and legacy 10-ms pitch behavior are not replaced. Build with
`BOILED_EGG_ENABLE_EXPERIMENTAL_SPECTRAL=ON` and opt in per instance.

## Public entry points

Include `<boiled_egg/automation.h>` (installed with the SDK):

- `boiledegg_process_realtime_ramps`: fixed input/output count, time ratio 1.
- `boiledegg_push_ramps`: variable-duration streaming, accepted-prefix result.
- `boiledegg_get_automation_info`: audio-owner snapshot of effective controls,
  targets, remaining durations and cumulative positions; it advances no clock.

The header-only C++ wrapper exposes corresponding methods, including
`process_realtime_ramps_nothrow`, `push_ramps` and `automation_info`.
These functions have one audio owner per handle. They are not concurrent UI
mailboxes. Different instances remain independently parallelizable.

The record is 32 bytes, fixed stride, with `struct_size == sizeof(record)` and
zero reserved fields. At most 256 sorted records are accepted per call. The
complete batch is checked before processing. Same-offset records follow array
order; coupled pitch/time bounds are checked after each equal-offset group.

## Curves and input-sample timing

`duration_frames == 0` is a step. With duration N > 0, the sample at the event
position is sample 1 and sample N reaches the target. Therefore a 4,800-sample
ramp takes 100 ms of accepted input at 48 kHz, irrespective of push block size.

- `BOILEDEGG_RAMP_LINEAR_RATIO`: uniform increments in the ratio.
- `BOILEDEGG_RAMP_LOG_RATIO`: uniform increments in log ratio; for pitch this
  is linear in semitones.

The curve is independent of whether the target is specified as PITCH_RATIO or
PITCH_SEMITONES. A later event restarts from the current effective value, even
when it repeats the previous target. No reset of phase or resampling position
occurs. A zero-frame call accepts offset-zero events without choosing an I/O mode.
Precise input timestamps do not imply instantaneous audible STFT response.

Example event, on a continuous-pitch spectral handle already configured for
fixed-I/O realtime use:

```c
boiledegg_ramp_event event = {
    sizeof(boiledegg_ramp_event), 0,
    BOILEDEGG_PARAMETER_PITCH_SEMITONES, 4800,
    BOILEDEGG_RAMP_LOG_RATIO, 7.0f, {0, 0}
};
boiledegg_result result = boiledegg_process_realtime_ramps(
    handle, input_channels, output_channels, block_frames, &event, 1);
/* Check result. Submit this event ONCE; subsequent blocks pass NULL, 0
   while the accepted trajectory continues internally. */
```

The executable installed-C example is `tests/backend_install/consumer_ramps.c`.
It also tests a 64-input-sample time ramp from 1 to 2: the prescribed post-tick
sum is 96.5 output samples, so EOS produces exactly 97 samples.

## Enabling variable time in streaming

For explicit pitch, use `BOILEDEGG_BACKEND_ALLOW_EXPERIMENTAL |
BOILEDEGG_BACKEND_CONTINUOUS_PITCH`. Variable time additionally requires
`BOILEDEGG_BACKEND_CONTINUOUS_TIME` and `BOILEDEGG_IO_STREAMING`.

Pitch and time ratios each have the supported range [0.5, 2]. The safety check
requires

`max(current_pitch, target_pitch) * max(current_time, target_time) <= 2`

after each equal-offset group, including any already active trajectory. This is
a conservative rectangular bound, not an exact maximization of intersecting
curves: some safe opposing ramps can be rejected. It prevents sparse synthesis
coverage over the supported trajectories. It is not an output peak limiter.

Two preallocated cumulative clocks use the same accepted input history:

- `W = sum(effective_time_ratio)`: output sample position.
- `V = sum(effective_time_ratio * effective_pitch_ratio)`: intermediate PV position.

The synthesis and resampling stages use those clocks consistently. Explicit
trajectories use compensated accumulation so rounding a duration near a half
sample does not depend on avoidable summation drift. Legacy trajectories retain
the earlier arithmetic; the old API is tested separately for exact output.

### Backpressure and end of stream

Only accepted input advances controls. If a push accepts k of n input frames,
events at offsets >= k were not consumed. Drain output, then retry only the
remaining input, rebasing those event offsets by k. Do not replay accepted
events. Pull calls advance neither control ramp.

Flush freezes controls at the effective values reached by real input; padding
must not complete the unconsumed remainder of a long ramp. Final output length
is `floor(W + 0.5)`. Reset discards trajectory history and retains requested
targets. The info snapshot is audio-owner-only and must not race processing.

On CONTINUOUS_TIME instances, uncoupled time/pitch UI setters and legacy state
writes are explicitly unsupported; use the coupled single-owner event API.
Existing formant mailboxes remain supported. Formant events still use the prior
API; they are not new duration-controlled ramp records.

## Fixed latency and host integration boundary

Realtime processing still requires time ratio 1. Variable time is not silently
inserted into a fixed-input/fixed-output DAW callback. Continuous pitch retains
the prior range-wide fixed latency: at 48/96 kHz, Transient is 2112/4160 samples
and General is 3648/7232. The latency does not change with ramp duration/curve.
Streaming output length varies with W and has a different I/O contract.

Existing CLAP/VST3 pitch/fine/formant events and the native editor continue to
use the compatible event path. This change does NOT add a GUI ramp-duration
control or reinterpret existing host points as future arbitrary-duration ramps.
User-specified durations are available through the new C/C++ API. Existing
plugins and state keep their previous interpretation.

The new entry points currently require the opted-in spectral backend; WSOLA
returns UNSUPPORTED_MODE rather than pretending to implement the trajectories.
The compiled backend capability record remains the authority for supported
rates/channels and flags (spectral: 44.1/48/88.2/96 kHz, mono/stereo).

## Validation and remaining adoption

`tests/test_automation_ramps.cpp`, `tests/test_time_ramps.cpp` and the rounding,
thread and no-allocation tests exercise the real public API, independent clock
formulas, interrupted/equal-offset commands, accepted-prefix resubmission,
reset/flush and fixed-delay output. `quality/automation_ramps/study.py` checks
analytic settled tones and compares block32 with block257 on identical inputs.
Installed shared/static C consumers test exported interfaces rather than private
implementation headers. See the dated benchmark record for actual run results.

No new audible-quality, native-zplane, sample-instant response, OS worst-case
execution time or automatic main-promotion claim is made. Issue #2 remains open
for product adoption and any broader host/backend contracts; draft PR #10 is
stacked on the still-experimental dynamic-pitch/editor branch.
