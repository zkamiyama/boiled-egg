#include <boiled_egg/boiled_egg.h>
#include "engine.hpp"

#include <algorithm>
#include <array>
#include <atomic>
#include <bit>
#include <cmath>
#include <cstddef>
#include <cstdint>
#include <new>

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

    boiled_egg::detail::Engine engine;
    std::atomic<uint32_t> requested_time_ratio_bits{float_bits(1.0f)};
    std::atomic<uint32_t> requested_pitch_ratio_bits{float_bits(1.0f)};
    std::atomic<uint32_t> mode{static_cast<uint32_t>(processing_mode::none)};

    uint32_t sample_rate = 0;
    uint32_t channels = 0;
    uint32_t max_block_size = 0;
    uint32_t parameter_quantum_frames = 0;
    uint32_t realtime_latency_frames = 0;
    uint32_t realtime_latency_remaining = 0;

    std::array<const float*, BOILEDEGG_MAX_CHANNELS> input_ptrs{};
    std::array<float*, BOILEDEGG_MAX_CHANNELS> output_ptrs{};

    explicit boiledegg_handle(const boiledegg_config& c)
        : engine(c),
          sample_rate(c.sample_rate),
          channels(c.channels),
          max_block_size(c.max_block_size),
          parameter_quantum_frames(c.window_frames / 2u),
          realtime_latency_frames(engine.input_latency_frames() + c.window_frames / 2u),
          realtime_latency_remaining(engine.input_latency_frames() + c.window_frames / 2u) {}
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
    const uint32_t desired_bits = static_cast<uint32_t>(desired);
    uint32_t current = h->mode.load(std::memory_order_acquire);
    if (current == desired_bits) return true;
    if (current != static_cast<uint32_t>(processing_mode::none)) return false;
    return h->mode.compare_exchange_strong(
        current, desired_bits, std::memory_order_acq_rel, std::memory_order_acquire) ||
        current == desired_bits;
}

inline void sync_requested_parameters_streaming(boiledegg_handle* h) noexcept {
    // Called only by the handle's single-owner streaming/lifecycle thread.
    (void)h->engine.set_time_ratio(load_ratio(h->requested_time_ratio_bits));
    (void)h->engine.set_pitch_ratio(load_ratio(h->requested_pitch_ratio_bits));
}

