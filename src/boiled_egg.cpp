#include <boiled_egg/boiled_egg.h>
#include "backend.hpp"
#include "backend_error.hpp"

#include <algorithm>
#include <array>
#include <atomic>
#include <bit>
#include <cmath>
#include <cstddef>
#include <cstdint>
#include <new>
#include <utility>

namespace {

enum class processing_mode : uint32_t {
    none = 0,
    streaming = 1,
    realtime = 2,
};

constexpr float kRealtimeTimeRatio = 1.0f;
constexpr float kRatioEpsilon = 1.0e-6f;

inline uint32_t float_bits(float value) noexcept {
    return std::bit_cast<uint32_t>(value);
}

inline float bits_float(uint32_t bits) noexcept {
    return std::bit_cast<float>(bits);
}

} // namespace

struct boiledegg_handle {
    static_assert(std::atomic<uint32_t>::is_always_lock_free,
                  "boiled egg requires lock-free 32-bit atomics");

    boiled_egg::detail::BackendEngine engine;
    const boiledegg_backend_config backend;
    std::atomic<uint32_t> requested_time_ratio_bits{float_bits(1.0f)};
    std::atomic<uint32_t> requested_pitch_ratio_bits{float_bits(1.0f)};
    std::atomic<uint32_t> requested_formant_ratio_bits{float_bits(1.0f)};
    std::atomic<uint32_t> mode{static_cast<uint32_t>(processing_mode::none)};

    uint32_t sample_rate = 0;
    uint32_t channels = 0;
    uint32_t max_block_size = 0;
    uint32_t parameter_quantum_frames = 0;
    uint32_t realtime_latency_frames = 0;
    uint32_t realtime_latency_remaining = 0;
    uint32_t realtime_tail_frames = 0;

    std::array<const float*, BOILEDEGG_MAX_CHANNELS> input_ptrs{};
    std::array<float*, BOILEDEGG_MAX_CHANNELS> output_ptrs{};

    explicit boiledegg_handle(const boiledegg_config& c)
        : boiledegg_handle(c,boiledegg_default_backend_config()) {}
    boiledegg_handle(const boiledegg_config& c,const boiledegg_backend_config& b)
        : engine(c,b), backend(b),
          requested_time_ratio_bits(float_bits(b.initial_time_ratio)),
          requested_pitch_ratio_bits(float_bits(b.initial_pitch_ratio)),
          requested_formant_ratio_bits(float_bits(b.initial_formant_ratio)),
          sample_rate(c.sample_rate),
          channels(c.channels),
          max_block_size(c.max_block_size),
          parameter_quantum_frames(engine.quantum(c)),
          realtime_latency_frames(engine.realtime_latency(c)),
          realtime_latency_remaining(engine.realtime_latency(c)),
          realtime_tail_frames(engine.realtime_tail(c)) {}
};

