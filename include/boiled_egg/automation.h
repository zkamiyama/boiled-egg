#ifndef BOILED_EGG_AUTOMATION_H
#define BOILED_EGG_AUTOMATION_H
#include <boiled_egg/backend.h>
#ifdef __cplusplus
extern "C" {
#endif
#define BOILEDEGG_AUTOMATION_VERSION 1u
#define BOILEDEGG_MAX_RAMP_EVENTS 256u
/* Curve is independent of parameter units. LOG_RATIO gives linear semitones.
 * duration_frames=0 is a step; positive N reaches its target on the Nth input
 * sample, counting the sample at sample_offset as 1. A later event restarts
 * from the current effective value, including when its target is unchanged. */
typedef enum boiledegg_ramp_curve {
    BOILEDEGG_RAMP_LINEAR_RATIO = 0,
    BOILEDEGG_RAMP_LOG_RATIO = 1
} boiledegg_ramp_curve;
typedef struct boiledegg_ramp_event {
    uint32_t struct_size, sample_offset, parameter_id, duration_frames;
    uint32_t curve;
    float value;
    uint32_t reserved[2];
} boiledegg_ramp_event;
typedef struct boiledegg_automation_info {
    uint32_t struct_size, version;
    uint64_t input_frames;
    double output_position, intermediate_position;
    double effective_pitch_ratio, effective_time_ratio;
    float target_pitch_ratio, target_time_ratio;
    uint32_t pitch_remaining_frames, time_remaining_frames;
} boiledegg_automation_info;
/* These entry points have ONE audio owner; they are not UI-thread mailboxes.
 * Requires an explicitly enabled continuous spectral backend. Legacy entry
 * points keep their existing behavior, including the default 10-ms pitch ramp.
 * Events are sorted by input sample offset; duplicates use array order. The
 * entire batch is validated before DSP/output mutation. A 0-frame call accepts
 * offset-0 events and changes no processing mode. Records use the fixed array
 * stride sizeof(boiledegg_ramp_event); struct_size must equal that size.
 * Pitch ratio/semitones supported. Formant events are intentionally still on
 * the old API. No audible sample-instant change or hard-RT guarantee implied. */
BOILEDEGG_API boiledegg_result boiledegg_process_realtime_ramps(
    boiledegg_handle*, const float* const*, float* const*, uint32_t frames,
    const boiledegg_ramp_event*, uint32_t count);
/* May accept a prefix because of backpressure. Events at offsets >=accepted
 * are NOT consumed. Retry only that suffix with offsets rebased; pull advances
 * neither control ramp. A previously accepted ramp continues across calls. */
BOILEDEGG_API boiledegg_result boiledegg_push_ramps(
    boiledegg_handle*, const float* const*, uint32_t frames,
    const boiledegg_ramp_event*, uint32_t count, uint32_t* accepted);
/* Audio-owner snapshot, not concurrently callable with processing. Does not
 * advance clocks. Reset discards the trajectory and retains requested targets. */
BOILEDEGG_API boiledegg_result boiledegg_get_automation_info(
    const boiledegg_handle*, boiledegg_automation_info*);
#ifdef __cplusplus
}
#endif
#endif
