#pragma once

#include <boiled_egg/boiled_egg.h>
#include <boiled_egg/backend.h>
#include <boiled_egg/automation.h>
#include <span>
#include <stdexcept>
#include <utility>

namespace boiled_egg {

class error : public std::runtime_error {
public:
    explicit error(boiledegg_result r)
        : std::runtime_error(boiledegg_result_string(r)), result_(r) {}
    boiledegg_result result() const noexcept { return result_; }
private:
    boiledegg_result result_;
};

struct parameter_event : boiledegg_parameter_event {
    static parameter_event time_ratio(uint32_t sample_offset, float ratio) noexcept {
        return parameter_event{sizeof(boiledegg_parameter_event), sample_offset,
                               BOILEDEGG_PARAMETER_TIME_RATIO, ratio};
    }
    static parameter_event pitch_ratio(uint32_t sample_offset, float ratio) noexcept {
        return parameter_event{sizeof(boiledegg_parameter_event), sample_offset,
                               BOILEDEGG_PARAMETER_PITCH_RATIO, ratio};
    }
    static parameter_event pitch_semitones(uint32_t sample_offset, float semitones) noexcept {
        return parameter_event{sizeof(boiledegg_parameter_event), sample_offset,
                               BOILEDEGG_PARAMETER_PITCH_SEMITONES, semitones};
    }
    static parameter_event formant_ratio(uint32_t offset,float v) noexcept {
        return parameter_event{sizeof(boiledegg_parameter_event),offset,BOILEDEGG_PARAMETER_FORMANT_RATIO,v};
    }
    static parameter_event formant_semitones(uint32_t offset,float v) noexcept {
        return parameter_event{sizeof(boiledegg_parameter_event),offset,BOILEDEGG_PARAMETER_FORMANT_SEMITONES,v};
    }
};

inline boiledegg_profile_config profile(
    boiledegg_quality_mode quality,
    boiledegg_formant_mode formants = BOILEDEGG_FORMANT_OFF) noexcept {
    auto value = boiledegg_default_profile();
    value.quality_mode = static_cast<uint32_t>(quality);
    value.formant_mode = static_cast<uint32_t>(formants);
    return value;
}

class engine {
public:
    engine(boiledegg_config config, boiledegg_backend_config backend) {
        boiledegg_result result = BOILEDEGG_OK;
        handle_ = boiledegg_create_backend(&config, &backend, &result);
        if (!handle_) throw error(result);
    }
    boiledegg_backend_config backend_configuration() const {
        auto value=boiledegg_default_backend_config();
        check(boiledegg_get_backend_configuration(handle_,&value));
        return value;
    }
    explicit engine(boiledegg_config config) {
        boiledegg_result result = BOILEDEGG_OK;
        handle_ = boiledegg_create(&config, &result);
        if (!handle_) throw error(result);
    }

    engine(boiledegg_config config, boiledegg_profile_config profile_config) {
        boiledegg_result result = BOILEDEGG_OK;
        handle_ = boiledegg_create_ex(&config, &profile_config, &result);
        if (!handle_) throw error(result);
    }

    engine(uint32_t sample_rate, uint32_t channels)
        : engine(boiledegg_default_config(sample_rate, channels)) {}

    engine(uint32_t sample_rate, uint32_t channels,
           boiledegg_quality_mode quality,
           boiledegg_formant_mode formants = BOILEDEGG_FORMANT_OFF)
        : engine(boiledegg_default_config(sample_rate, channels),
                 profile(quality, formants)) {}

    ~engine() { boiledegg_destroy(handle_); }

    engine(const engine&) = delete;
    engine& operator=(const engine&) = delete;

    engine(engine&& other) noexcept : handle_(std::exchange(other.handle_, nullptr)) {}
    engine& operator=(engine&& other) noexcept {
        if (this != &other) {
            boiledegg_destroy(handle_);
            handle_ = std::exchange(other.handle_, nullptr);
        }
        return *this;
    }

    void set_formant_ratio(float v) { check(boiledegg_set_formant_ratio(handle_,v)); }
    void set_formant_semitones(float v) { check(boiledegg_set_formant_semitones(handle_,v)); }
    float formant_ratio() const noexcept { return boiledegg_get_formant_ratio(handle_); }
    boiledegg_backend_parameter_state backend_parameter_state() const {
        boiledegg_backend_parameter_state value{};value.struct_size=sizeof(value);
        check(boiledegg_get_backend_parameter_state(handle_,&value));return value;
    }
    void set_backend_parameter_state(const boiledegg_backend_parameter_state& value) {
        check(boiledegg_set_backend_parameter_state(handle_,&value));
    }
    void reset() { check(boiledegg_reset(handle_)); }
    void set_time_ratio(float ratio) { check(boiledegg_set_time_ratio(handle_, ratio)); }
    void set_pitch_ratio(float ratio) { check(boiledegg_set_pitch_ratio(handle_, ratio)); }
    void set_pitch_semitones(float st) { check(boiledegg_set_pitch_semitones(handle_, st)); }

