#include "boiled_egg_multires_rt.h"

#include <algorithm>
#include <array>
#include <atomic>
#include <cmath>
#include <cstdlib>
#include <iostream>
#include <new>
#include <string_view>
#include <vector>

static std::atomic<bool> track{false};
static std::atomic<unsigned> allocations{0};
void* operator new(std::size_t size) {
    if (track.load(std::memory_order_relaxed)) ++allocations;
    if (void* p = std::malloc(size ? size : 1)) return p;
    throw std::bad_alloc();
}
void operator delete(void* p) noexcept { std::free(p); }
void operator delete(void* p, std::size_t) noexcept { std::free(p); }
void* operator new[](std::size_t size) { return ::operator new(size); }
void operator delete[](void* p) noexcept { ::operator delete(p); }
void operator delete[](void* p, std::size_t) noexcept { ::operator delete(p); }

int check(float time, float pitch, bool dynamic) {
    constexpr unsigned sr = 48000, block = 64, frames = 32768;
    auto c = boiledegg_research_multires_rt_default_config(sr, 2, block);
    c.initial_time_ratio = time;
    c.initial_pitch_ratio = pitch;
    c.formant_mode = BOILEDEGG_RESEARCH_PV_RT_FORMANT_HARMONIC;
    boiledegg_research_pv_rt_result status{};
    auto* h = boiledegg_research_multires_rt_create(&c, &status);
    if (!h || status != BOILEDEGG_RESEARCH_PV_RT_OK) return 1;
    std::array<float, block> left{}, right{};
    std::array<float, block * 32> ol{}, oright{};
    const float* in[] = {left.data(), right.data()};
    float* out[] = {ol.data(), oright.data()};
    unsigned long long count = 0;
    double energy = 1e-30, error = 0, expected = 0;
    float peak = 0;
    bool finite = true;
    auto drain = [&]() {
        while (boiledegg_research_multires_rt_available(h)) {
            auto n = boiledegg_research_multires_rt_pull(h, out, static_cast<unsigned>(ol.size()));
            count += n;
            for (unsigned i = 0; i < n; ++i) {
                finite = finite && std::isfinite(ol[i]) && std::isfinite(oright[i]);
                peak = std::max(peak, std::abs(ol[i]));
                const double e = oright[i] - .375 * ol[i];
                energy += static_cast<double>(ol[i]) * ol[i];
                error += e * e;
            }
        }
    };
    allocations = 0;
    track = true;
    for (unsigned p = 0; p < frames; p += block) {
        if (dynamic && p == frames / 2) {
            time = .75F;
            if (boiledegg_research_multires_rt_set_time_ratio(h, time) != BOILEDEGG_RESEARCH_PV_RT_OK ||
                boiledegg_research_multires_rt_set_pitch_ratio(h, 1.625F) != BOILEDEGG_RESEARCH_PV_RT_OK) {
                track = false; boiledegg_research_multires_rt_destroy(h); return 2;
            }
        }
        for (unsigned i = 0; i < block; ++i) {
            const double t = static_cast<double>(p+i) / sr;
            float x = static_cast<float>(.16*std::sin(6.283185307179586*220*t)
                + .09*std::sin(6.283185307179586*6300*t)
                + .06*std::sin(6.283185307179586*9700*t));
            if ((p+i)%3001 == 0) x += .25F;
            left[i] = x; right[i] = .375F*x;
        }
        expected += block * static_cast<double>(time);
        status = boiledegg_research_multires_rt_push(h, in, block);
        if (status != BOILEDEGG_RESEARCH_PV_RT_OK) {
            track = false; boiledegg_research_multires_rt_destroy(h); return 3;
        }
        drain();
    }
    status = boiledegg_research_multires_rt_flush(h);
    drain();
    track = false;
    const auto allocated = allocations.load();
    const bool exact = count == static_cast<unsigned long long>(std::llround(expected));
    const double linked = std::sqrt(error / energy);
    boiledegg_research_multires_rt_destroy(h);
    std::cout << "time=" << c.initial_time_ratio << " pitch=" << pitch << " dynamic=" << dynamic
              << " peak=" << peak << " linked=" << linked << " alloc=" << allocated
              << " frames=" << count << " expected=" << expected << '\n';
    if (status != BOILEDEGG_RESEARCH_PV_RT_OK || !finite || !exact) return 4;
    if (allocated || linked > 1e-4 || peak > 2.0F) return 5;
    return 0;
}

int main(int argc, char** argv) {
    // These extra diagnostics intentionally remain separate from the constant-
    // control overlap regression. They expose existing streaming limitations.
    if (argc > 1 && std::string_view(argv[1]) == "dynamic") return check(3.75F, .875F, true);
    if (argc > 1 && std::string_view(argv[1]) == "extended") return check(4.0F, 4.0F, false);
    for (const auto& pair : {std::array{4.0F, 1.0F}, std::array{1.0F, 4.0F},
                             std::array{2.0F, 2.0F},
                             std::array{.5F, 2.0F}, std::array{1.0F, 1.0F}}) {
        const int result = check(pair[0], pair[1], false);
        if (result) return result;
    }
    return 0;
}
