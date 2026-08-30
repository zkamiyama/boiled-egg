#ifndef BOILED_EGG_BOILED_EGG_H
#define BOILED_EGG_BOILED_EGG_H

#include <stdint.h>

#if defined(_WIN32)
  #if defined(BOILED_EGG_BUILDING_LIBRARY)
    #define BOILEDEGG_API __declspec(dllexport)
  #else
    #define BOILEDEGG_API __declspec(dllimport)
  #endif
#else
  #define BOILEDEGG_API __attribute__((visibility("default")))
#endif

#ifdef __cplusplus
extern "C" {
#endif

typedef struct boiledegg_handle boiledegg_handle;

#define BOILEDEGG_ABI_VERSION 1u
#define BOILEDEGG_MAX_CHANNELS 32u

typedef enum boiledegg_result {
    BOILEDEGG_OK = 0,
    BOILEDEGG_INVALID_ARGUMENT = 1,
    BOILEDEGG_OUT_OF_MEMORY = 2,
    BOILEDEGG_BUFFER_FULL = 3,
    BOILEDEGG_END_OF_STREAM = 4,
    BOILEDEGG_INTERNAL_ERROR = 5,
    BOILEDEGG_INVALID_STATE = 6,
    BOILEDEGG_UNSUPPORTED_MODE = 7,
    BOILEDEGG_REALTIME_UNDERRUN = 8
} boiledegg_result;

typedef struct boiledegg_config {
    uint32_t struct_size;
    uint32_t abi_version;
    uint32_t sample_rate;
    uint32_t channels;
    uint32_t max_block_size;
    uint32_t window_frames;
    uint32_t search_frames;
    uint32_t fifo_frames;
} boiledegg_config;

typedef enum boiledegg_parameter_id {
    BOILEDEGG_PARAMETER_TIME_RATIO = 1,
    BOILEDEGG_PARAMETER_PITCH_RATIO = 2,
    BOILEDEGG_PARAMETER_PITCH_SEMITONES = 3
} boiledegg_parameter_id;

typedef struct boiledegg_parameter_event {
    uint32_t struct_size;
    uint32_t sample_offset;
    uint32_t parameter_id;
    float value;
} boiledegg_parameter_event;

/* boiledegg_runtime_info::capabilities */
#define BOILEDEGG_CAP_PARALLEL_INSTANCES          (1u << 0)
#define BOILEDEGG_CAP_CONTROL_THREAD_PARAMETERS   (1u << 1)
#define BOILEDEGG_CAP_FIXED_REALTIME_IO           (1u << 2)
#define BOILEDEGG_CAP_SAMPLE_OFFSET_EVENTS        (1u << 3)
#define BOILEDEGG_CAP_SAMPLE_ACCURATE_AUTOMATION  (1u << 4)
#define BOILEDEGG_CAP_IN_PLACE_REALTIME_IO        (1u << 5)

typedef struct boiledegg_runtime_info {
    uint32_t struct_size;
    uint32_t sample_rate;
    uint32_t channels;
    uint32_t max_block_size;
    uint32_t realtime_latency_frames;
    uint32_t realtime_tail_frames;
    uint32_t parameter_quantum_frames;
    uint32_t capabilities;
} boiledegg_runtime_info;

BOILEDEGG_API boiledegg_config boiledegg_default_config(uint32_t sample_rate, uint32_t channels);
BOILEDEGG_API uint32_t boiledegg_abi_version(void);
BOILEDEGG_API const char* boiledegg_version_string(void);
BOILEDEGG_API const char* boiledegg_result_string(boiledegg_result result);

BOILEDEGG_API boiledegg_handle* boiledegg_create(const boiledegg_config* config, boiledegg_result* out_result);
BOILEDEGG_API void boiledegg_destroy(boiledegg_handle* handle);
BOILEDEGG_API boiledegg_result boiledegg_reset(boiledegg_handle* handle);

/* output-duration / input-duration. Valid range in v0.1: 0.25 .. 4.0 */
BOILEDEGG_API boiledegg_result boiledegg_set_time_ratio(boiledegg_handle* handle, float ratio);

/* Pitch shift in semitones. Valid range in v0.1: -24 .. +24 */
BOILEDEGG_API boiledegg_result boiledegg_set_pitch_semitones(boiledegg_handle* handle, float semitones);
BOILEDEGG_API boiledegg_result boiledegg_set_pitch_ratio(boiledegg_handle* handle, float ratio);

BOILEDEGG_API float boiledegg_get_time_ratio(const boiledegg_handle* handle);
BOILEDEGG_API float boiledegg_get_pitch_ratio(const boiledegg_handle* handle);

/*
 * Threading contract:
 *
 * - Distinct boiledegg_handle instances are independent and may be processed
 *   concurrently on different DAW worker/audio threads.
 * - Time/pitch setters and their getters may run on a control/UI thread
 *   concurrently with the streaming thread. Parameter transfer uses lock-free
 *   32-bit atomic mailboxes.
 * - For one handle, all streaming/realtime processing calls are single-owner.
 *   Do not call them concurrently from multiple audio threads.
 * - reset and destroy are lifecycle operations: serialize them with processing;
 *   destroy must not race with any call using the same handle.
 *
 * A handle selects one processing mode after reset: either variable-rate
 * push/pull streaming, or fixed-I/O realtime processing. Mixing both modes on
 * one handle returns BOILEDEGG_INVALID_STATE until boiledegg_reset().
 */

/*
 * Variable-rate streaming API for time-scale modification.
 * Audio is non-interleaved planar float32. Push may accept fewer frames only
 * if the fixed-capacity input FIFO is full. Pull never allocates or blocks.
 */
BOILEDEGG_API boiledegg_result boiledegg_push(
    boiledegg_handle* handle,
    const float* const* input,
    uint32_t frames,
    uint32_t* accepted_frames);

BOILEDEGG_API uint32_t boiledegg_available(const boiledegg_handle* handle);

BOILEDEGG_API boiledegg_result boiledegg_pull(
    boiledegg_handle* handle,
    float* const* output,
    uint32_t capacity_frames,
    uint32_t* produced_frames);

/* Signal end-of-stream. Internally zero-pads only enough to drain the pipeline. */
BOILEDEGG_API boiledegg_result boiledegg_flush(boiledegg_handle* handle);
BOILEDEGG_API int boiledegg_is_drained(const boiledegg_handle* handle);

/*
 * Fixed-I/O realtime API for DAW insert/plugin use.
 *
 * Exactly `frames` samples are written for every channel. Startup latency is
 * represented by deterministic zero padding and is reported through
 * boiledegg_get_runtime_info(). The current backend requires time_ratio == 1;
 * use push/pull for actual time-scale modification.
 *
 * `events` may be NULL when event_count == 0. Events must be sorted by
 * non-decreasing sample_offset and use offsets < frames. Multiple events at the
 * same offset are applied in array order. v0.1 accepts sample-offset events but
 * the WSOLA backend quantizes their audible application to its DSP quantum;
 * therefore BOILEDEGG_CAP_SAMPLE_ACCURATE_AUTOMATION is intentionally not set.
 *
 * In-place processing (input[ch] == output[ch]) is supported.
 */
BOILEDEGG_API boiledegg_result boiledegg_process_realtime(
    boiledegg_handle* handle,
    const float* const* input,
    float* const* output,
    uint32_t frames,
    const boiledegg_parameter_event* events,
    uint32_t event_count);

/* Static for the lifetime of the current handle/backend configuration. */
BOILEDEGG_API boiledegg_result boiledegg_get_runtime_info(
    const boiledegg_handle* handle,
    boiledegg_runtime_info* out_info);

/* Input-side lookahead for variable-rate streaming. */
BOILEDEGG_API uint32_t boiledegg_input_latency_frames(const boiledegg_handle* handle);

#ifdef __cplusplus
}
#endif

#endif
