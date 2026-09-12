#include "boiled_egg_pv_rt.h"
#include "fuzzy_median_checks.hpp"
#include "../src/fuzzy_phase.hpp"

#include <algorithm>
#include <array>
#include <cmath>
#include <cstdint>
#include <iostream>
#include <memory>
#include <numbers>
#include <stdexcept>
#include <vector>

namespace {
using kernel = boiled_egg::research::detail::fuzzy_phase;
using handle = std::unique_ptr<boiledegg_research_pv_rt_handle,
                              decltype(&boiledegg_research_pv_rt_destroy)>;
void require(bool ok, const char* message) { if (!ok) throw std::runtime_error(message); }
using audio = std::vector<std::vector<float>>;

audio source(std::uint32_t frames, std::uint32_t channels, bool silence = false) {
    audio x(channels, std::vector<float>(frames));
    std::uint32_t state = 1234567U;
    for (std::uint32_t i = 0; i < frames; ++i) {
        state = 1664525U * state + 1013904223U;
        const float noise = (static_cast<float>(state >> 8U) / 16777216.0F - 0.5F) * 0.08F;
        const float t = static_cast<float>(i) / 48000.0F;
        const float value = silence ? 0.0F : 0.2F * std::sin(2.0F * std::numbers::pi_v<float> * 220.0F * t)
            + noise + (i % 5000U < 2U ? 0.4F : 0.0F);
        for (std::uint32_t ch = 0; ch < channels; ++ch)
            x[ch][i] = value * (ch % 2U ? -0.5F : 1.0F);
    }
    return x;
}

audio render(const audio& input, std::uint32_t block, std::uint32_t mode,
             float pitch, float time, std::uint32_t formant, bool repeat = false) {
    auto c = boiledegg_research_pv_rt_default_config(48000U,
        static_cast<std::uint32_t>(input.size()), block);
    c.fft_size = 1024; c.analysis_hop = 256; c.mode = mode;
    c.initial_pitch_ratio = pitch; c.initial_time_ratio = time; c.formant_mode = formant;
    boiledegg_research_pv_rt_result result{};
    handle h(boiledegg_research_pv_rt_create(&c, &result), boiledegg_research_pv_rt_destroy);
    require(h && result == BOILEDEGG_RESEARCH_PV_RT_OK, "create");
    auto one = [&] {
        audio y(input.size()), buffer(input.size(), std::vector<float>(block * 8U));
        std::array<const float*, 8> in{};
        std::array<float*, 8> out{};
        for (std::size_t ch = 0; ch < input.size(); ++ch) out[ch] = buffer[ch].data();
        auto drain = [&] {
            while (boiledegg_research_pv_rt_available(h.get())) {
                const auto n = boiledegg_research_pv_rt_pull(h.get(), out.data(), block * 8U);
                require(n > 0, "pull progress");
                for (std::size_t ch = 0; ch < input.size(); ++ch)
                    y[ch].insert(y[ch].end(), buffer[ch].begin(), buffer[ch].begin() + n);
            }
        };
        for (std::size_t p = 0; p < input[0].size(); p += block) {
            const auto n = static_cast<std::uint32_t>(std::min<std::size_t>(block, input[0].size() - p));
            for (std::size_t ch = 0; ch < input.size(); ++ch) in[ch] = input[ch].data() + p;
            require(boiledegg_research_pv_rt_push(h.get(), in.data(), n) == BOILEDEGG_RESEARCH_PV_RT_OK, "push");
            drain();
        }
        require(boiledegg_research_pv_rt_flush(h.get()) == BOILEDEGG_RESEARCH_PV_RT_OK, "flush");
        drain();
        const auto expected = static_cast<std::size_t>(std::llround(static_cast<double>(input[0].size()) * time));
        for (const auto& channel : y) {
            require(channel.size() == expected, "exact duration");
            for (float v : channel) require(std::isfinite(v), "finite output");
        }
        return y;
    };
    auto output = one();
    if (repeat) {
        require(boiledegg_research_pv_rt_reset(h.get()) == BOILEDEGG_RESEARCH_PV_RT_OK, "reset");
        require(output == one(), "reset reproduces RNG, median history and phase state");
    }
    return output;
}

void membership_tests() {
    const auto tonal = kernel::classify(1.0F, 0.0F);
    const auto noise = kernel::classify(1.0F, 1.0F);
    const auto transient = kernel::classify(0.0F, 1.0F);
    require(tonal.tonal == 1.0F && tonal.noise == 0.0F, "tonal membership");
    require(noise.noise == 1.0F && noise.transient == 0.5F, "noise membership");
    require(transient.transient == 1.0F && transient.noise == 0.0F, "transient membership");
    require(kernel::classify(0.0F, 0.0F).noise == 0.0F, "silence guard");
    kernel f(33, 64, 48000);
    std::array<float, 33> magnitude{}; magnitude.fill(0.1F); magnitude[16] = 10.0F;
    for (int i = 0; i < 12; ++i) f.analyze(magnitude.data());
    require(f.bin(16).tonal > 0.98F, "horizontal tonal ridge");
    magnitude.fill(4.0F); f.analyze(magnitude.data());
    require(f.bin(5).transient > 0.95F, "causal transient rise");
    for (int i = 0; i < 12; ++i) f.analyze(magnitude.data());
    require(f.bin(5).noise > 0.99F, "stationary broad spectrum");
}

void linked_spectral_test() {
    constexpr std::uint32_t bins = 33, channels = 3;
    kernel f(bins, 64, 48000);
    std::array<float, bins> linked{}, prev_linked{}, omega{};
    std::array<std::uint32_t, bins> owners{};
    std::array<float, bins * channels> magnitude{}, phase{}, previous{}, output{};
    linked.fill(1.0F); prev_linked.fill(1.0F); magnitude.fill(1.0F);
    for (std::uint32_t k = 0; k < bins; ++k) { owners[k] = k; omega[k] = 0.03F * k; }
    for (int frame = 0; frame < 20; ++frame) {
        for (std::uint32_t ch = 0; ch < channels; ++ch)
            for (std::uint32_t k = 0; k < bins; ++k) {
                const auto i = ch * bins + k;
                phase[i] = kernel::wrap(0.31F * frame + 0.21F * ch + 0.17F * k);
                magnitude[i] = ch == static_cast<std::uint32_t>(frame % 3) ? 2.0F : 1.0F;
            }
        f.process(linked.data(), prev_linked.data(), magnitude.data(), phase.data(), previous.data(),
            owners.data(), omega.data(), channels, 16U, 32.0F, 2.0F, frame != 0, true, output.data());
        for (std::uint32_t ch = 1; ch < channels; ++ch)
            for (std::uint32_t k = 0; k < bins; ++k) {
                const float input_diff = kernel::wrap(phase[ch * bins + k] - phase[k]);
                const float output_diff = kernel::wrap(output[ch * bins + k] - output[k]);
                require(std::abs(kernel::wrap(input_diff - output_diff)) < 2.0e-6F,
                        "shared rotation preserves spectral channel phase, including RNG");
            }
        previous = phase;
    }
}
} // namespace

