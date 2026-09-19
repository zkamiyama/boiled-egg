#pragma once
// Finite-file research API only. Not installed or exported as SDK ABI.
#include <cstddef>
#include <cstdint>
#include <span>
#include <vector>

namespace boiled_egg::offline_research {
struct Config {
    std::uint32_t sample_rate{48000};
    double time_ratio{1.0}; // output duration / input duration
    double pitch_ratio{1.0};
    unsigned iterations{0}; // Explicitly supported: 0, 8, 32
    std::size_t memory_limit_bytes{512u * 1024u * 1024u};
};
struct Result {
    std::vector<float> audio;
    std::vector<double> magnitude_residual; // intermediate stretched signal, NOT quality
    std::size_t estimated_work_bytes{};
    std::size_t fft_size{}, hop{}, intermediate_frames{};
};
Result render(std::span<const float> input, const Config& config);
}
