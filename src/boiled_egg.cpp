#include <boiled_egg/boiled_egg.h>
#include "engine.hpp"

#include <cmath>
#include <new>

struct boiledegg_handle {
    boiled_egg::detail::Engine engine;
    explicit boiledegg_handle(const boiledegg_config& c) : engine(c) {}
};

static bool valid_config(const boiledegg_config& c) {
    if (c.struct_size < sizeof(boiledegg_config) || c.abi_version != BOILEDEGG_ABI_VERSION) return false;
    if (c.sample_rate < 8000 || c.sample_rate > 384000) return false;
    if (c.channels == 0 || c.channels > 32) return false;
    if (c.max_block_size == 0 || c.max_block_size > 65536) return false;
    if (c.window_frames < 128 || (c.window_frames % 2u) != 0) return false;
    if (c.search_frames >= c.window_frames / 2u) return false;
    if (c.fifo_frames < c.window_frames * 8u + c.max_block_size * 2u) return false;
    return true;
}

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
const char* boiledegg_version_string(void) { return "0.1.0-research-baseline"; }

const char* boiledegg_result_string(boiledegg_result r) {
    switch (r) {
        case BOILEDEGG_OK: return "ok";
        case BOILEDEGG_INVALID_ARGUMENT: return "invalid argument";
        case BOILEDEGG_OUT_OF_MEMORY: return "out of memory";
        case BOILEDEGG_BUFFER_FULL: return "buffer full";
        case BOILEDEGG_END_OF_STREAM: return "end of stream";
        case BOILEDEGG_INTERNAL_ERROR: return "internal error";
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
boiledegg_result boiledegg_reset(boiledegg_handle* h) { return h ? h->engine.reset() : BOILEDEGG_INVALID_ARGUMENT; }
boiledegg_result boiledegg_set_time_ratio(boiledegg_handle* h, float r) { return h ? h->engine.set_time_ratio(r) : BOILEDEGG_INVALID_ARGUMENT; }
boiledegg_result boiledegg_set_pitch_ratio(boiledegg_handle* h, float r) { return h ? h->engine.set_pitch_ratio(r) : BOILEDEGG_INVALID_ARGUMENT; }
boiledegg_result boiledegg_set_pitch_semitones(boiledegg_handle* h, float st) {
    if (!h || !std::isfinite(st) || st < -24.0f || st > 24.0f) return BOILEDEGG_INVALID_ARGUMENT;
    return h->engine.set_pitch_ratio(std::pow(2.0f, st / 12.0f));
}
float boiledegg_get_time_ratio(const boiledegg_handle* h) { return h ? h->engine.time_ratio() : 0.0f; }
float boiledegg_get_pitch_ratio(const boiledegg_handle* h) { return h ? h->engine.pitch_ratio() : 0.0f; }

boiledegg_result boiledegg_push(boiledegg_handle* h, const float* const* in, uint32_t frames, uint32_t* accepted) {
    if (!h || !accepted) return BOILEDEGG_INVALID_ARGUMENT;
    return h->engine.push(in, frames, *accepted);
}
uint32_t boiledegg_available(const boiledegg_handle* h) { return h ? h->engine.available() : 0; }
boiledegg_result boiledegg_pull(boiledegg_handle* h, float* const* out, uint32_t cap, uint32_t* produced) {
    if (!h || !produced) return BOILEDEGG_INVALID_ARGUMENT;
    return h->engine.pull(out, cap, *produced);
}
boiledegg_result boiledegg_flush(boiledegg_handle* h) { return h ? h->engine.flush() : BOILEDEGG_INVALID_ARGUMENT; }
int boiledegg_is_drained(const boiledegg_handle* h) { return h && h->engine.drained() ? 1 : 0; }
uint32_t boiledegg_input_latency_frames(const boiledegg_handle* h) { return h ? h->engine.input_latency_frames() : 0; }

} // extern C
