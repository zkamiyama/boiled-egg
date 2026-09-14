#ifndef BOILED_EGG_RESEARCH_MULTIRES_RT_H
#define BOILED_EGG_RESEARCH_MULTIRES_RT_H

#include "boiled_egg_pv_rt.h"

#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define BOILEDEGG_RESEARCH_MULTIRES_RT_ABI_VERSION 1u

typedef struct boiledegg_research_multires_rt_handle boiledegg_research_multires_rt_handle;

typedef struct boiledegg_research_multires_rt_config {
    uint32_t struct_size;
    uint32_t abi_version;
    uint32_t sample_rate;
    uint32_t channels;
    uint32_t max_block_frames;
    float initial_time_ratio;
    float initial_pitch_ratio;
    uint32_t formant_mode;
    uint32_t formant_cepstral_order;
    float formant_gain_limit_db;
    float monophonic_min_f0_hz;
    float monophonic_max_f0_hz;
    float crossover_hz;
    uint32_t fir_taps;
} boiledegg_research_multires_rt_config;

boiledegg_research_multires_rt_config boiledegg_research_multires_rt_default_config(
    uint32_t sample_rate,
    uint32_t channels,
    uint32_t max_block_frames);

boiledegg_research_multires_rt_handle* boiledegg_research_multires_rt_create(
    const boiledegg_research_multires_rt_config* config,
    boiledegg_research_pv_rt_result* result);

void boiledegg_research_multires_rt_destroy(boiledegg_research_multires_rt_handle* handle);
boiledegg_research_pv_rt_result boiledegg_research_multires_rt_reset(boiledegg_research_multires_rt_handle* handle);
boiledegg_research_pv_rt_result boiledegg_research_multires_rt_set_time_ratio(boiledegg_research_multires_rt_handle* handle, float ratio);
float boiledegg_research_multires_rt_get_time_ratio(const boiledegg_research_multires_rt_handle* handle);
boiledegg_research_pv_rt_result boiledegg_research_multires_rt_set_pitch_ratio(boiledegg_research_multires_rt_handle* handle, float ratio);
float boiledegg_research_multires_rt_get_pitch_ratio(const boiledegg_research_multires_rt_handle* handle);
boiledegg_research_pv_rt_result boiledegg_research_multires_rt_push(
    boiledegg_research_multires_rt_handle* handle,
    const float* const* input,
    uint32_t frames);
uint32_t boiledegg_research_multires_rt_available(const boiledegg_research_multires_rt_handle* handle);
uint32_t boiledegg_research_multires_rt_pull(
    boiledegg_research_multires_rt_handle* handle,
    float* const* output,
    uint32_t capacity_frames);
boiledegg_research_pv_rt_result boiledegg_research_multires_rt_flush(boiledegg_research_multires_rt_handle* handle);
uint32_t boiledegg_research_multires_rt_latency_frames(const boiledegg_research_multires_rt_handle* handle);
uint64_t boiledegg_research_multires_rt_input_frames(const boiledegg_research_multires_rt_handle* handle);
uint64_t boiledegg_research_multires_rt_output_frames(const boiledegg_research_multires_rt_handle* handle);

#ifdef __cplusplus
}
#endif
#endif
