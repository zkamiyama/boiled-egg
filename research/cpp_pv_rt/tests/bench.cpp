#include "boiled_egg_pv_rt.h"
#include <algorithm>
#include <chrono>
#include <cmath>
#include <cstdint>
#include <iomanip>
#include <iostream>
#include <numeric>
#include <vector>

namespace {
const char* mode_name(std::uint32_t mode) noexcept { return mode == 0U ? "classic" : mode == 1U ? "locked" : "transient"; }
double quantile(std::vector<double> values, double q) { if (values.empty()) return 0.0; const std::size_t index = static_cast<std::size_t>(std::floor(q * static_cast<double>(values.size() - 1U))); std::nth_element(values.begin(), values.begin() + static_cast<std::ptrdiff_t>(index), values.end()); return values[index]; }
}

int main() {
    std::cout << "sample_rate,block_frames,mode,ratio,iterations,mean_us,p50_us,p95_us,p99_us,max_us,deadline_us,p99_deadline_ratio\n";
    for (std::uint32_t sample_rate : {44100U, 48000U, 96000U}) for (std::uint32_t block : {32U, 64U, 128U, 256U, 512U}) for (std::uint32_t mode : {0U, 1U, 2U}) for (float ratio : {0.5F, 1.0F, 2.0F}) {
        auto config = boiledegg_research_pv_rt_default_config(sample_rate, 2U, block); config.mode = mode; config.initial_time_ratio = ratio;
        boiledegg_research_pv_rt_result result{}; auto* handle = boiledegg_research_pv_rt_create(&config, &result); if (!handle) return 2;
        std::vector<float> left(block), right(block), out_left(block * 8U), out_right(block * 8U); const float* input[2] = {left.data(), right.data()}; float* output[2] = {out_left.data(), out_right.data()};
        std::vector<double> measurements; measurements.reserve(800U); std::uint64_t frame_cursor = 0;
        for (std::uint32_t iteration = 0; iteration < 900U; ++iteration) {
            for (std::uint32_t i = 0; i < block; ++i) { const float t = static_cast<float>(frame_cursor + i) / static_cast<float>(sample_rate); left[i] = 0.3F * std::sin(2.0F * 3.14159265358979323846F * 220.0F * t) + 0.13F * std::sin(2.0F * 3.14159265358979323846F * 1760.0F * t); right[i] = 0.97F * left[i] + 0.02F * std::sin(2.0F * 3.14159265358979323846F * 731.0F * t); if ((frame_cursor + i) % (sample_rate / 4U) == 0U) { left[i] += 0.75F; right[i] += 0.72F; } }
            const auto begin = std::chrono::steady_clock::now(); result = boiledegg_research_pv_rt_push(handle, input, block); while (boiledegg_research_pv_rt_available(handle) != 0U) (void)boiledegg_research_pv_rt_pull(handle, output, static_cast<std::uint32_t>(out_left.size())); const auto end = std::chrono::steady_clock::now();
            if (result != BOILEDEGG_RESEARCH_PV_RT_OK) return 3; if (iteration >= 100U) measurements.push_back(std::chrono::duration<double, std::micro>(end - begin).count()); frame_cursor += block;
        }
        const double mean = std::accumulate(measurements.begin(), measurements.end(), 0.0) / static_cast<double>(measurements.size()); const double p50 = quantile(measurements, 0.50), p95 = quantile(measurements, 0.95), p99 = quantile(measurements, 0.99); const double maximum = *std::max_element(measurements.begin(), measurements.end()); const double deadline = 1.0e6 * static_cast<double>(block) / static_cast<double>(sample_rate);
        std::cout << sample_rate << ',' << block << ',' << mode_name(mode) << ',' << ratio << ',' << measurements.size() << ',' << std::fixed << std::setprecision(3) << mean << ',' << p50 << ',' << p95 << ',' << p99 << ',' << maximum << ',' << deadline << ',' << p99 / deadline << '\n'; boiledegg_research_pv_rt_destroy(handle);
    }
    return 0;
}
