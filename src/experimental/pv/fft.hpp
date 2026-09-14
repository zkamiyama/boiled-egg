#ifndef BOILED_EGG_RESEARCH_PV_RT_FFT_HPP
#define BOILED_EGG_RESEARCH_PV_RT_FFT_HPP
#include <complex>
#include <cstddef>
#include <vector>

namespace boiled_egg::research::detail {
class fft_plan {
public:
    explicit fft_plan(std::size_t size);
    [[nodiscard]] std::size_t size() const noexcept { return size_; }
    void forward(std::complex<float>* data) const noexcept;
    void inverse(std::complex<float>* data) const noexcept;
    // Caller-owned cursor. A plan can service distinct cursors independently.
    struct cursor {
        std::complex<float>* data{};
        std::size_t position{}, length{2}, base{}, column{};
        unsigned stage{};
        bool inverse{}, simd{};
    };
    void start(cursor& state, std::complex<float>* data, bool inverse, bool simd) const noexcept;
    // At most budget permutations/butterflies/scales. Zero budget changes nothing.
    // Returns true while work remains. Only finite-input DSP is qualified.
    bool advance(cursor& state, std::size_t budget) const noexcept;
    static bool simd_available() noexcept;
private:
    void transform(std::complex<float>* data, bool inverse) const noexcept;
    std::size_t size_{};
    std::vector<std::size_t> bit_reverse_;
    std::vector<std::complex<float>> roots_, stage_roots_;
};
}
#endif
