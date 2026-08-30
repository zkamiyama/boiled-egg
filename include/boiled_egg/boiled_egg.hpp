#pragma once

#include <boiled_egg/boiled_egg.h>
#include <stdexcept>
#include <string>
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

class engine {
public:
    explicit engine(boiledegg_config config) {
        boiledegg_result result = BOILEDEGG_OK;
        handle_ = boiledegg_create(&config, &result);
        if (!handle_) throw error(result);
    }

    engine(uint32_t sample_rate, uint32_t channels)
        : engine(boiledegg_default_config(sample_rate, channels)) {}

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

    void reset() { check(boiledegg_reset(handle_)); }
    void set_time_ratio(float ratio) { check(boiledegg_set_time_ratio(handle_, ratio)); }
    void set_pitch_ratio(float ratio) { check(boiledegg_set_pitch_ratio(handle_, ratio)); }
    void set_pitch_semitones(float st) { check(boiledegg_set_pitch_semitones(handle_, st)); }

    float time_ratio() const noexcept { return boiledegg_get_time_ratio(handle_); }
    float pitch_ratio() const noexcept { return boiledegg_get_pitch_ratio(handle_); }
    uint32_t available() const noexcept { return boiledegg_available(handle_); }
    uint32_t input_latency_frames() const noexcept { return boiledegg_input_latency_frames(handle_); }
    bool drained() const noexcept { return boiledegg_is_drained(handle_) != 0; }

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
