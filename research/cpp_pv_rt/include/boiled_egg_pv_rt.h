#ifndef BOILED_EGG_RESEARCH_PV_RT_H
#define BOILED_EGG_RESEARCH_PV_RT_H

#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define BOILEDEGG_RESEARCH_PV_RT_ABI_VERSION 2u

typedef struct boiledegg_research_pv_rt_handle boiledegg_research_pv_rt_handle;

typedef enum boiledegg_research_pv_rt_result {
    BOILEDEGG_RESEARCH_PV_RT_OK = 0,
    BOILEDEGG_RESEARCH_PV_RT_INVALID_ARGUMENT = 1,
    BOILEDEGG_RESEARCH_PV_RT_INVALID_CONFIG = 2,
    BOILEDEGG_RESEARCH_PV_RT_OUT_OF_MEMORY = 3,
    BOILEDEGG_RESEARCH_PV_RT_FIFO_OVERFLOW = 4,
    BOILEDEGG_RESEARCH_PV_RT_ALREADY_FLUSHED = 5,
    BOILEDEGG_RESEARCH_PV_RT_INTERNAL_ERROR = 6
} boiledegg_research_pv_rt_result;

typedef enum boiledegg_research_pv_rt_mode {
    BOILEDEGG_RESEARCH_PV_RT_CLASSIC = 0,
    BOILEDEGG_RESEARCH_PV_RT_PHASE_LOCKED = 1,
    BOILEDEGG_RESEARCH_PV_RT_TRANSIENT = 2
} boiledegg_research_pv_rt_mode;

/*
 * User-facing research quality presets. These are intentionally separate from
 * boiledegg_research_pv_rt_mode: the low-level TRANSIENT mode above means
 * frame-level phase reset, while the TRANSIENT quality profile below selects
 * the independently validated shorter phase-locked analysis window.
 */
typedef enum boiledegg_research_pv_rt_quality_profile {
    BOILEDEGG_RESEARCH_PV_RT_PROFILE_GENERAL = 0,
    BOILEDEGG_RESEARCH_PV_RT_PROFILE_TRANSIENT = 1
} boiledegg_research_pv_rt_quality_profile;

/*
 * Spectral-envelope handling for pitch shifting.
 *
 * HARMONIC is the polyphonic/general path: one linked spectral envelope is
 * estimated and pre-warped for the later resampling stage.
 * MONOPHONIC uses the same envelope estimate but gates correction around a
 * cepstrally estimated harmonic series to reduce amplification of spectral
 * valleys/noise on voiced single-pitch material.
 */
typedef enum boiledegg_research_pv_rt_formant_mode {
    BOILEDEGG_RESEARCH_PV_RT_FORMANT_OFF = 0,
    BOILEDEGG_RESEARCH_PV_RT_FORMANT_HARMONIC = 1,
    BOILEDEGG_RESEARCH_PV_RT_FORMANT_MONOPHONIC = 2
} boiledegg_research_pv_rt_formant_mode;

typedef struct boiledegg_research_pv_rt_config {
    uint32_t struct_size;
    uint32_t abi_version;
    uint32_t sample_rate;
    uint32_t channels;
    uint32_t max_block_frames;
    uint32_t fft_size;
    uint32_t analysis_hop;
    uint32_t mode;
    float initial_time_ratio;      /* final output duration / input duration */
    float initial_pitch_ratio;     /* output frequency / input frequency */
    float transient_floor;
    float transient_sigma;
    uint32_t formant_mode;
    uint32_t formant_cepstral_order;
    float formant_gain_limit_db;
    float monophonic_min_f0_hz;
    float monophonic_max_f0_hz;
} boiledegg_research_pv_rt_config;

boiledegg_research_pv_rt_config boiledegg_research_pv_rt_default_config(
    uint32_t sample_rate, uint32_t channels, uint32_t max_block_frames);

/*
 * Apply only the quality-dependent PV window/phase settings. Formant mode,
 * pitch/time ratios and all other user choices are preserved.
 *
 * GENERAL   = 2048 FFT / 256 hop / phase locked
 * TRANSIENT = 1024 FFT / 256 hop / phase locked
 */
boiledegg_research_pv_rt_result boiledegg_research_pv_rt_configure_quality_profile(
    boiledegg_research_pv_rt_config* config,
    uint32_t profile);

boiledegg_research_pv_rt_handle* boiledegg_research_pv_rt_create(
    const boiledegg_research_pv_rt_config* config,
    boiledegg_research_pv_rt_result* result);

void boiledegg_research_pv_rt_destroy(boiledegg_research_pv_rt_handle* handle);
boiledegg_research_pv_rt_result boiledegg_research_pv_rt_reset(boiledegg_research_pv_rt_handle* handle);
boiledegg_research_pv_rt_result boiledegg_research_pv_rt_set_time_ratio(boiledegg_research_pv_rt_handle* handle, float ratio);
float boiledegg_research_pv_rt_get_time_ratio(const boiledegg_research_pv_rt_handle* handle);
boiledegg_research_pv_rt_result boiledegg_research_pv_rt_set_pitch_ratio(boiledegg_research_pv_rt_handle* handle, float ratio);
float boiledegg_research_pv_rt_get_pitch_ratio(const boiledegg_research_pv_rt_handle* handle);
boiledegg_research_pv_rt_result boiledegg_research_pv_rt_push(boiledegg_research_pv_rt_handle* handle, const float* const* input, uint32_t frames);
uint32_t boiledegg_research_pv_rt_available(const boiledegg_research_pv_rt_handle* handle);
uint32_t boiledegg_research_pv_rt_pull(boiledegg_research_pv_rt_handle* handle, float* const* output, uint32_t capacity_frames);
boiledegg_research_pv_rt_result boiledegg_research_pv_rt_flush(boiledegg_research_pv_rt_handle* handle);
uint32_t boiledegg_research_pv_rt_latency_frames(const boiledegg_research_pv_rt_handle* handle);
uint64_t boiledegg_research_pv_rt_input_frames(const boiledegg_research_pv_rt_handle* handle);
uint64_t boiledegg_research_pv_rt_output_frames(const boiledegg_research_pv_rt_handle* handle);
const char* boiledegg_research_pv_rt_result_string(boiledegg_research_pv_rt_result result);

#ifdef __cplusplus
}
#endif
#endif
