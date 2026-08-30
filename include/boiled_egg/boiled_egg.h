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

/* Lifecycle/configuration choice, not a sample-accurate parameter. */
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

/*
 * Formant-envelope estimator/processor. AUTO is reserved for a future
 * user-opted adaptive selector; it does not imply automatic switching today.
 * HARMONIC is intended for polyphonic/harmonic material using a smooth
 * spectral-envelope model. MONOPHONIC is intended for voice/single-note
 * material and may use F0/partial tracking.
 */
typedef enum boiledegg_formant_strategy {
    BOILEDEGG_FORMANT_STRATEGY_AUTO = 0,
    BOILEDEGG_FORMANT_STRATEGY_HARMONIC = 1,
    BOILEDEGG_FORMANT_STRATEGY_MONOPHONIC = 2
} boiledegg_formant_strategy;

typedef struct boiledegg_profile_config {
    uint32_t struct_size;
    uint32_t quality_mode;
    uint32_t formant_mode;
    uint32_t formant_strategy;
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

typedef struct boiledegg_parameter_state {
    uint32_t struct_size;
    float time_ratio;
    float pitch_ratio;
    uint32_t reserved;
} boiledegg_parameter_state;

#define BOILEDEGG_CAP_PARALLEL_INSTANCES           (1u << 0)
#define BOILEDEGG_CAP_CONTROL_THREAD_PARAMETERS    (1u << 1)
#define BOILEDEGG_CAP_FIXED_REALTIME_IO            (1u << 2)
#define BOILEDEGG_CAP_SAMPLE_OFFSET_EVENTS         (1u << 3)
#define BOILEDEGG_CAP_SAMPLE_ACCURATE_AUTOMATION   (1u << 4)
#define BOILEDEGG_CAP_IN_PLACE_REALTIME_IO         (1u << 5)
#define BOILEDEGG_CAP_REALTIME_RESET               (1u << 6)
#define BOILEDEGG_CAP_HARD_REALTIME_PROCESSING     (1u << 7)
#define BOILEDEGG_CAP_PARAMETER_ONLY_FLUSH         (1u << 8)
#define BOILEDEGG_CAP_FORMANT_HARMONIC              (1u << 9)
#define BOILEDEGG_CAP_FORMANT_MONOPHONIC            (1u << 10)

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

BOILEDEGG_API boiledegg_handle* boiledegg_create(const boiledegg_config* config, boiledegg_result* out_result);
BOILEDEGG_API boiledegg_handle* boiledegg_create_ex(
    const boiledegg_config* config,
    const boiledegg_profile_config* profile,
    boiledegg_result* out_result);
BOILEDEGG_API void boiledegg_destroy(boiledegg_handle* handle);

BOILEDEGG_API boiledegg_result boiledegg_reset(boiledegg_handle* handle);
BOILEDEGG_API boiledegg_result boiledegg_set_time_ratio(boiledegg_handle* handle, float ratio);
BOILEDEGG_API boiledegg_result boiledegg_set_pitch_semitones(boiledegg_handle* handle, float semitones);
BOILEDEGG_API boiledegg_result boiledegg_set_pitch_ratio(boiledegg_handle* handle, float ratio);
BOILEDEGG_API float boiledegg_get_time_ratio(const boiledegg_handle* handle);
BOILEDEGG_API float boiledegg_get_pitch_ratio(const boiledegg_handle* handle);

BOILEDEGG_API boiledegg_result boiledegg_apply_parameter_events(
    boiledegg_handle* handle,
    const boiledegg_parameter_event* events,
    uint32_t event_count);
BOILEDEGG_API boiledegg_result boiledegg_get_parameter_state(
    const boiledegg_handle* handle,
    boiledegg_parameter_state* out_state);
BOILEDEGG_API boiledegg_result boiledegg_set_parameter_state(
    boiledegg_handle* handle,
    const boiledegg_parameter_state* state);

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
BOILEDEGG_API boiledegg_result boiledegg_flush(boiledegg_handle* handle);
BOILEDEGG_API int boiledegg_is_drained(const boiledegg_handle* handle);

BOILEDEGG_API boiledegg_result boiledegg_process_realtime(
    boiledegg_handle* handle,
    const float* const* input,
    float* const* output,
    uint32_t frames,
    const boiledegg_parameter_event* events,
    uint32_t event_count);
BOILEDEGG_API boiledegg_result boiledegg_get_runtime_info(
    const boiledegg_handle* handle,
    boiledegg_runtime_info* out_info);
BOILEDEGG_API uint32_t boiledegg_input_latency_frames(const boiledegg_handle* handle);

#ifdef __cplusplus
}
#endif

#endif
