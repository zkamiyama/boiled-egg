#ifndef BOILED_EGG_FUZZY_MEDIAN_CHECKS_HPP
#define BOILED_EGG_FUZZY_MEDIAN_CHECKS_HPP

#include "../src/fuzzy_phase.hpp"
#include <algorithm>
#include <array>
#include <bit>
#include <cmath>
#include <cstdint>
#include <stdexcept>
#include <vector>

// Independent slow oracle: full sorts at every bin, exactly as before rolling
// order statistics. No FFT or listening metric can hide a classifier mismatch.
inline void fuzzy_median_regression() {
    using kernel = boiled_egg::research::detail::fuzzy_phase;
    constexpr std::size_t depth = kernel::history_size;
    std::uint64_t compared = 0;
    for (const auto config : {std::array<std::uint32_t, 2>{64, 384000},
                             {1024, 44100}, {2048, 96000}, {4096, 16000}}) {
        const auto fft = config[0], rate = config[1], bins = fft / 2U + 1U;
        const auto radius = std::clamp(static_cast<std::uint32_t>(std::lround(250.0 * fft / rate)), 2U, 31U);
        const auto length = 2U * radius + 1U;
        kernel f(bins, fft, rate);
        std::vector<float> linked(bins), history(static_cast<std::size_t>(bins) * depth);
        std::uint32_t rng = 0x12345678U;
        for (unsigned pass = 0; pass < 2; ++pass) {
            f.reset();
            std::size_t position = 0;
            for (unsigned frame = 0; frame < 53; ++frame) {
                for (std::uint32_t k = 0; k < bins; ++k) {
                    rng = 1664525U * rng + 1013904223U;
                    float v = static_cast<float>((rng >> 16U) % 17U); // frequent exact duplicates
                    if (frame < 11) v = pass ? 0.25F : 0.0F;
                    else if (frame < 22) v = static_cast<float>(k); // increasing
                    else if (frame < 33) v = static_cast<float>(bins - k); // decreasing
                    else if (frame % 3U == 0U) v *= 1.0e-20F;
                    else if (frame % 3U == 1U) v *= 1.0e12F;
                    linked[k] = v;
                }
                if (!frame)
                    for (std::size_t j = 0; j < depth; ++j)
                        std::copy(linked.begin(), linked.end(), history.begin() + j * bins);
                std::copy(linked.begin(), linked.end(), history.begin() + position * bins);
                position = (position + 1U) % depth;
                f.analyze(linked.data());
                for (std::uint32_t k = 0; k < bins; ++k) {
                    std::array<float, depth> horizontal{};
                    std::array<float, 63> vertical{};
                    for (std::size_t j = 0; j < depth; ++j) horizontal[j] = history[j * bins + k];
                    for (std::uint32_t j = 0; j < length; ++j) {
                        const auto index = std::clamp(static_cast<int>(k) + static_cast<int>(j) -
                            static_cast<int>(radius), 0, static_cast<int>(bins) - 1);
                        vertical[j] = linked[static_cast<std::uint32_t>(index)];
                    }
                    std::sort(horizontal.begin(), horizontal.end());
                    std::sort(vertical.begin(), vertical.begin() + length);
                    const auto expected = kernel::classify(horizontal[depth / 2U], vertical[length / 2U]);
                    const auto actual = f.bin(k);
                    for (const auto pair : {std::array<float, 2>{expected.tonal, actual.tonal},
                                           {expected.noise, actual.noise}, {expected.transient, actual.transient}}) {
                        if (std::bit_cast<std::uint32_t>(pair[0]) != std::bit_cast<std::uint32_t>(pair[1]))
                            throw std::runtime_error("rolling fuzzy median differs from full-sort oracle");
                        ++compared;
                    }
                }
            }
        }
    }
    if (compared != 1151160U) throw std::runtime_error("unexpected median regression coverage");
}
#endif
