#ifndef BOILED_EGG_RESEARCH_PV_RT_HPP
#define BOILED_EGG_RESEARCH_PV_RT_HPP

#include "boiled_egg_pv_rt.h"
#include <stdexcept>
#include <utility>

namespace boiled_egg::research {
class pv_rt_engine {
public:
    explicit pv_rt_engine(const boiledegg_research_pv_rt_config& config) {
        boiledegg_research_pv_rt_result result{};
        handle_ = boiledegg_research_pv_rt_create(&config, &result);
        if (!handle_) throw std::runtime_error(boiledegg_research_pv_rt_result_string(result));
    }
    pv_rt_engine(uint32_t sample_rate, uint32_t channels, uint32_t max_block_frames)
        : pv_rt_engine(boiledegg_research_pv_rt_default_config(sample_rate, channels, max_block_frames)) {}
    ~pv_rt_engine() { boiledegg_research_pv_rt_destroy(handle_); }
    pv_rt_engine(const pv_rt_engine&) = delete;
    pv_rt_engine& operator=(const pv_rt_engine&) = delete;
    pv_rt_engine(pv_rt_engine&& other) noexcept : handle_(std::exchange(other.handle_, nullptr)) {}
    pv_rt_engine& operator=(pv_rt_engine&& other) noexcept {
        if (this != &other) {
            boiledegg_research_pv_rt_destroy(handle_);
            handle_ = std::exchange(other.handle_, nullptr);
        }
        return *this;
    }
    void set_time_ratio(float ratio) { check(boiledegg_research_pv_rt_set_time_ratio(handle_, ratio)); }
    void push(const float* const* input, uint32_t frames) { check(boiledegg_research_pv_rt_push(handle_, input, frames)); }
    uint32_t pull(float* const* output, uint32_t frames) noexcept { return boiledegg_research_pv_rt_pull(handle_, output, frames); }
    void flush() { check(boiledegg_research_pv_rt_flush(handle_)); }
    void reset() { check(boiledegg_research_pv_rt_reset(handle_)); }
    [[nodiscard]] uint32_t available() const noexcept { return boiledegg_research_pv_rt_available(handle_); }
    [[nodiscard]] uint32_t latency_frames() const noexcept { return boiledegg_research_pv_rt_latency_frames(handle_); }
private:
    static void check(boiledegg_research_pv_rt_result result) {
        if (result != BOILEDEGG_RESEARCH_PV_RT_OK) throw std::runtime_error(boiledegg_research_pv_rt_result_string(result));
    }
    boiledegg_research_pv_rt_handle* handle_{};
};
}
#endif
