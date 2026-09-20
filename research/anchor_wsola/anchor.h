#ifndef BE_RESEARCH_ANCHOR_H
#define BE_RESEARCH_ANCHOR_H
/* Finite-file research API only: not installed, not the product ABI. */
#include <stdint.h>
#ifdef __cplusplus
extern "C" {
#endif
/* mode: 0 free, 1 snap, 2 owned. Landmarks: source sample indices, ordered. */
typedef struct {
    uint32_t struct_size, sample_rate, channels, mode;
    double pitch_ratio;
    uint64_t memory_limit_bytes;
} be_anchor_config;
typedef struct {
    int64_t output_center, source_center, expected_center;
    int32_t anchor_index;
    uint32_t masked_samples;
    double correlation;
} be_anchor_grain;
typedef struct {
    uint64_t frames, grains, masked_samples, workspace_bytes;
    double min_weight, max_weight;
} be_anchor_info;
/* 0 success, 2 invalid/unsupported input, 3 allocation/budget, 4 uncovered, 5 arithmetic output failure.
   Caller buffers must be valid, separate, and sized by frame/trace_capacity.
   On error no PCM/trace output is written. No processing thread is spawned. */
int be_anchor_render(const float* input, uint64_t frames,
                     const int64_t* anchors, uint32_t anchor_count,
                     const be_anchor_config* config, float* output,
                     be_anchor_grain* trace, uint64_t trace_capacity,
                     be_anchor_info* info);
#ifdef __cplusplus
}
#endif
#endif
