#ifndef BOILED_EGG_RESEARCH_PV_RT_HPP
#define BOILED_EGG_RESEARCH_PV_RT_HPP

#include "boiled_egg_pv_rt.h"
#include "boiled_egg_research_features.h"
#include <stdexcept>
#include <utility>

namespace boiled_egg::research {

enum class pv_rt_quality_profile : uint32_t {
    general = BOILEDEGG_RESEARCH_PV_RT_PROFILE_GENERAL,
    transient = BOILEDEGG_RESEARCH_PV_RT_PROFILE_TRANSIENT,
};

inline boiledegg_research_pv_rt_config pv_rt_profile_config(
    uint32_t sample_rate,
    uint32_t channels,
    uint32_t max_block_frames,
    pv_rt_quality_profile profile) {
    auto config = boiledegg_research_pv_rt_default_config(sample_rate, channels, max_block_frames);
    const auto result = boiledegg_research_pv_rt_configure_quality_profile(
        &config, static_cast<uint32_t>(profile));
    if (result != BOILEDEGG_RESEARCH_PV_RT_OK) {
        throw std::runtime_error(boiledegg_research_pv_rt_result_string(result));
    }
    return config;
}

class pv_rt_engine {
public:
    pv_rt_engine(const boiledegg_research_pv_rt_config& config,
                const boiledegg_research_features& features) {
        boiledegg_research_pv_rt_result result{};
        handle_ = boiledegg_research_pv_rt_create_ex(&config, &features, &result);
        if (!handle_) throw std::runtime_error(boiledegg_research_pv_rt_result_string(result));
    }
    void set_formant_ratio(float ratio) { check(boiledegg_research_pv_rt_set_formant_ratio(handle_, ratio)); }
    [[nodiscard]] float formant_ratio() const noexcept { return boiledegg_research_pv_rt_get_formant_ratio(handle_); }
    explicit pv_rt_engine(const boiledegg_research_pv_rt_config& config) {
        boiledegg_research_pv_rt_result result{};
        handle_ = boiledegg_research_pv_rt_create(&config, &result);
        if (!handle_) throw std::runtime_error(boiledegg_research_pv_rt_result_string(result));
    }
    pv_rt_engine(uint32_t sample_rate, uint32_t channels, uint32_t max_block_frames)
        : pv_rt_engine(boiledegg_research_pv_rt_default_config(sample_rate, channels, max_block_frames)) {}
    pv_rt_engine(
        uint32_t sample_rate,
        uint32_t channels,
        uint32_t max_block_frames,
        pv_rt_quality_profile profile)
        : pv_rt_engine(pv_rt_profile_config(sample_rate, channels, max_block_frames, profile)) {}
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
    void set_pitch_ratio(float ratio) { check(boiledegg_research_pv_rt_set_pitch_ratio(handle_, ratio)); }
    [[nodiscard]] float time_ratio() const noexcept { return boiledegg_research_pv_rt_get_time_ratio(handle_); }
    [[nodiscard]] float pitch_ratio() const noexcept { return boiledegg_research_pv_rt_get_pitch_ratio(handle_); }
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
