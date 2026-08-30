#ifndef BOILED_EGG_RESEARCH_PV_RT_H
#define BOILED_EGG_RESEARCH_PV_RT_H

#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define BOILEDEGG_RESEARCH_PV_RT_ABI_VERSION 1u

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

typedef struct boiledegg_research_pv_rt_config {
    uint32_t struct_size;
    uint32_t abi_version;
    uint32_t sample_rate;
    uint32_t channels;
    uint32_t max_block_frames;
    uint32_t fft_size;
    uint32_t analysis_hop;
    uint32_t mode;
    float initial_time_ratio;
    float transient_floor;
    float transient_sigma;
} boiledegg_research_pv_rt_config;

boiledegg_research_pv_rt_config boiledegg_research_pv_rt_default_config(
    uint32_t sample_rate, uint32_t channels, uint32_t max_block_frames);

boiledegg_research_pv_rt_handle* boiledegg_research_pv_rt_create(
    const boiledegg_research_pv_rt_config* config,
    boiledegg_research_pv_rt_result* result);

void boiledegg_research_pv_rt_destroy(boiledegg_research_pv_rt_handle* handle);
boiledegg_research_pv_rt_result boiledegg_research_pv_rt_reset(boiledegg_research_pv_rt_handle* handle);
boiledegg_research_pv_rt_result boiledegg_research_pv_rt_set_time_ratio(boiledegg_research_pv_rt_handle* handle, float ratio);
float boiledegg_research_pv_rt_get_time_ratio(const boiledegg_research_pv_rt_handle* handle);
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
