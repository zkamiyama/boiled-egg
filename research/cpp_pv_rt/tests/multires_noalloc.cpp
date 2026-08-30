#include "boiled_egg_multires_rt.h"

#include <atomic>
#include <cmath>
#include <cstdlib>
#include <new>
#include <vector>

static std::atomic<bool> count_enabled{false};
static std::atomic<std::uint64_t> allocations{0};

void* operator new(std::size_t size) {
    if (count_enabled.load(std::memory_order_relaxed)) allocations.fetch_add(1U, std::memory_order_relaxed);
    if (void* pointer = std::malloc(size)) return pointer;
    throw std::bad_alloc();
}
void operator delete(void* pointer) noexcept { std::free(pointer); }
void operator delete(void* pointer, std::size_t) noexcept { std::free(pointer); }
void* operator new[](std::size_t size) { return ::operator new(size); }
void operator delete[](void* pointer) noexcept { ::operator delete(pointer); }
void operator delete[](void* pointer, std::size_t) noexcept { ::operator delete(pointer); }

int main() {
    constexpr std::uint32_t block = 128U;
    auto config = boiledegg_research_multires_rt_default_config(48000U, 2U, block);
    config.initial_pitch_ratio = 1.35F;
    config.formant_mode = BOILEDEGG_RESEARCH_PV_RT_FORMANT_HARMONIC;
    boiledegg_research_pv_rt_result result{};
    auto* handle = boiledegg_research_multires_rt_create(&config, &result);
    if (handle == nullptr) return 1;

    std::vector<float> a(block), b(block), oa(block * 16U), ob(block * 16U);
    const float* input[2] = {a.data(), b.data()};
    float* output[2] = {oa.data(), ob.data()};
    for (std::uint32_t i = 0U; i < block; ++i) {
        a[i] = std::sin(0.03F * static_cast<float>(i));
        b[i] = 0.6F * a[i];
    }

    for (int warm = 0; warm < 48; ++warm) {
        if (boiledegg_research_multires_rt_push(handle, input, block) != BOILEDEGG_RESEARCH_PV_RT_OK) return 2;
        while (boiledegg_research_multires_rt_available(handle) != 0U) {
            boiledegg_research_multires_rt_pull(handle, output, static_cast<std::uint32_t>(oa.size()));
        }
    }

    allocations.store(0U, std::memory_order_relaxed);
    count_enabled.store(true, std::memory_order_relaxed);
    for (int iteration = 0; iteration < 128; ++iteration) {
        if (iteration % 17 == 0 && boiledegg_research_multires_rt_set_time_ratio(
                handle, 0.75F + 0.01F * static_cast<float>(iteration % 50)) != BOILEDEGG_RESEARCH_PV_RT_OK) return 3;
        if (iteration % 23 == 0 && boiledegg_research_multires_rt_set_pitch_ratio(
                handle, 0.8F + 0.02F * static_cast<float>(iteration % 30)) != BOILEDEGG_RESEARCH_PV_RT_OK) return 4;
        if (boiledegg_research_multires_rt_push(handle, input, block) != BOILEDEGG_RESEARCH_PV_RT_OK) return 5;
        while (boiledegg_research_multires_rt_available(handle) != 0U) {
            boiledegg_research_multires_rt_pull(handle, output, static_cast<std::uint32_t>(oa.size()));
        }
    }
    count_enabled.store(false, std::memory_order_relaxed);
    const auto count = allocations.load(std::memory_order_relaxed);
    boiledegg_research_multires_rt_destroy(handle);
    return count == 0U ? 0 : 6;
}
