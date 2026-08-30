#include "fft.hpp"
#include <cmath>
#include <numbers>
#include <stdexcept>

namespace boiled_egg::research::detail {
namespace {
bool is_power_of_two(std::size_t value) noexcept { return value >= 2 && (value & (value - 1)) == 0; }
}
fft_plan::fft_plan(std::size_t size) : size_(size), bit_reverse_(size), roots_(size / 2) {
    if (!is_power_of_two(size)) throw std::invalid_argument("FFT size must be a power of two");
    unsigned bits = 0;
    for (std::size_t n = size; n > 1; n >>= 1) ++bits;
    for (std::size_t i = 0; i < size; ++i) {
        std::size_t x = i, reversed = 0;
        for (unsigned b = 0; b < bits; ++b) { reversed = (reversed << 1) | (x & 1U); x >>= 1; }
        bit_reverse_[i] = reversed;
    }
    for (std::size_t k = 0; k < roots_.size(); ++k) {
        const float angle = -2.0F * std::numbers::pi_v<float> * static_cast<float>(k) / static_cast<float>(size_);
        roots_[k] = {std::cos(angle), std::sin(angle)};
    }
}
void fft_plan::forward(std::complex<float>* data) const noexcept { transform(data, false); }
void fft_plan::inverse(std::complex<float>* data) const noexcept { transform(data, true); }
void fft_plan::transform(std::complex<float>* data, bool inverse_flag) const noexcept {
    for (std::size_t i = 0; i < size_; ++i) {
        const std::size_t j = bit_reverse_[i];
        if (j > i) { const auto tmp = data[i]; data[i] = data[j]; data[j] = tmp; }
    }
    for (std::size_t length = 2; length <= size_; length <<= 1) {
        const std::size_t half = length / 2;
        const std::size_t root_step = size_ / length;
        for (std::size_t base = 0; base < size_; base += length) {
            for (std::size_t j = 0; j < half; ++j) {
                std::complex<float> root = roots_[j * root_step];
                if (inverse_flag) root = std::conj(root);
                const auto even = data[base + j];
                const auto odd = data[base + j + half] * root;
                data[base + j] = even + odd;
                data[base + j + half] = even - odd;
            }
        }
    }
    if (inverse_flag) {
        const float scale = 1.0F / static_cast<float>(size_);
        for (std::size_t i = 0; i < size_; ++i) data[i] *= scale;
    }
}
}