namespace {

inline void store_ratio(std::atomic<uint32_t>& bits, float value) noexcept {
    bits.store(float_bits(value), std::memory_order_relaxed);
}

inline float load_ratio(const std::atomic<uint32_t>& bits) noexcept {
    return bits_float(bits.load(std::memory_order_relaxed));
}

processing_mode load_mode(const boiledegg_handle* h) noexcept {
    return static_cast<processing_mode>(h->mode.load(std::memory_order_acquire));
}

bool enter_mode(boiledegg_handle* h, processing_mode desired) noexcept {
    if ((h->backend.io_contract==BOILEDEGG_IO_STREAMING && desired!=processing_mode::streaming) ||
        (h->backend.io_contract==BOILEDEGG_IO_REALTIME && desired!=processing_mode::realtime)) return false;
    const uint32_t desired_bits = static_cast<uint32_t>(desired);
    uint32_t current = h->mode.load(std::memory_order_acquire);
    if (current == desired_bits) return true;
    if (current != static_cast<uint32_t>(processing_mode::none)) return false;
    return h->mode.compare_exchange_strong(
        current, desired_bits, std::memory_order_acq_rel, std::memory_order_acquire) ||
        current == desired_bits;
}

inline void sync_requested_parameters_streaming(boiledegg_handle* h) noexcept {
    (void)h->engine.set_time_ratio(load_ratio(h->requested_time_ratio_bits));
    (void)h->engine.set_pitch_ratio(load_ratio(h->requested_pitch_ratio_bits));
    (void)h->engine.set_formant_ratio(load_ratio(h->requested_formant_ratio_bits));
}

inline void sync_requested_parameters_realtime(boiledegg_handle* h) noexcept {
    (void)h->engine.set_time_ratio(kRealtimeTimeRatio);
    (void)h->engine.set_pitch_ratio(load_ratio(h->requested_pitch_ratio_bits));
    (void)h->engine.set_formant_ratio(load_ratio(h->requested_formant_ratio_bits));
}

bool valid_config(const boiledegg_config& c) {
    if (c.struct_size < sizeof(boiledegg_config) || c.abi_version != BOILEDEGG_ABI_VERSION) return false;
    if (c.sample_rate < 8000 || c.sample_rate > 384000) return false;
    if (c.channels == 0 || c.channels > BOILEDEGG_MAX_CHANNELS) return false;
    if (c.max_block_size == 0 || c.max_block_size > 65536) return false;
    if (c.window_frames < 128 || (c.window_frames % 2u) != 0) return false;
    if (c.search_frames >= c.window_frames / 2u) return false;
    if (c.fifo_frames < c.window_frames * 8u + c.max_block_size * 2u) return false;
    return true;
}

bool valid_planar_input(const boiledegg_handle* h, const float* const* input) noexcept {
    if (!input) return false;
    for (uint32_t ch = 0; ch < h->channels; ++ch) {
        if (!input[ch]) return false;
    }
    return true;
}

bool valid_planar_output(const boiledegg_handle* h, float* const* output) noexcept {
    if (!output) return false;
    for (uint32_t ch = 0; ch < h->channels; ++ch) {
        if (!output[ch]) return false;
    }
    return true;
}

boiledegg_result validate_parameter_value(const boiledegg_handle* h,uint32_t parameter_id, float value, bool fixed_realtime) noexcept {
    if (!std::isfinite(value)) return BOILEDEGG_INVALID_ARGUMENT;
    if(h->backend.backend_id==BOILEDEGG_BACKEND_PHASE_VOCODER){
        if(parameter_id==BOILEDEGG_PARAMETER_TIME_RATIO || parameter_id==BOILEDEGG_PARAMETER_PITCH_RATIO || parameter_id==BOILEDEGG_PARAMETER_PITCH_SEMITONES){
            if(parameter_id==BOILEDEGG_PARAMETER_PITCH_SEMITONES && (value < -24.f || value > 24.f))return BOILEDEGG_INVALID_ARGUMENT;
            const float v=parameter_id==BOILEDEGG_PARAMETER_PITCH_SEMITONES?std::pow(2.0f,value/12.0f):value;
            if(v<.25f || v>4.f)return BOILEDEGG_INVALID_ARGUMENT;
            const float expected=parameter_id==BOILEDEGG_PARAMETER_TIME_RATIO?h->backend.initial_time_ratio:h->backend.initial_pitch_ratio;
            if(v!=expected)return BOILEDEGG_UNSUPPORTED_MODE;
        }
    }
    switch (parameter_id) {
        case BOILEDEGG_PARAMETER_TIME_RATIO:
            if (value < 0.25f || value > 4.0f) return BOILEDEGG_INVALID_ARGUMENT;
            if (fixed_realtime && std::abs(value - kRealtimeTimeRatio) > kRatioEpsilon) {
                return BOILEDEGG_UNSUPPORTED_MODE;
            }
            return BOILEDEGG_OK;
        case BOILEDEGG_PARAMETER_PITCH_RATIO:
            return value >= 0.25f && value <= 4.0f ? BOILEDEGG_OK : BOILEDEGG_INVALID_ARGUMENT;
        case BOILEDEGG_PARAMETER_PITCH_SEMITONES:
            return value >= -24.0f && value <= 24.0f ? BOILEDEGG_OK : BOILEDEGG_INVALID_ARGUMENT;
        case BOILEDEGG_PARAMETER_FORMANT_RATIO:
        case BOILEDEGG_PARAMETER_FORMANT_SEMITONES: {
            const bool semitones=parameter_id==BOILEDEGG_PARAMETER_FORMANT_SEMITONES;
            if(semitones?(value < -12.f || value > 12.f):(value < .5f || value > 2.f))return BOILEDEGG_INVALID_ARGUMENT;
            const float v=semitones?std::pow(2.f,value/12.f):value;
            if((h->backend.backend_id!=BOILEDEGG_BACKEND_PHASE_VOCODER || h->backend.formant_policy==BOILEDEGG_FORMANT_POLICY_OFF) && v!=1.f)
                return BOILEDEGG_UNSUPPORTED_MODE;
            return BOILEDEGG_OK;
        }
        default:
            return BOILEDEGG_INVALID_ARGUMENT;
    }
}

boiledegg_result validate_realtime_event(const boiledegg_handle* h,const boiledegg_parameter_event& event, uint32_t frames) noexcept {
    if (event.struct_size < sizeof(boiledegg_parameter_event) || event.sample_offset >= frames) {
        return BOILEDEGG_INVALID_ARGUMENT;
    }
    return validate_parameter_value(h,event.parameter_id, event.value, true);
}

boiledegg_result validate_parameter_only_event(
    const boiledegg_handle* h,const boiledegg_parameter_event& event,
    bool fixed_realtime) noexcept {
    if (event.struct_size < sizeof(boiledegg_parameter_event) || event.sample_offset != 0) {
        return BOILEDEGG_INVALID_ARGUMENT;
    }
    return validate_parameter_value(h,event.parameter_id, event.value, fixed_realtime);
}

void store_event_mailbox(boiledegg_handle* h, const boiledegg_parameter_event& event) noexcept {
    switch (event.parameter_id) {
        case BOILEDEGG_PARAMETER_TIME_RATIO:
            store_ratio(h->requested_time_ratio_bits, event.value);
            break;
        case BOILEDEGG_PARAMETER_PITCH_RATIO:
            store_ratio(h->requested_pitch_ratio_bits, event.value);
            break;
        case BOILEDEGG_PARAMETER_PITCH_SEMITONES:
            store_ratio(h->requested_pitch_ratio_bits, std::pow(2.0f, event.value / 12.0f));
            break;
        case BOILEDEGG_PARAMETER_FORMANT_RATIO:
            store_ratio(h->requested_formant_ratio_bits,event.value);break;
        case BOILEDEGG_PARAMETER_FORMANT_SEMITONES:
            store_ratio(h->requested_formant_ratio_bits,std::pow(2.f,event.value/12.f));break;
        default:
            break;
    }
}

boiledegg_result apply_event_realtime(boiledegg_handle* h, const boiledegg_parameter_event& event) noexcept {
    store_event_mailbox(h, event);
    switch (event.parameter_id) {
        case BOILEDEGG_PARAMETER_TIME_RATIO:
            return h->engine.set_time_ratio(kRealtimeTimeRatio);
        case BOILEDEGG_PARAMETER_PITCH_RATIO:
            return h->engine.set_pitch_ratio(event.value);
        case BOILEDEGG_PARAMETER_PITCH_SEMITONES:
            return h->engine.set_pitch_ratio(std::pow(2.0f, event.value / 12.0f));
        case BOILEDEGG_PARAMETER_FORMANT_RATIO:
        case BOILEDEGG_PARAMETER_FORMANT_SEMITONES:
            return h->engine.set_formant_ratio(load_ratio(h->requested_formant_ratio_bits));
        default:
            return BOILEDEGG_INVALID_ARGUMENT;
    }
}

boiledegg_result process_realtime_chunk(
    boiledegg_handle* h,
    const float* const* input,
    float* const* output,
    uint32_t offset,
    uint32_t frames) noexcept {
    if (frames == 0) return BOILEDEGG_OK;

    for (uint32_t ch = 0; ch < h->channels; ++ch) {
        h->input_ptrs[ch] = input[ch] + offset;
    }

    uint32_t accepted = 0;
    const boiledegg_result push_result = h->engine.push(h->input_ptrs.data(), frames, accepted);
    if ((push_result != BOILEDEGG_OK && push_result != BOILEDEGG_BUFFER_FULL) || accepted != frames) {
        return push_result == BOILEDEGG_OK ? BOILEDEGG_BUFFER_FULL : push_result;
    }

    uint32_t cursor = 0;
    if (h->realtime_latency_remaining > 0) {
        const uint32_t zero_frames = std::min(frames, h->realtime_latency_remaining);
        for (uint32_t ch = 0; ch < h->channels; ++ch) {
            std::fill_n(output[ch] + offset, zero_frames, 0.0f);
        }
        h->realtime_latency_remaining -= zero_frames;
        cursor = zero_frames;
    }

    const uint32_t wanted = frames - cursor;
    if (wanted == 0) return BOILEDEGG_OK;

    for (uint32_t ch = 0; ch < h->channels; ++ch) {
        h->output_ptrs[ch] = output[ch] + offset + cursor;
    }

    uint32_t produced = 0;
    const boiledegg_result pull_result = h->engine.pull(h->output_ptrs.data(), wanted, produced);
    if (pull_result != BOILEDEGG_OK) return pull_result;
    if (produced == wanted) return BOILEDEGG_OK;

    for (uint32_t ch = 0; ch < h->channels; ++ch) {
        std::fill_n(output[ch] + offset + cursor + produced, wanted - produced, 0.0f);
    }
    return BOILEDEGG_REALTIME_UNDERRUN;
}

} // namespace