inline void sync_requested_parameters_realtime(boiledegg_handle* h) noexcept {
    // Fixed-rate DAW insert mode always keeps the timeline ratio at 1.0.
    (void)h->engine.set_time_ratio(kRealtimeTimeRatio);
    (void)h->engine.set_pitch_ratio(load_ratio(h->requested_pitch_ratio_bits));
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

boiledegg_result validate_event(const boiledegg_parameter_event& event, uint32_t frames) noexcept {
    if (event.struct_size < sizeof(boiledegg_parameter_event) || event.sample_offset >= frames) {
        return BOILEDEGG_INVALID_ARGUMENT;
    }
    if (!std::isfinite(event.value)) return BOILEDEGG_INVALID_ARGUMENT;
    switch (event.parameter_id) {
        case BOILEDEGG_PARAMETER_TIME_RATIO:
            if (std::abs(event.value - kRealtimeTimeRatio) > kRatioEpsilon) return BOILEDEGG_UNSUPPORTED_MODE;
            return BOILEDEGG_OK;
        case BOILEDEGG_PARAMETER_PITCH_RATIO:
            return event.value >= 0.25f && event.value <= 4.0f ? BOILEDEGG_OK : BOILEDEGG_INVALID_ARGUMENT;
        case BOILEDEGG_PARAMETER_PITCH_SEMITONES:
            return event.value >= -24.0f && event.value <= 24.0f ? BOILEDEGG_OK : BOILEDEGG_INVALID_ARGUMENT;
        default:
            return BOILEDEGG_INVALID_ARGUMENT;
    }
}

boiledegg_result apply_event(boiledegg_handle* h, const boiledegg_parameter_event& event) noexcept {
    switch (event.parameter_id) {
        case BOILEDEGG_PARAMETER_TIME_RATIO:
            store_ratio(h->requested_time_ratio_bits, kRealtimeTimeRatio);
            return h->engine.set_time_ratio(kRealtimeTimeRatio);
        case BOILEDEGG_PARAMETER_PITCH_RATIO:
            store_ratio(h->requested_pitch_ratio_bits, event.value);
            return h->engine.set_pitch_ratio(event.value);
        case BOILEDEGG_PARAMETER_PITCH_SEMITONES: {
            const float ratio = std::pow(2.0f, event.value / 12.0f);
            store_ratio(h->requested_pitch_ratio_bits, ratio);
            return h->engine.set_pitch_ratio(ratio);
        }
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
const char* boiledegg_version_string(void) { return "0.1.1-daw-foundation"; }

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
    const bool non_realtime_ratio = std::abs(r - kRealtimeTimeRatio) > kRatioEpsilon;
    if (non_realtime_ratio && load_mode(h) == processing_mode::realtime) {
        return BOILEDEGG_UNSUPPORTED_MODE;
    }
    store_ratio(h->requested_time_ratio_bits, r);
    if (non_realtime_ratio && load_mode(h) == processing_mode::realtime) {
        store_ratio(h->requested_time_ratio_bits, kRealtimeTimeRatio);
        return BOILEDEGG_UNSUPPORTED_MODE;
    }
    return BOILEDEGG_OK;
}

boiledegg_result boiledegg_set_pitch_ratio(boiledegg_handle* h, float r) {
    if (!h || !std::isfinite(r) || r < 0.25f || r > 4.0f) return BOILEDEGG_INVALID_ARGUMENT;
    store_ratio(h->requested_pitch_ratio_bits, r);
    return BOILEDEGG_OK;
}

boiledegg_result boiledegg_set_pitch_semitones(boiledegg_handle* h, float st) {
    if (!h || !std::isfinite(st) || st < -24.0f || st > 24.0f) return BOILEDEGG_INVALID_ARGUMENT;
    store_ratio(h->requested_pitch_ratio_bits, std::pow(2.0f, st / 12.0f));
    return BOILEDEGG_OK;
}

float boiledegg_get_time_ratio(const boiledegg_handle* h) {
    return h ? load_ratio(h->requested_time_ratio_bits) : 0.0f;
}

float boiledegg_get_pitch_ratio(const boiledegg_handle* h) {
    return h ? load_ratio(h->requested_pitch_ratio_bits) : 0.0f;
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
    if (frames == 0) return event_count == 0 ? BOILEDEGG_OK : BOILEDEGG_INVALID_ARGUMENT;
    if (frames > h->max_block_size || !valid_planar_input(h, input) || !valid_planar_output(h, output)) {
        return BOILEDEGG_INVALID_ARGUMENT;
    }
    if (event_count > 0 && !events) return BOILEDEGG_INVALID_ARGUMENT;

    uint32_t previous_offset = 0;
    for (uint32_t i = 0; i < event_count; ++i) {
        const boiledegg_result event_result = validate_event(events[i], frames);
        if (event_result != BOILEDEGG_OK) return event_result;
        if (i > 0 && events[i].sample_offset < previous_offset) return BOILEDEGG_INVALID_ARGUMENT;
        previous_offset = events[i].sample_offset;
    }

    if (!enter_mode(h, processing_mode::realtime)) return BOILEDEGG_INVALID_STATE;
    const float requested_time = load_ratio(h->requested_time_ratio_bits);
    if (std::abs(requested_time - kRealtimeTimeRatio) > kRatioEpsilon) return BOILEDEGG_UNSUPPORTED_MODE;

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
            const boiledegg_result event_result = apply_event(h, events[event_index]);
            if (event_result != BOILEDEGG_OK) return event_result;
            ++event_index;
        }
    }

    if (cursor < frames) {
        const boiledegg_result chunk_result = process_realtime_chunk(h, input, output, cursor, frames - cursor);
        if (chunk_result != BOILEDEGG_OK && chunk_result != BOILEDEGG_REALTIME_UNDERRUN) return chunk_result;
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
    out_info->realtime_tail_frames = h->realtime_latency_frames;
    out_info->parameter_quantum_frames = h->parameter_quantum_frames;
    out_info->capabilities = BOILEDEGG_CAP_PARALLEL_INSTANCES |
                             BOILEDEGG_CAP_CONTROL_THREAD_PARAMETERS |
                             BOILEDEGG_CAP_FIXED_REALTIME_IO |
                             BOILEDEGG_CAP_SAMPLE_OFFSET_EVENTS |
                             BOILEDEGG_CAP_IN_PLACE_REALTIME_IO;
    return BOILEDEGG_OK;
}

uint32_t boiledegg_input_latency_frames(const boiledegg_handle* h) {
    return h ? h->engine.input_latency_frames() : 0;
}

} // extern C
