#include "boiled_egg_multires_rt.h"

#include <algorithm>
#include <cmath>
#include <cstdint>
#include <vector>

int main() {
    constexpr std::uint32_t sample_rate = 48000U;
    constexpr std::uint32_t block = 128U;
    constexpr std::uint32_t input_frames = sample_rate * 2U;
    auto config = boiledegg_research_multires_rt_default_config(sample_rate, 2U, block);
    config.initial_pitch_ratio = 1.4983071F;
    config.formant_mode = BOILEDEGG_RESEARCH_PV_RT_FORMANT_HARMONIC;

    auto invalid = config;
    invalid.fir_taps = 128U;
    boiledegg_research_pv_rt_result result{};
    if (boiledegg_research_multires_rt_create(&invalid, &result) != nullptr ||
        result != BOILEDEGG_RESEARCH_PV_RT_INVALID_CONFIG) return 1;

    auto* handle = boiledegg_research_multires_rt_create(&config, &result);
    if (handle == nullptr || result != BOILEDEGG_RESEARCH_PV_RT_OK) return 2;
    if (boiledegg_research_multires_rt_latency_frames(handle) <= 1024U) return 3;

    std::vector<float> left(block), right(block), out_left(block * 16U), out_right(block * 16U);
    const float* input[2] = {left.data(), right.data()};
    float* output[2] = {out_left.data(), out_right.data()};
    std::vector<float> rendered_left, rendered_right;
    rendered_left.reserve(input_frames);
    rendered_right.reserve(input_frames);

    const auto drain = [&]() {
        while (boiledegg_research_multires_rt_available(handle) != 0U) {
            const auto count = boiledegg_research_multires_rt_pull(handle, output, static_cast<std::uint32_t>(out_left.size()));
            for (std::uint32_t i = 0U; i < count; ++i) {
                rendered_left.push_back(out_left[i]);
                rendered_right.push_back(out_right[i]);
            }
        }
    };

    for (std::uint32_t position = 0U; position < input_frames; position += block) {
        const auto count = std::min(block, input_frames - position);
        for (std::uint32_t i = 0U; i < count; ++i) {
            const float t = static_cast<float>(position + i) / static_cast<float>(sample_rate);
            float sample = 0.20F * std::sin(2.0F * 3.14159265358979323846F * 220.0F * t)
                + 0.12F * std::sin(2.0F * 3.14159265358979323846F * 1100.0F * t)
                + 0.05F * std::sin(2.0F * 3.14159265358979323846F * 7000.0F * t);
            if (((position + i) % 12000U) == 0U) sample += 0.25F;
            left[i] = sample;
            right[i] = 0.6F * sample;
        }
        result = boiledegg_research_multires_rt_push(handle, input, count);
        if (result != BOILEDEGG_RESEARCH_PV_RT_OK) return 4;
        drain();
    }
    drain();
    result = boiledegg_research_multires_rt_flush(handle);
    if (result != BOILEDEGG_RESEARCH_PV_RT_OK) return 5;
    drain();

    if (rendered_left.size() != input_frames || rendered_right.size() != input_frames) return 6;
    if (boiledegg_research_multires_rt_input_frames(handle) != input_frames) return 7;
    if (boiledegg_research_multires_rt_output_frames(handle) != input_frames) return 8;

    double error_energy = 0.0;
    double signal_energy = 1.0e-30;
    for (std::size_t i = 0U; i < rendered_left.size(); ++i) {
        if (!std::isfinite(rendered_left[i]) || !std::isfinite(rendered_right[i])) return 9;
        const double residual = static_cast<double>(rendered_right[i]) - 0.6 * static_cast<double>(rendered_left[i]);
        error_energy += residual * residual;
        signal_energy += static_cast<double>(rendered_left[i]) * rendered_left[i];
    }
    const double relative = std::sqrt(error_energy / signal_energy);
    if (relative > 1.0e-4) return 10;

    if (boiledegg_research_multires_rt_reset(handle) != BOILEDEGG_RESEARCH_PV_RT_OK) return 11;
    if (boiledegg_research_multires_rt_set_time_ratio(handle, 1.25F) != BOILEDEGG_RESEARCH_PV_RT_OK) return 12;
    if (boiledegg_research_multires_rt_set_pitch_ratio(handle, 0.8F) != BOILEDEGG_RESEARCH_PV_RT_OK) return 13;
    if (std::abs(boiledegg_research_multires_rt_get_time_ratio(handle) - 1.25F) > 1.0e-6F) return 14;
    if (std::abs(boiledegg_research_multires_rt_get_pitch_ratio(handle) - 0.8F) > 1.0e-6F) return 15;

    boiledegg_research_multires_rt_destroy(handle);
    return 0;
}
