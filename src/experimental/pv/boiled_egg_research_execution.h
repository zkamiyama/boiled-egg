#ifndef BOILED_EGG_RESEARCH_EXECUTION_H
#define BOILED_EGG_RESEARCH_EXECUTION_H
#include "boiled_egg_research_features.h"
#ifdef __cplusplus
extern "C" {
#endif
#define BOILEDEGG_RESEARCH_EXECUTION_VERSION 1u
/* Opt-in single-owner execution. No worker threads or locks. Existing create
 * functions retain immediate scalar execution. Cooperatively scheduled mode
 * currently supports time=1, static pitch [0.5,2], hop>=64; formants may change.
 * Pitch/time changes after the first input sample are rejected, not flushed
 * through an asynchronous frame. reset/flush are bounded offline operations,
 * NOT covered by the small-callback timing guarantee. There is no such portable
 * timing guarantee: inspect measured deadline misses on the target machine. */
typedef struct boiledegg_research_execution {
    uint32_t struct_size;
    uint32_t version;
    uint32_t scheduled; /* 0 immediate; 1 input-clock cooperative slices */
    uint32_t simd;      /* 0 scalar; 1 SSE2 if compiled, otherwise scalar */
} boiledegg_research_execution;
typedef struct boiledegg_research_execution_stats {
    uint32_t struct_size;
    uint32_t steps_per_input;
    uint64_t completed_frames;
    uint64_t frame_overruns;
    uint64_t max_frame_steps;
} boiledegg_research_execution_stats;
boiledegg_research_execution boiledegg_research_default_execution(void);
uint32_t boiledegg_research_simd_available(void);
/* Product-private construction-time opt-in. Not installed or exported. */
boiledegg_research_pv_rt_result boiledegg_private_pv_enable_timeline(boiledegg_research_pv_rt_handle*);
boiledegg_research_pv_rt_handle* boiledegg_research_pv_rt_create_exec(
    const boiledegg_research_pv_rt_config*, const boiledegg_research_features*,
    const boiledegg_research_execution*, boiledegg_research_pv_rt_result*);
boiledegg_research_multires_rt_handle* boiledegg_research_multires_rt_create_exec(
    const boiledegg_research_multires_rt_config*, const boiledegg_research_features*,
    const boiledegg_research_execution*, boiledegg_research_pv_rt_result*);
/* Single-owner snapshots; unlike the later host mailbox these are not UI calls. */
boiledegg_research_pv_rt_result boiledegg_research_pv_rt_execution_stats(
    const boiledegg_research_pv_rt_handle*, boiledegg_research_execution_stats*);
boiledegg_research_pv_rt_result boiledegg_research_multires_rt_execution_stats(
    const boiledegg_research_multires_rt_handle*, boiledegg_research_execution_stats*);
#ifdef __cplusplus
}
#endif
#endif