    float time_ratio() const noexcept { return boiledegg_get_time_ratio(handle_); }
    float pitch_ratio() const noexcept { return boiledegg_get_pitch_ratio(handle_); }
    uint32_t available() const noexcept { return boiledegg_available(handle_); }
    uint32_t input_latency_frames() const noexcept { return boiledegg_input_latency_frames(handle_); }
    bool drained() const noexcept { return boiledegg_is_drained(handle_) != 0; }

    boiledegg_runtime_info runtime_info() const {
        boiledegg_runtime_info info{};
        info.struct_size = sizeof(info);
        check(boiledegg_get_runtime_info(handle_, &info));
        return info;
    }

    boiledegg_parameter_state parameter_state() const {
        boiledegg_parameter_state state{};
        state.struct_size = sizeof(state);
        check(boiledegg_get_parameter_state(handle_, &state));
        return state;
    }

    void set_parameter_state(const boiledegg_parameter_state& state) {
        check(boiledegg_set_parameter_state(handle_, &state));
    }

    void apply_parameter_events(std::span<const parameter_event> events) {
        const auto* raw = events.empty()
            ? nullptr
            : static_cast<const boiledegg_parameter_event*>(events.data());
        check(boiledegg_apply_parameter_events(handle_, raw, static_cast<uint32_t>(events.size())));
    }

    uint32_t push(const float* const* input, uint32_t frames) {
        uint32_t accepted = 0;
        check(boiledegg_push(handle_, input, frames, &accepted), true);
        return accepted;
    }

    uint32_t pull(float* const* output, uint32_t capacity) {
        uint32_t produced = 0;
        check(boiledegg_pull(handle_, output, capacity, &produced));
        return produced;
    }

    void flush() { check(boiledegg_flush(handle_)); }

    boiledegg_result process_realtime_nothrow(
        const float* const* input,
        float* const* output,
        uint32_t frames,
        std::span<const parameter_event> events = {}) noexcept {
        const auto* raw = events.empty()
            ? nullptr
            : static_cast<const boiledegg_parameter_event*>(events.data());
        return boiledegg_process_realtime(
            handle_, input, output, frames, raw, static_cast<uint32_t>(events.size()));
    }

    void process_realtime(
        const float* const* input,
        float* const* output,
        uint32_t frames,
        std::span<const parameter_event> events = {}) {
        check(process_realtime_nothrow(input, output, frames, events));
    }

    boiledegg_result process_realtime_ramps_nothrow(const float* const* input,float* const* output,
        uint32_t frames,std::span<const boiledegg_ramp_event> events={}) noexcept {
        if(events.size()>BOILEDEGG_MAX_RAMP_EVENTS)return BOILEDEGG_INVALID_ARGUMENT;
        return boiledegg_process_realtime_ramps(handle_,input,output,frames,events.data(),static_cast<uint32_t>(events.size()));
    }
    void process_realtime_ramps(const float* const* input,float* const* output,uint32_t frames,
        std::span<const boiledegg_ramp_event> events={}) {
        check(process_realtime_ramps_nothrow(input,output,frames,events));
    }
    uint32_t push_ramps(const float* const* input,uint32_t frames,std::span<const boiledegg_ramp_event> events={}) {
        if(events.size()>BOILEDEGG_MAX_RAMP_EVENTS)throw error(BOILEDEGG_INVALID_ARGUMENT);
        uint32_t accepted=0;
        check(boiledegg_push_ramps(handle_,input,frames,events.data(),static_cast<uint32_t>(events.size()),&accepted),true);
        return accepted;
    }
    boiledegg_automation_info automation_info() const {
        boiledegg_automation_info info{};info.struct_size=sizeof(info);
        check(boiledegg_get_automation_info(handle_,&info));return info;
    }
    boiledegg_handle* native_handle() noexcept { return handle_; }
    const boiledegg_handle* native_handle() const noexcept { return handle_; }

private:
    static void check(boiledegg_result r, bool allow_full = false) {
        if (r == BOILEDEGG_OK || (allow_full && r == BOILEDEGG_BUFFER_FULL)) return;
        throw error(r);
    }

    boiledegg_handle* handle_ = nullptr;
};

} // namespace boiled_egg
