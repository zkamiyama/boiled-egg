#include "boiled_egg_pv_rt.h"
#include <math.h>
#include <stdint.h>
#include <stdlib.h>

int main(void) {
    enum { block = 96, frames = 4800 };
    boiledegg_research_pv_rt_config config = boiledegg_research_pv_rt_default_config(48000U, 1U, block);
    config.initial_time_ratio = 1.5F;
    config.mode = BOILEDEGG_RESEARCH_PV_RT_PHASE_LOCKED;
    boiledegg_research_pv_rt_result result = BOILEDEGG_RESEARCH_PV_RT_INTERNAL_ERROR;
    boiledegg_research_pv_rt_handle* handle = boiledegg_research_pv_rt_create(&config, &result);
    if (handle == NULL || result != BOILEDEGG_RESEARCH_PV_RT_OK) return 1;
    float input[block]; float output[block * 8]; const float* input_ptrs[1] = {input}; float* output_ptrs[1] = {output};
    uint64_t pulled = 0;
    for (uint32_t position = 0; position < frames; position += block) {
        uint32_t count = block; if (position + count > frames) count = frames - position;
        for (uint32_t i = 0; i < count; ++i) input[i] = 0.25F * sinf(2.0F * 3.14159265358979323846F * 440.0F * (float)(position + i) / 48000.0F);
        result = boiledegg_research_pv_rt_push(handle, input_ptrs, count); if (result != BOILEDEGG_RESEARCH_PV_RT_OK) return 2;
        while (boiledegg_research_pv_rt_available(handle) != 0U) pulled += boiledegg_research_pv_rt_pull(handle, output_ptrs, block * 8U);
    }
    if (boiledegg_research_pv_rt_flush(handle) != BOILEDEGG_RESEARCH_PV_RT_OK) return 3;
    while (boiledegg_research_pv_rt_available(handle) != 0U) pulled += boiledegg_research_pv_rt_pull(handle, output_ptrs, block * 8U);
    if (pulled != 7200U) return 4;
    if (boiledegg_research_pv_rt_input_frames(handle) != frames) return 5;
    if (boiledegg_research_pv_rt_output_frames(handle) != pulled) return 6;
    boiledegg_research_pv_rt_destroy(handle); return 0;
}