extern "C" {

boiledegg_config boiledegg_default_config(uint32_t sample_rate, uint32_t channels) {
    boiledegg_config c{};
    c.struct_size = sizeof(boiledegg_config);
    c.abi_version = BOILEDEGG_ABI_VERSION;
    c.sample_rate = sample_rate;
    c.channels = channels;
    c.max_block_size = 2048;
    c.window_frames = sample_rate >= 88200 ? 1536 : 1024;
    c.search_frames = c.window_frames / 8u;
    c.fifo_frames = 1u << 18u;
    return c;
}

uint32_t boiledegg_abi_version(void) { return BOILEDEGG_ABI_VERSION; }
const char* boiledegg_version_string(void) { return "0.1.2-daw-foundation"; }

const char* boiledegg_result_string(boiledegg_result r) {
    switch (r) {
        case BOILEDEGG_OK: return "ok";
        case BOILEDEGG_INVALID_ARGUMENT: return "invalid argument";
        case BOILEDEGG_OUT_OF_MEMORY: return "out of memory";
        case BOILEDEGG_BUFFER_FULL: return "buffer full";
        case BOILEDEGG_END_OF_STREAM: return "end of stream";
        case BOILEDEGG_INTERNAL_ERROR: return "internal error";
        case BOILEDEGG_INVALID_STATE: return "invalid state";
        case BOILEDEGG_UNSUPPORTED_MODE: return "unsupported mode";
        case BOILEDEGG_REALTIME_UNDERRUN: return "realtime underrun";
        default: return "unknown error";
    }
}

boiledegg_handle* boiledegg_create(const boiledegg_config* config, boiledegg_result* out_result) {
    if (out_result) *out_result = BOILEDEGG_INVALID_ARGUMENT;
    if (!config || !valid_config(*config)) return nullptr;
    try {
        auto* h = new boiledegg_handle(*config);
        if (out_result) *out_result = BOILEDEGG_OK;
        return h;
    } catch (const std::bad_alloc&) {
        if (out_result) *out_result = BOILEDEGG_OUT_OF_MEMORY;
        return nullptr;
    } catch (...) {
        if (out_result) *out_result = BOILEDEGG_INTERNAL_ERROR;
        return nullptr;
    }
}

void boiledegg_destroy(boiledegg_handle* h) { delete h; }

boiledegg_result boiledegg_reset(boiledegg_handle* h) {
    if (!h) return BOILEDEGG_INVALID_ARGUMENT;
    const auto result = h->engine.reset();
    if (result != BOILEDEGG_OK) return result;
    h->realtime_latency_remaining = h->realtime_latency_frames;
    h->mode.store(static_cast<uint32_t>(processing_mode::none), std::memory_order_release);
    sync_requested_parameters_streaming(h);
    return BOILEDEGG_OK;
}

boiledegg_result boiledegg_set_time_ratio(boiledegg_handle* h, float r) {
    if (!h || !std::isfinite(r) || r < 0.25f || r > 4.0f) return BOILEDEGG_INVALID_ARGUMENT;
    const auto checked=validate_parameter_value(h,BOILEDEGG_PARAMETER_TIME_RATIO,r,h->backend.io_contract==BOILEDEGG_IO_REALTIME);
    if(checked!=BOILEDEGG_OK)return checked;
    const bool non_realtime_ratio = std::abs(r - kRealtimeTimeRatio) > kRatioEpsilon;
    if (non_realtime_ratio && (load_mode(h) == processing_mode::realtime || h->backend.io_contract==BOILEDEGG_IO_REALTIME)) {
        return BOILEDEGG_UNSUPPORTED_MODE;
    }
    store_ratio(h->requested_time_ratio_bits, r);
    if (non_realtime_ratio && (load_mode(h) == processing_mode::realtime || h->backend.io_contract==BOILEDEGG_IO_REALTIME)) {
        store_ratio(h->requested_time_ratio_bits, kRealtimeTimeRatio);
        return BOILEDEGG_UNSUPPORTED_MODE;
    }
    return BOILEDEGG_OK;
}

boiledegg_result boiledegg_set_pitch_ratio(boiledegg_handle* h, float r) {
    if (!h || !std::isfinite(r) || r < 0.25f || r > 4.0f) return BOILEDEGG_INVALID_ARGUMENT;
    const auto checked=validate_parameter_value(h,BOILEDEGG_PARAMETER_PITCH_RATIO,r,h->backend.io_contract==BOILEDEGG_IO_REALTIME);
    if(checked!=BOILEDEGG_OK)return checked;
    store_ratio(h->requested_pitch_ratio_bits, r);
    return BOILEDEGG_OK;
}

boiledegg_result boiledegg_set_pitch_semitones(boiledegg_handle* h, float st) {
    if (!h || !std::isfinite(st) || st < -24.0f || st > 24.0f) return BOILEDEGG_INVALID_ARGUMENT;
    const auto checked=validate_parameter_value(h,BOILEDEGG_PARAMETER_PITCH_SEMITONES,st,h->backend.io_contract==BOILEDEGG_IO_REALTIME);
    if(checked!=BOILEDEGG_OK)return checked;
    store_ratio(h->requested_pitch_ratio_bits, std::pow(2.0f, st / 12.0f));
    return BOILEDEGG_OK;
}

float boiledegg_get_time_ratio(const boiledegg_handle* h) {
    return h ? load_ratio(h->requested_time_ratio_bits) : 0.0f;
}

float boiledegg_get_pitch_ratio(const boiledegg_handle* h) {
    return h ? load_ratio(h->requested_pitch_ratio_bits) : 0.0f;
}

boiledegg_result boiledegg_apply_parameter_events(
    boiledegg_handle* h,
    const boiledegg_parameter_event* events,
    uint32_t event_count) {
    if (!h) return BOILEDEGG_INVALID_ARGUMENT;
    if (event_count > 0 && !events) return BOILEDEGG_INVALID_ARGUMENT;
    if(h->backend.backend_id==BOILEDEGG_BACKEND_PHASE_VOCODER && event_count>256)return BOILEDEGG_INVALID_ARGUMENT;
    const bool fixed_realtime = (load_mode(h) == processing_mode::realtime || h->backend.io_contract==BOILEDEGG_IO_REALTIME);
    for (uint32_t i = 0; i < event_count; ++i) {
        const auto result = validate_parameter_only_event(h,events[i], fixed_realtime);
        if (result != BOILEDEGG_OK) return result;
    }
    for (uint32_t i = 0; i < event_count; ++i) {
        store_event_mailbox(h, events[i]);
    }
    return BOILEDEGG_OK;
}

boiledegg_result boiledegg_get_parameter_state(
    const boiledegg_handle* h,
    boiledegg_parameter_state* out_state) {
    if (!h || !out_state || out_state->struct_size < sizeof(boiledegg_parameter_state)) {
        return BOILEDEGG_INVALID_ARGUMENT;
    }
    out_state->time_ratio = load_ratio(h->requested_time_ratio_bits);
    out_state->pitch_ratio = load_ratio(h->requested_pitch_ratio_bits);
    out_state->reserved = 0;
    return BOILEDEGG_OK;
}

boiledegg_result boiledegg_set_parameter_state(
    boiledegg_handle* h,
    const boiledegg_parameter_state* state) {
    if (!h || !state || state->struct_size < sizeof(boiledegg_parameter_state)) {
        return BOILEDEGG_INVALID_ARGUMENT;
    }
    if (!std::isfinite(state->time_ratio) || state->time_ratio < 0.25f || state->time_ratio > 4.0f ||
        !std::isfinite(state->pitch_ratio) || state->pitch_ratio < 0.25f || state->pitch_ratio > 4.0f) {
        return BOILEDEGG_INVALID_ARGUMENT;
    }
    const auto time_status=validate_parameter_value(h,BOILEDEGG_PARAMETER_TIME_RATIO,state->time_ratio,false);
    const auto pitch_status=validate_parameter_value(h,BOILEDEGG_PARAMETER_PITCH_RATIO,state->pitch_ratio,false);
    if(time_status!=BOILEDEGG_OK)return time_status;
    if(pitch_status!=BOILEDEGG_OK)return pitch_status;
    const bool non_realtime_ratio = std::abs(state->time_ratio - kRealtimeTimeRatio) > kRatioEpsilon;
    if (non_realtime_ratio && (load_mode(h) == processing_mode::realtime || h->backend.io_contract==BOILEDEGG_IO_REALTIME)) {
        return BOILEDEGG_UNSUPPORTED_MODE;
    }
    store_ratio(h->requested_time_ratio_bits, state->time_ratio);
    store_ratio(h->requested_pitch_ratio_bits, state->pitch_ratio);
    if (non_realtime_ratio && (load_mode(h) == processing_mode::realtime || h->backend.io_contract==BOILEDEGG_IO_REALTIME)) {
        store_ratio(h->requested_time_ratio_bits, kRealtimeTimeRatio);
        return BOILEDEGG_UNSUPPORTED_MODE;
    }
    return BOILEDEGG_OK;
}

boiledegg_result boiledegg_push(boiledegg_handle* h, const float* const* in, uint32_t frames, uint32_t* accepted) {
    if (!h || !accepted) return BOILEDEGG_INVALID_ARGUMENT;
    if (!enter_mode(h, processing_mode::streaming)) return BOILEDEGG_INVALID_STATE;
    sync_requested_parameters_streaming(h);
    return h->engine.push(in, frames, *accepted);
}

uint32_t boiledegg_available(const boiledegg_handle* h) {
    return h ? h->engine.available() : 0;
}

boiledegg_result boiledegg_pull(boiledegg_handle* h, float* const* out, uint32_t cap, uint32_t* produced) {
    if (!h || !produced) return BOILEDEGG_INVALID_ARGUMENT;
    if (!enter_mode(h, processing_mode::streaming)) return BOILEDEGG_INVALID_STATE;
    sync_requested_parameters_streaming(h);
    return h->engine.pull(out, cap, *produced);
}

boiledegg_result boiledegg_flush(boiledegg_handle* h) {
    if (!h) return BOILEDEGG_INVALID_ARGUMENT;
    if (!enter_mode(h, processing_mode::streaming)) return BOILEDEGG_INVALID_STATE;
    sync_requested_parameters_streaming(h);
    return h->engine.flush();
}

int boiledegg_is_drained(const boiledegg_handle* h) {
    return h && load_mode(h) != processing_mode::realtime && h->engine.drained() ? 1 : 0;
}

boiledegg_result boiledegg_process_realtime(
    boiledegg_handle* h,
    const float* const* input,
    float* const* output,
    uint32_t frames,
    const boiledegg_parameter_event* events,
    uint32_t event_count) {
    if (!h) return BOILEDEGG_INVALID_ARGUMENT;
    if (frames == 0) return boiledegg_apply_parameter_events(h, events, event_count);
    if (frames > h->max_block_size || !valid_planar_input(h, input) || !valid_planar_output(h, output)) {
        return BOILEDEGG_INVALID_ARGUMENT;
    }
    if (event_count > 0 && !events) return BOILEDEGG_INVALID_ARGUMENT;
    if(h->backend.backend_id==BOILEDEGG_BACKEND_PHASE_VOCODER){
        if(event_count>256)return BOILEDEGG_INVALID_ARGUMENT;
        for(uint32_t ch=0;ch<h->channels;++ch)for(uint32_t i=0;i<frames;++i)
            if(!std::isfinite(input[ch][i]))return BOILEDEGG_INVALID_ARGUMENT;
    }

    uint32_t previous_offset = 0;
    for (uint32_t i = 0; i < event_count; ++i) {
        const boiledegg_result event_result = validate_realtime_event(h,events[i], frames);
        if (event_result != BOILEDEGG_OK) return event_result;
        if (i > 0 && events[i].sample_offset < previous_offset) return BOILEDEGG_INVALID_ARGUMENT;
        previous_offset = events[i].sample_offset;
    }

    const processing_mode before = load_mode(h);
    if (before == processing_mode::none &&
        std::abs(load_ratio(h->requested_time_ratio_bits) - kRealtimeTimeRatio) > kRatioEpsilon) {
        return BOILEDEGG_UNSUPPORTED_MODE;
    }
    if (!enter_mode(h, processing_mode::realtime)) return BOILEDEGG_INVALID_STATE;

    // A control-thread time-ratio setter can race the first realtime mode
    // transition. The setter will report UNSUPPORTED_MODE; do not make the
    // audio callback fail transiently because of that race.
    if (std::abs(load_ratio(h->requested_time_ratio_bits) - kRealtimeTimeRatio) > kRatioEpsilon) {
        store_ratio(h->requested_time_ratio_bits, kRealtimeTimeRatio);
    }
    sync_requested_parameters_realtime(h);

    boiledegg_result overall = BOILEDEGG_OK;
    uint32_t cursor = 0;
    uint32_t event_index = 0;
    while (event_index < event_count) {
        const uint32_t event_offset = events[event_index].sample_offset;
        if (event_offset > cursor) {
            const boiledegg_result chunk_result = process_realtime_chunk(h, input, output, cursor, event_offset - cursor);
            if (chunk_result != BOILEDEGG_OK && chunk_result != BOILEDEGG_REALTIME_UNDERRUN) return chunk_result;
            if (chunk_result == BOILEDEGG_REALTIME_UNDERRUN) overall = chunk_result;
            cursor = event_offset;
        }
        while (event_index < event_count && events[event_index].sample_offset == cursor) {
            const boiledegg_result event_result = apply_event_realtime(h, events[event_index]);
            if (event_result != BOILEDEGG_OK) return event_result;
            ++event_index;
        }
    }

    if (cursor < frames) {
        const boiledegg_result chunk_result = process_realtime_chunk(h, input, output, cursor, frames - cursor);
        if (chunk_result != BOILEDEGG_OK && chunk_result != BOILEDEGG_REALTIME_UNDERRUN) overall = chunk_result;
        if (chunk_result == BOILEDEGG_REALTIME_UNDERRUN) overall = chunk_result;
    }
    return overall;
}

boiledegg_result boiledegg_get_runtime_info(const boiledegg_handle* h, boiledegg_runtime_info* out_info) {
    if (!h || !out_info || out_info->struct_size < sizeof(boiledegg_runtime_info)) {
        return BOILEDEGG_INVALID_ARGUMENT;
    }
    out_info->sample_rate = h->sample_rate;
    out_info->channels = h->channels;
    out_info->max_block_size = h->max_block_size;
    out_info->realtime_latency_frames = h->realtime_latency_frames;
    out_info->realtime_tail_frames = h->realtime_tail_frames;
    out_info->parameter_quantum_frames = h->parameter_quantum_frames;
    out_info->capabilities = BOILEDEGG_CAP_PARALLEL_INSTANCES |
                             BOILEDEGG_CAP_CONTROL_THREAD_PARAMETERS |
                             BOILEDEGG_CAP_FIXED_REALTIME_IO |
                             BOILEDEGG_CAP_SAMPLE_OFFSET_EVENTS |
                             BOILEDEGG_CAP_IN_PLACE_REALTIME_IO |
                             BOILEDEGG_CAP_REALTIME_RESET |
                             BOILEDEGG_CAP_HARD_REALTIME_PROCESSING |
                             BOILEDEGG_CAP_PARAMETER_ONLY_FLUSH;
    if(h->backend.backend_id==BOILEDEGG_BACKEND_PHASE_VOCODER)
        out_info->capabilities &= ~BOILEDEGG_CAP_HARD_REALTIME_PROCESSING;
    if(h->backend.io_contract==BOILEDEGG_IO_STREAMING){
        out_info->capabilities &= ~(BOILEDEGG_CAP_FIXED_REALTIME_IO|BOILEDEGG_CAP_IN_PLACE_REALTIME_IO|BOILEDEGG_CAP_SAMPLE_OFFSET_EVENTS);
        out_info->realtime_latency_frames=out_info->realtime_tail_frames=0;
    }
    return BOILEDEGG_OK;
}

uint32_t boiledegg_input_latency_frames(const boiledegg_handle* h) {
    return h ? h->engine.input_latency_frames() : 0;
}

boiledegg_result boiledegg_set_formant_ratio(boiledegg_handle* h,float v) {
    if(!h)return BOILEDEGG_INVALID_ARGUMENT;
    const auto r=validate_parameter_value(h,BOILEDEGG_PARAMETER_FORMANT_RATIO,v,false);
    if(r==BOILEDEGG_OK)store_ratio(h->requested_formant_ratio_bits,v);
    return r;
}
boiledegg_result boiledegg_set_formant_semitones(boiledegg_handle* h,float v) {
    if(!h)return BOILEDEGG_INVALID_ARGUMENT;
    const auto r=validate_parameter_value(h,BOILEDEGG_PARAMETER_FORMANT_SEMITONES,v,false);
    if(r==BOILEDEGG_OK)store_ratio(h->requested_formant_ratio_bits,std::pow(2.f,v/12.f));
    return r;
}
float boiledegg_get_formant_ratio(const boiledegg_handle* h) {
    return h?load_ratio(h->requested_formant_ratio_bits):0.f;
}
boiledegg_result boiledegg_get_backend_parameter_state(const boiledegg_handle* h,boiledegg_backend_parameter_state* s) {
    if(!h || !s || s->struct_size<sizeof(*s))return BOILEDEGG_INVALID_ARGUMENT;
    *s={sizeof(*s),BOILEDEGG_BACKEND_API_VERSION,h->backend.backend_id,h->backend.formant_policy,
        load_ratio(h->requested_time_ratio_bits),load_ratio(h->requested_pitch_ratio_bits),load_ratio(h->requested_formant_ratio_bits),0};
    return BOILEDEGG_OK;
}
boiledegg_result boiledegg_set_backend_parameter_state(boiledegg_handle* h,const boiledegg_backend_parameter_state* s) {
    if(!h || !s || s->struct_size<sizeof(*s) || s->version!=BOILEDEGG_BACKEND_API_VERSION || s->reserved)return BOILEDEGG_INVALID_ARGUMENT;
    if(s->backend_id!=h->backend.backend_id || s->formant_policy!=h->backend.formant_policy)return BOILEDEGG_UNSUPPORTED_MODE;
    const bool fixed=h->backend.io_contract==BOILEDEGG_IO_REALTIME || load_mode(h)==processing_mode::realtime;
    for(const auto pair:{std::pair{BOILEDEGG_PARAMETER_TIME_RATIO,s->time_ratio},std::pair{BOILEDEGG_PARAMETER_PITCH_RATIO,s->pitch_ratio}}){
        const auto status=validate_parameter_value(h,static_cast<uint32_t>(pair.first),pair.second,fixed);
        if(status!=BOILEDEGG_OK)return status;
    }
    const auto status=validate_parameter_value(h,BOILEDEGG_PARAMETER_FORMANT_RATIO,s->formant_ratio,fixed);
    if(status!=BOILEDEGG_OK)return status;
    boiledegg_parameter_state legacy{sizeof(legacy),s->time_ratio,s->pitch_ratio,0};
    const auto restored=boiledegg_set_parameter_state(h,&legacy);
    if(restored!=BOILEDEGG_OK)return restored;
    store_ratio(h->requested_formant_ratio_bits,s->formant_ratio);return BOILEDEGG_OK;
}
boiledegg_result boiledegg_get_backend_configuration(const boiledegg_handle* h,boiledegg_backend_config* out) {
    if (!h || !out || out->struct_size<sizeof(*out)) return BOILEDEGG_INVALID_ARGUMENT;
    *out=h->backend; out->struct_size=sizeof(*out); return BOILEDEGG_OK;
}
} // extern C
namespace boiled_egg::detail {
boiledegg_handle* create_selected_backend(const boiledegg_config& c,
    const boiledegg_backend_config& b,boiledegg_result* result) {
    try {
        auto* h=new boiledegg_handle(c,b);
        if (result) *result=BOILEDEGG_OK;
        return h;
    } catch (const boiled_egg::detail::BackendConstructionError& error) {
        if (result) *result=error.status;
    } catch (const std::bad_alloc&) {
        if (result) *result=BOILEDEGG_OUT_OF_MEMORY;
    } catch (...) {
        if (result) *result=BOILEDEGG_INTERNAL_ERROR;
    }
    return nullptr;
}
}
