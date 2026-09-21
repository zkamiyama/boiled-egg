#ifndef BOILED_EGG_BOILED_EGG_H
#define BOILED_EGG_BOILED_EGG_H

#include <stdint.h>

#if defined(_WIN32)
  #if defined(BOILED_EGG_STATIC)
    #define BOILEDEGG_API
  #elif defined(BOILED_EGG_BUILDING_LIBRARY)
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

/*
 * User-selected algorithm profile. This is a lifecycle/configuration choice,
 * not a sample-accurate automation parameter. Recreate the handle to change it.
 */
typedef enum boiledegg_quality_mode {
    BOILEDEGG_QUALITY_GENERAL = 0,
    BOILEDEGG_QUALITY_TRANSIENT = 1,
    BOILEDEGG_QUALITY_EFFICIENT = 2,
    BOILEDEGG_QUALITY_MONOPHONIC = 3
} boiledegg_quality_mode;

typedef enum boiledegg_formant_mode {
    BOILEDEGG_FORMANT_OFF = 0,
    BOILEDEGG_FORMANT_PRESERVE = 1
} boiledegg_formant_mode;

typedef struct boiledegg_profile_config {
    uint32_t struct_size;
    uint32_t quality_mode;
    uint32_t formant_mode;
    uint32_t reserved;
} boiledegg_profile_config;

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

/* Backend-independent state suitable for project/preset serialization. */
typedef struct boiledegg_parameter_state {
    uint32_t struct_size;
    float time_ratio;
    float pitch_ratio;
    uint32_t reserved;
} boiledegg_parameter_state;

/* boiledegg_runtime_info::capabilities */
#define BOILEDEGG_CAP_PARALLEL_INSTANCES           (1u << 0)
#define BOILEDEGG_CAP_CONTROL_THREAD_PARAMETERS    (1u << 1)
#define BOILEDEGG_CAP_FIXED_REALTIME_IO            (1u << 2)
#define BOILEDEGG_CAP_SAMPLE_OFFSET_EVENTS         (1u << 3)
#define BOILEDEGG_CAP_SAMPLE_ACCURATE_AUTOMATION   (1u << 4)
#define BOILEDEGG_CAP_IN_PLACE_REALTIME_IO         (1u << 5)
#define BOILEDEGG_CAP_REALTIME_RESET               (1u << 6)
#define BOILEDEGG_CAP_HARD_REALTIME_PROCESSING     (1u << 7)
#define BOILEDEGG_CAP_PARAMETER_ONLY_FLUSH         (1u << 8)

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
BOILEDEGG_API boiledegg_profile_config boiledegg_default_profile(void);
BOILEDEGG_API int boiledegg_profile_is_supported(const boiledegg_profile_config* profile);
BOILEDEGG_API uint32_t boiledegg_abi_version(void);
BOILEDEGG_API const char* boiledegg_version_string(void);
BOILEDEGG_API const char* boiledegg_result_string(boiledegg_result result);

/* Existing creation API: equivalent to boiledegg_create_ex() with default profile. */
BOILEDEGG_API boiledegg_handle* boiledegg_create(const boiledegg_config* config, boiledegg_result* out_result);

/*
 * Explicit manual algorithm selection. General/Transient/Efficient are
 * supported by the current product backend. Monophonic and formant-preserving
 * profiles become supported only when their quality backends pass the product
 * gates; until then this returns NULL with BOILEDEGG_UNSUPPORTED_MODE.
 */
BOILEDEGG_API boiledegg_handle* boiledegg_create_ex(
    const boiledegg_config* config,
    const boiledegg_profile_config* profile,
    boiledegg_result* out_result);

BOILEDEGG_API void boiledegg_destroy(boiledegg_handle* handle);

/*
 * Clears DSP/FIFO state while preserving requested parameter values.
 * This performs no allocation or locking and may be called by the sole audio
 * owner between process calls (for example CLAP's audio-thread reset callback).
 * It must not race with another call on the same handle.
 */
BOILEDEGG_API boiledegg_result boiledegg_reset(boiledegg_handle* handle);

/* output-duration / input-duration. Valid range: 0.25 .. 4.0 */
BOILEDEGG_API boiledegg_result boiledegg_set_time_ratio(boiledegg_handle* handle, float ratio);

/* Pitch shift in semitones. Valid range: -24 .. +24 */
BOILEDEGG_API boiledegg_result boiledegg_set_pitch_semitones(boiledegg_handle* handle, float semitones);
BOILEDEGG_API boiledegg_result boiledegg_set_pitch_ratio(boiledegg_handle* handle, float ratio);

BOILEDEGG_API float boiledegg_get_time_ratio(const boiledegg_handle* handle);
BOILEDEGG_API float boiledegg_get_pitch_ratio(const boiledegg_handle* handle);

/*
 * Parameter-only host flush. All sample_offset fields must be zero. The whole
 * batch is validated before any value is published. This function only writes
 * lock-free parameter mailboxes, so it is safe wherever the individual setter
 * functions are safe. It does not select a processing mode.
 */
BOILEDEGG_API boiledegg_result boiledegg_apply_parameter_events(
    boiledegg_handle* handle,
    const boiledegg_parameter_event* events,
    uint32_t event_count);

/* Backend-independent parameter snapshot for project/preset state. */
BOILEDEGG_API boiledegg_result boiledegg_get_parameter_state(
    const boiledegg_handle* handle,
    boiledegg_parameter_state* out_state);
BOILEDEGG_API boiledegg_result boiledegg_set_parameter_state(
    boiledegg_handle* handle,
    const boiledegg_parameter_state* state);

/*
 * Threading contract:
 *
 * - Distinct boiledegg_handle instances are independent and may be processed
 *   concurrently on different DAW worker/audio threads.
 * - The audio owner for one handle may migrate between OS threads from one
 *   non-overlapping processing call to the next; there is no thread affinity.
 * - Time/pitch setters and their getters may run on a control/UI thread
 *   concurrently with the streaming thread. Parameter transfer uses lock-free
 *   32-bit atomic mailboxes.
 * - For one handle, all streaming/realtime processing calls are single-owner.
 *   Do not call them concurrently from multiple audio threads.
 * - reset is realtime-safe when called serially by that audio owner. destroy is
 *   a lifecycle operation and must not race with any call using the handle.
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
 * `events` may be NULL when event_count == 0. For frames > 0, events must be
 * sorted by non-decreasing sample_offset and use offsets < frames. Multiple
 * events at the same offset are applied in array order. The current WSOLA
 * backend quantizes audible automation to its DSP quantum, so
 * BOILEDEGG_CAP_SAMPLE_ACCURATE_AUTOMATION is intentionally not set.
 *
 * When frames == 0, input/output may be NULL and events are treated as a
 * parameter-only host flush; every event must have sample_offset == 0. This
 * does not select realtime vs streaming mode.
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
