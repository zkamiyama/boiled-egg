#ifndef BOILED_EGG_RESEARCH_MULTIRES_RT_HPP
#define BOILED_EGG_RESEARCH_MULTIRES_RT_HPP

#include "boiled_egg_multires_rt.h"

#include "boiled_egg_research_features.h"
#include "boiled_egg_research_execution.h"
#include <cstdint>
#include <stdexcept>
#include <utility>

namespace boiled_egg::research {

class multires_rt_engine {
public:
    multires_rt_engine(const boiledegg_research_multires_rt_config& config,
                const boiledegg_research_features& features, const boiledegg_research_execution& execution) {
        boiledegg_research_pv_rt_result result{};
        handle_ = boiledegg_research_multires_rt_create_exec(&config, &features, &execution, &result);
        if (!handle_) throw std::runtime_error(boiledegg_research_pv_rt_result_string(result));
    }
    [[nodiscard]] boiledegg_research_execution_stats execution_stats() const noexcept {
        boiledegg_research_execution_stats stats{sizeof(stats),0,0,0,0};
        (void)boiledegg_research_multires_rt_execution_stats(handle_, &stats); return stats;
    }
    multires_rt_engine(const boiledegg_research_multires_rt_config& config,
                const boiledegg_research_features& features) {
        boiledegg_research_pv_rt_result result{};
        handle_ = boiledegg_research_multires_rt_create_ex(&config, &features, &result);
        if (!handle_) throw std::runtime_error(boiledegg_research_pv_rt_result_string(result));
    }
    void set_formant_ratio(float ratio) { check(boiledegg_research_multires_rt_set_formant_ratio(handle_, ratio)); }
    [[nodiscard]] float formant_ratio() const noexcept { return boiledegg_research_multires_rt_get_formant_ratio(handle_); }
    explicit multires_rt_engine(const boiledegg_research_multires_rt_config& config) {
        boiledegg_research_pv_rt_result result{};
        handle_ = boiledegg_research_multires_rt_create(&config, &result);
        if (handle_ == nullptr) throw std::runtime_error(boiledegg_research_pv_rt_result_string(result));
    }
    multires_rt_engine(std::uint32_t sample_rate, std::uint32_t channels, std::uint32_t max_block_frames)
        : multires_rt_engine(boiledegg_research_multires_rt_default_config(sample_rate, channels, max_block_frames)) {}
    ~multires_rt_engine() { boiledegg_research_multires_rt_destroy(handle_); }
    multires_rt_engine(const multires_rt_engine&) = delete;
    multires_rt_engine& operator=(const multires_rt_engine&) = delete;
    multires_rt_engine(multires_rt_engine&& other) noexcept : handle_(std::exchange(other.handle_, nullptr)) {}
    multires_rt_engine& operator=(multires_rt_engine&& other) noexcept {
        if (this != &other) {
            boiledegg_research_multires_rt_destroy(handle_);
            handle_ = std::exchange(other.handle_, nullptr);
        }
        return *this;
    }
    void set_time_ratio(float ratio) { check(boiledegg_research_multires_rt_set_time_ratio(handle_, ratio)); }
    void set_pitch_ratio(float ratio) { check(boiledegg_research_multires_rt_set_pitch_ratio(handle_, ratio)); }
    [[nodiscard]] float time_ratio() const noexcept { return boiledegg_research_multires_rt_get_time_ratio(handle_); }
    [[nodiscard]] float pitch_ratio() const noexcept { return boiledegg_research_multires_rt_get_pitch_ratio(handle_); }
    void push(const float* const* input, std::uint32_t frames) { check(boiledegg_research_multires_rt_push(handle_, input, frames)); }
    std::uint32_t pull(float* const* output, std::uint32_t frames) noexcept { return boiledegg_research_multires_rt_pull(handle_, output, frames); }
    void flush() { check(boiledegg_research_multires_rt_flush(handle_)); }
    void reset() { check(boiledegg_research_multires_rt_reset(handle_)); }
    [[nodiscard]] std::uint32_t available() const noexcept { return boiledegg_research_multires_rt_available(handle_); }
    [[nodiscard]] std::uint32_t latency_frames() const noexcept { return boiledegg_research_multires_rt_latency_frames(handle_); }
private:
    static void check(boiledegg_research_pv_rt_result result) {
        if (result != BOILEDEGG_RESEARCH_PV_RT_OK) throw std::runtime_error(boiledegg_research_pv_rt_result_string(result));
    }
    boiledegg_research_multires_rt_handle* handle_{};
};

} // namespace boiled_egg::research
#endif
