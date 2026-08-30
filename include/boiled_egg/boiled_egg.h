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

typedef enum boiledegg_result {
    BOILEDEGG_OK = 0,
    BOILEDEGG_INVALID_ARGUMENT = 1,
    BOILEDEGG_OUT_OF_MEMORY = 2,
    BOILEDEGG_BUFFER_FULL = 3,
    BOILEDEGG_END_OF_STREAM = 4,
    BOILEDEGG_INTERNAL_ERROR = 5
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
 *   32-bit atomic mailboxes and is observed at the next streaming API boundary.
 * - For one handle, push/pull/available/flush/is_drained are a single-owner
 *   streaming interface. Do not call them concurrently from multiple threads.
 * - reset and destroy are lifecycle operations: serialize them with streaming;
 *   destroy must not race with any call using the same handle.
 *
 * This is intentionally optimized for DAWs: parallelize across track/plugin
 * instances, not by placing a mutex around one instance's DSP state machine.
 *
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

/* Input-side algorithmic lookahead estimate, useful for host scheduling. */
BOILEDEGG_API uint32_t boiledegg_input_latency_frames(const boiledegg_handle* handle);

#ifdef __cplusplus
}
#endif

#endif