int main() {
    try {
        fuzzy_median_regression(); membership_tests(); linked_spectral_test();
        const auto x = source(12013, 2);
        for (auto mode : {BOILEDEGG_RESEARCH_PV_RT_FUZZY, BOILEDEGG_RESEARCH_PV_RT_FUZZY_NOISE}) {
            for (std::uint32_t formant : {0U, 1U, 2U}) {
                const auto a = render(x, 32U, mode, 1.4983071F, 1.0F, formant, true);
                const auto b = render(x, 257U, mode, 1.4983071F, 1.0F, formant);
                require(a == b, "bitwise input-block partition invariance");
                double error = 0.0, power = 0.0;
                for (std::size_t i = 0; i < a[0].size(); ++i) {
                    const double d = a[1][i] + 0.5 * a[0][i];
                    error += d*d; power += static_cast<double>(a[0][i])*a[0][i];
                }
                require(std::sqrt(error / (power + 1e-30)) < 1e-5, "antiphase stereo relation");
            }
            for (float time : {0.5F, 0.75F, 1.25F, 2.0F})
                for (float pitch : {0.5F, 1.0F, 2.0F}) (void)render(x, 64, mode, pitch, time, 1);
            for (std::uint32_t frames : {0U, 1U, 31U, 513U})
                (void)render(source(frames, 1), 31, mode, 1.5F, 1.0F, 2, true);
            const auto silent = render(source(1237, 8, true), 64, mode, 2.0F, 1.0F, 1, true);
            for (const auto& ch : silent) for (float v : ch) require(v == 0.0F, "silence stays silent");
            auto silent_left = x; std::fill(silent_left[0].begin(), silent_left[0].end(), 0.0F);
            const auto right_only = render(silent_left, 64, mode, 1.5F, 1.0F, 1);
            for (float v : right_only[0]) require(v == 0.0F, "no leakage into silent channel");
            double energy = 0; for (float v : right_only[1]) energy += v*v;
            require(energy > 1, "silent first channel is not a phase reference failure");
            const auto identity = render(x, 64, mode, 1.0F, 1.0F, 0);
            double e=0,p=0;
            for(std::size_t i=0;i<x[0].size();++i){double d=identity[0][i]-x[0][i];e+=d*d;p+=x[0][i]*x[0][i];}
            require(std::sqrt(e/p)<1e-5, "identity reconstruction");
        }
        auto config=boiledegg_research_pv_rt_default_config(48000,1,64);
        config.mode=5U;
        boiledegg_research_pv_rt_result result{};
        handle h(boiledegg_research_pv_rt_create(&config,&result),boiledegg_research_pv_rt_destroy);
        require(!h && result==BOILEDEGG_RESEARCH_PV_RT_INVALID_CONFIG,"invalid mode rejected");
        std::cout << "fuzzy classifier, phase linkage, reset, block, duration and identity tests passed\n";
    } catch (const std::exception& e) { std::cerr << e.what() << '\n'; return 1; }
}
