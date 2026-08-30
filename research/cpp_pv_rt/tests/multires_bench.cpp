#include "boiled_egg_multires_rt.h"

#include <algorithm>
#include <chrono>
#include <cmath>
#include <cstdint>
#include <iomanip>
#include <iostream>
#include <numeric>
#include <vector>

namespace {
double quantile(std::vector<double> values, double q) {
    const auto index = static_cast<std::size_t>(std::floor(q * static_cast<double>(values.size() - 1U)));
    std::nth_element(values.begin(), values.begin() + static_cast<std::ptrdiff_t>(index), values.end());
    return values[index];
}
}

int main() {
    std::cout << "sample_rate,block,pitch_ratio,mean_us,p99_us,deadline_us,p99_deadline_ratio\n";
    for (const std::uint32_t sample_rate : {48000U, 96000U}) {
        for (const std::uint32_t block : {32U, 64U, 128U, 256U}) {
            for (const float pitch : {0.6674199F, 1.4983071F}) {
                auto config = boiledegg_research_multires_rt_default_config(sample_rate, 1U, block);
                config.initial_pitch_ratio = pitch;
                config.formant_mode = BOILEDEGG_RESEARCH_PV_RT_FORMANT_HARMONIC;
                boiledegg_research_pv_rt_result result{};
                auto* handle = boiledegg_research_multires_rt_create(&config, &result);
                if (handle == nullptr) return 2;

                std::vector<float> input(block), output(block * 32U);
                const float* in[1] = {input.data()};
                float* out[1] = {output.data()};
                std::vector<double> times;
                times.reserve(1400U);
                std::uint64_t position = 0U;

                for (std::uint32_t iteration = 0U; iteration < 1600U; ++iteration) {
                    for (std::uint32_t i = 0U; i < block; ++i) {
                        const float t = static_cast<float>(position + i) / static_cast<float>(sample_rate);
                        input[i] = 0.25F * std::sin(2.0F * 3.14159265358979323846F * 120.0F * t)
                            + 0.18F * std::sin(2.0F * 3.14159265358979323846F * 720.0F * t)
                            + 0.10F * std::sin(2.0F * 3.14159265358979323846F * 6200.0F * t);
                    }
                    const auto begin = std::chrono::steady_clock::now();
                    result = boiledegg_research_multires_rt_push(handle, in, block);
                    while (boiledegg_research_multires_rt_available(handle) != 0U) {
                        boiledegg_research_multires_rt_pull(handle, out, static_cast<std::uint32_t>(output.size()));
                    }
                    const auto end = std::chrono::steady_clock::now();
                    if (result != BOILEDEGG_RESEARCH_PV_RT_OK) return 3;
                    if (iteration >= 200U) {
                        times.push_back(std::chrono::duration<double, std::micro>(end - begin).count());
                    }
                    position += block;
                }

                const double mean = std::accumulate(times.begin(), times.end(), 0.0) / static_cast<double>(times.size());
                const double p99 = quantile(times, 0.99);
                const double deadline = 1.0e6 * static_cast<double>(block) / static_cast<double>(sample_rate);
                std::cout << sample_rate << ',' << block << ',' << pitch << ','
                          << std::fixed << std::setprecision(3) << mean << ',' << p99 << ','
                          << deadline << ',' << (p99 / deadline) << '\n';
                boiledegg_research_multires_rt_destroy(handle);
            }
        }
    }
}
