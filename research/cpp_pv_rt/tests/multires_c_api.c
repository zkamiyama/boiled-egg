#include "boiled_egg_multires_rt.h"

#include <math.h>
#include <stdint.h>

int main(void) {
    enum { block = 64, frames = 4096 };
    boiledegg_research_multires_rt_config config = boiledegg_research_multires_rt_default_config(48000U, 1U, block);
    config.initial_pitch_ratio = 1.25F;
    config.formant_mode = BOILEDEGG_RESEARCH_PV_RT_FORMANT_HARMONIC;
    if (config.crossover_hz != 6500.0F || config.fir_taps != 129U) return 1;
    boiledegg_research_pv_rt_result result = BOILEDEGG_RESEARCH_PV_RT_INTERNAL_ERROR;
    boiledegg_research_multires_rt_handle* handle = boiledegg_research_multires_rt_create(&config, &result);
    if (handle == 0 || result != BOILEDEGG_RESEARCH_PV_RT_OK) return 2;

    float input_buffer[block];
    float output_buffer[block * 32];
    const float* input[1] = {input_buffer};
    float* output[1] = {output_buffer};
    uint64_t pulled = 0U;
    for (uint32_t position = 0U; position < frames; position += block) {
        const uint32_t count = position + block <= frames ? block : frames - position;
        for (uint32_t i = 0U; i < count; ++i) {
            input_buffer[i] = 0.2F * sinf(2.0F * 3.14159265358979323846F * 440.0F * (float)(position + i) / 48000.0F);
        }
        if (boiledegg_research_multires_rt_push(handle, input, count) != BOILEDEGG_RESEARCH_PV_RT_OK) return 3;
        while (boiledegg_research_multires_rt_available(handle) != 0U) {
            pulled += boiledegg_research_multires_rt_pull(handle, output, block * 32U);
        }
    }
    if (boiledegg_research_multires_rt_flush(handle) != BOILEDEGG_RESEARCH_PV_RT_OK) return 4;
    while (boiledegg_research_multires_rt_available(handle) != 0U) {
        pulled += boiledegg_research_multires_rt_pull(handle, output, block * 32U);
    }
    if (pulled != frames) return 5;
    if (boiledegg_research_multires_rt_output_frames(handle) != frames) return 6;
    boiledegg_research_multires_rt_destroy(handle);
    return 0;
}
