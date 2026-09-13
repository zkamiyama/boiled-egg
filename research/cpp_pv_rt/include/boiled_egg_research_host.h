#ifndef BOILED_EGG_RESEARCH_HOST_H
#define BOILED_EGG_RESEARCH_HOST_H
#include "boiled_egg_research_execution.h"
#ifdef __cplusplus
extern "C" {
#endif
#define BOILEDEGG_RESEARCH_HOST_VERSION 1u
#define BOILEDEGG_RESEARCH_HOST_MAX_EVENTS 256u
/* Isolated fixed-latency pitch-effect bridge, NOT the product SDK ABI.
 * Static pitch [0.5,2], time=1. Pitch/profile/rate changes require recreation.
 * Formants may be automated. One audio owner; UI may call request/get_target
 * and state_get/state_request concurrently. Lifecycle calls need exclusion.
 * Execution is single-thread cooperative, not a worker thread or async task. */
typedef enum boiledegg_research_host_profile {
    BOILEDEGG_RESEARCH_HOST_GENERAL=0,
    BOILEDEGG_RESEARCH_HOST_TRANSIENT=1,
    BOILEDEGG_RESEARCH_HOST_FUZZY=2,
    BOILEDEGG_RESEARCH_HOST_MULTIRES=3,
    BOILEDEGG_RESEARCH_HOST_FUZZY_NOISE=4
} boiledegg_research_host_profile;
typedef struct boiledegg_research_host_config {
    uint32_t struct_size,version,sample_rate,channels,max_block_frames;
    uint32_t profile,formant_mode;
    float pitch_ratio,formant_ratio;
    uint32_t scheduled,simd;
} boiledegg_research_host_config;
typedef struct boiledegg_research_host_event {
    uint32_t struct_size,sample_offset;
    float formant_ratio;
    uint32_t reserved; /* zero */
} boiledegg_research_host_event;
typedef struct boiledegg_research_host_stats {
    uint32_t struct_size,latency_frames;
    uint64_t input_frames,applied_events,underruns;
    boiledegg_research_execution_stats execution;
} boiledegg_research_host_stats;
typedef struct boiledegg_research_host_state {
    uint32_t struct_size,version;
    float formant_ratio;
    uint32_t reserved; /* zero; this state only describes the automatable target */
} boiledegg_research_host_state;
typedef struct boiledegg_research_host_handle boiledegg_research_host_handle;
boiledegg_research_host_config boiledegg_research_host_default_config(uint32_t rate,uint32_t channels,uint32_t block);
boiledegg_research_host_handle* boiledegg_research_host_create(const boiledegg_research_host_config*,boiledegg_research_pv_rt_result*);
/* Opt-in pitch-aware conservative availability bound. Same ABI/config and
 * event semantics; legacy create() retains its old fixed delay. The bound
 * assumes the declared zero-overrun scheduling contract, not a CPU guarantee.
 * Query before activation; invalid config returns0. */
uint32_t boiledegg_research_host_compact_latency(const boiledegg_research_host_config*);
boiledegg_research_host_handle* boiledegg_research_host_create_compact(const boiledegg_research_host_config*,boiledegg_research_pv_rt_result*);
void boiledegg_research_host_destroy(boiledegg_research_host_handle*);
boiledegg_research_pv_rt_result boiledegg_research_host_reset(boiledegg_research_host_handle*);
/* Exactly frames output on success, including initial latency zeros. Null input
 * means silence/tail. Exact in-place planar input/output is allowed. Events are
 * validated atomically, sorted by offset, offset<frames, max256; last duplicate
 * offset wins. Targets apply before that input sample; the first eligible STFT
 * frame latches them with 10ms smoothing, NOT a sample-instant spectral change.
 * UI mailbox is consumed once at block start, then timestamped events override.
 * Invalid arguments leave DSP/output untouched. Internal underrun faults the
 * handle until reset (remaining outputs zero), never changes the declared delay.
 * Drain by processing silence, not by calling the research offline flush(). */
boiledegg_research_pv_rt_result boiledegg_research_host_process(boiledegg_research_host_handle*,
    const float* const* input,float* const* output,uint32_t frames,
    const boiledegg_research_host_event* events,uint32_t event_count);
uint32_t boiledegg_research_host_latency_frames(const boiledegg_research_host_handle*);
/* Lock-free latest-value mailbox: bounded work, no spin, latest request wins.
 * get_target is an atomic UI/state snapshot, not an audio-history timestamp. */
boiledegg_research_pv_rt_result boiledegg_research_host_request_formant(boiledegg_research_host_handle*,float ratio);
float boiledegg_research_host_get_target(const boiledegg_research_host_handle*);
boiledegg_research_pv_rt_result boiledegg_research_host_state_get(const boiledegg_research_host_handle*,boiledegg_research_host_state*);
boiledegg_research_pv_rt_result boiledegg_research_host_state_request(boiledegg_research_host_handle*,const boiledegg_research_host_state*);
/* Stats snapshot is audio-owner only; latency/config/target do not require it. */
boiledegg_research_pv_rt_result boiledegg_research_host_get_stats(const boiledegg_research_host_handle*,boiledegg_research_host_stats*);
#ifdef __cplusplus
}
#endif
#endif
