#include <boiled_egg/boiled_egg.h>
#include <clap/clap.h>

#include <algorithm>
#include <atomic>
#include <bit>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <new>

namespace {

constexpr clap_id kPitchParamId = 0x42450001u;
constexpr uint32_t kStateMagic = 0x42454747u; // "BEGG"
constexpr uint32_t kStateVersion = 1u;

uint32_t float_bits(float value) noexcept { return std::bit_cast<uint32_t>(value); }
float bits_float(uint32_t bits) noexcept { return std::bit_cast<float>(bits); }

struct Plugin {
    static_assert(std::atomic<uint32_t>::is_always_lock_free,
                  "CLAP adapter requires lock-free 32-bit atomics");

    clap_plugin_t clap{};
    const clap_host_t* host = nullptr;
    const clap_host_params_t* host_params = nullptr;
    boiledegg_handle* core = nullptr;
    boiledegg_runtime_info runtime{};
    std::atomic<uint32_t> pitch_semitones_bits{float_bits(0.0f)};

    explicit Plugin(const clap_host_t* host_in) : host(host_in) {
        runtime.struct_size = sizeof(runtime);
    }
};

Plugin* self(const clap_plugin_t* plugin) noexcept {
    return static_cast<Plugin*>(plugin->plugin_data);
}

float requested_pitch(const Plugin* plugin) noexcept {
    return bits_float(plugin->pitch_semitones_bits.load(std::memory_order_relaxed));
}

bool set_pitch(Plugin* plugin, double value) noexcept {
    if (!std::isfinite(value) || value < -24.0 || value > 24.0) return false;
    const float semitones = static_cast<float>(value);
    plugin->pitch_semitones_bits.store(float_bits(semitones), std::memory_order_relaxed);
    return !plugin->core || boiledegg_set_pitch_semitones(plugin->core, semitones) == BOILEDEGG_OK;
}

bool is_global_pitch_event(const clap_event_header_t* header) noexcept {
    if (!header || header->space_id != CLAP_CORE_EVENT_SPACE_ID ||
        header->type != CLAP_EVENT_PARAM_VALUE ||
        header->size < sizeof(clap_event_param_value_t)) return false;
    const auto* event = reinterpret_cast<const clap_event_param_value_t*>(header);
    return event->param_id == kPitchParamId && event->note_id < 0 &&
           event->port_index < 0 && event->channel < 0 && event->key < 0;
}

bool apply_param_header(Plugin* plugin, const clap_event_header_t* header) noexcept {
    if (!is_global_pitch_event(header)) return true;
    const auto* event = reinterpret_cast<const clap_event_param_value_t*>(header);
    return set_pitch(plugin, event->value);
}

bool process_range(Plugin* plugin, const clap_process_t* process, uint32_t offset, uint32_t frames) noexcept {
    if (frames == 0) return true;
    const auto& input = process->audio_inputs[0];
    auto& output = process->audio_outputs[0];
    const float* in[2] = {input.data32[0] + offset, input.data32[1] + offset};
    float* out[2] = {output.data32[0] + offset, output.data32[1] + offset};
    const auto result = boiledegg_process_realtime(plugin->core, in, out, frames, nullptr, 0);
    return result == BOILEDEGG_OK || result == BOILEDEGG_REALTIME_UNDERRUN;
}

bool validate_audio(const clap_process_t* process) noexcept {
    if (!process || process->audio_inputs_count != 1 || process->audio_outputs_count != 1 ||
        !process->audio_inputs || !process->audio_outputs) return false;
    const auto& input = process->audio_inputs[0];
    const auto& output = process->audio_outputs[0];
    return input.channel_count == 2 && output.channel_count == 2 &&
           input.data32 && output.data32 && input.data32[0] && input.data32[1] &&
           output.data32[0] && output.data32[1];
}

void flush_param_list(Plugin* plugin, const clap_input_events_t* input_events) noexcept {
    if (!input_events) return;
    const uint32_t count = input_events->size(input_events);
    for (uint32_t i = 0; i < count; ++i) {
        (void)apply_param_header(plugin, input_events->get(input_events, i));
    }
}

bool stream_write_all(const clap_ostream_t* stream, const void* source, uint64_t size) noexcept {
    if (!stream || !stream->write) return false;
    const auto* bytes = static_cast<const uint8_t*>(source);
    uint64_t offset = 0;
    while (offset < size) {
        const int64_t written = stream->write(stream, bytes + offset, size - offset);
        if (written <= 0) return false;
        offset += static_cast<uint64_t>(written);
    }
    return true;
}

bool stream_read_all(const clap_istream_t* stream, void* destination, uint64_t size) noexcept {
    if (!stream || !stream->read) return false;
    auto* bytes = static_cast<uint8_t*>(destination);
    uint64_t offset = 0;
    while (offset < size) {
        const int64_t read = stream->read(stream, bytes + offset, size - offset);
        if (read <= 0) return false;
        offset += static_cast<uint64_t>(read);
    }
    return true;
}

struct SavedState {
    uint32_t magic;
    uint32_t version;
    float pitch_semitones;
    uint32_t reserved;
};
static_assert(sizeof(SavedState) == 16);

bool CLAP_ABI plugin_init(const clap_plugin_t* clap) {
    auto* plugin = self(clap);
    if (!plugin || !plugin->host || !clap_version_is_compatible(plugin->host->clap_version)) return false;
    if (plugin->host->get_extension) {
        plugin->host_params = static_cast<const clap_host_params_t*>(
            plugin->host->get_extension(plugin->host, CLAP_EXT_PARAMS));
    }
    return true;
}

void CLAP_ABI plugin_destroy(const clap_plugin_t* clap) {
    auto* plugin = self(clap);
    if (!plugin) return;
    boiledegg_destroy(plugin->core);
    plugin->core = nullptr;
    delete plugin;
}

bool CLAP_ABI plugin_activate(
    const clap_plugin_t* clap,
    double sample_rate,
    uint32_t /*min_frames_count*/,
    uint32_t max_frames_count) {
    auto* plugin = self(clap);
    if (!plugin || plugin->core || !std::isfinite(sample_rate) || max_frames_count == 0) return false;
    const long rounded_rate = std::lround(sample_rate);
    if (rounded_rate < 8000 || rounded_rate > 384000 ||
        std::abs(sample_rate - static_cast<double>(rounded_rate)) > 0.01) return false;

    auto config = boiledegg_default_config(static_cast<uint32_t>(rounded_rate), 2);
    config.max_block_size = max_frames_count;
    boiledegg_result result = BOILEDEGG_INTERNAL_ERROR;
    plugin->core = boiledegg_create(&config, &result);
    if (!plugin->core || result != BOILEDEGG_OK) {
        plugin->core = nullptr;
        return false;
    }
    if (boiledegg_set_pitch_semitones(plugin->core, requested_pitch(plugin)) != BOILEDEGG_OK ||
        boiledegg_get_runtime_info(plugin->core, &plugin->runtime) != BOILEDEGG_OK) {
        boiledegg_destroy(plugin->core);
        plugin->core = nullptr;
        return false;
    }
    return true;
}

void CLAP_ABI plugin_deactivate(const clap_plugin_t* clap) {
    auto* plugin = self(clap);
    if (!plugin) return;
    boiledegg_destroy(plugin->core);
    plugin->core = nullptr;
    plugin->runtime = {};
    plugin->runtime.struct_size = sizeof(plugin->runtime);
}

bool CLAP_ABI plugin_start_processing(const clap_plugin_t* clap) {
    return self(clap) && self(clap)->core;
}

void CLAP_ABI plugin_stop_processing(const clap_plugin_t* /*clap*/) {}

void CLAP_ABI plugin_reset(const clap_plugin_t* clap) {
    auto* plugin = self(clap);
    if (plugin && plugin->core) (void)boiledegg_reset(plugin->core);
}

clap_process_status CLAP_ABI plugin_process(const clap_plugin_t* clap, const clap_process_t* process) {
    auto* plugin = self(clap);
    if (!plugin || !plugin->core || !process) return CLAP_PROCESS_ERROR;

    if (process->frames_count == 0) {
        flush_param_list(plugin, process->in_events);
        return CLAP_PROCESS_CONTINUE;
    }
    if (process->frames_count > plugin->runtime.max_block_size || !validate_audio(process)) {
        return CLAP_PROCESS_ERROR;
    }
    process->audio_outputs[0].constant_mask = 0;

    uint32_t cursor = 0;
    const uint32_t event_count = process->in_events ? process->in_events->size(process->in_events) : 0;
    for (uint32_t i = 0; i < event_count; ++i) {
        const clap_event_header_t* header = process->in_events->get(process->in_events, i);
        if (!is_global_pitch_event(header)) continue;
        if (header->time > process->frames_count || header->time < cursor) return CLAP_PROCESS_ERROR;
        if (header->time > cursor && !process_range(plugin, process, cursor, header->time - cursor)) {
            return CLAP_PROCESS_ERROR;
        }
        if (!apply_param_header(plugin, header)) return CLAP_PROCESS_ERROR;
        cursor = header->time;
    }
    if (cursor < process->frames_count &&
        !process_range(plugin, process, cursor, process->frames_count - cursor)) {
        return CLAP_PROCESS_ERROR;
    }
    return CLAP_PROCESS_CONTINUE;
}

uint32_t CLAP_ABI audio_ports_count(const clap_plugin_t* /*plugin*/, bool /*is_input*/) { return 1; }

bool CLAP_ABI audio_ports_get(
    const clap_plugin_t* /*plugin*/, uint32_t index, bool is_input, clap_audio_port_info_t* info) {
    if (!info || index != 0) return false;
    info->id = 0;
    std::snprintf(info->name, sizeof(info->name), "%s", is_input ? "Stereo Input" : "Stereo Output");
    info->flags = CLAP_AUDIO_PORT_IS_MAIN;
    info->channel_count = 2;
    info->port_type = CLAP_PORT_STEREO;
    info->in_place_pair = 0;
    return true;
}

uint32_t CLAP_ABI params_count(const clap_plugin_t* /*plugin*/) { return 1; }

bool CLAP_ABI params_get_info(const clap_plugin_t* /*plugin*/, uint32_t index, clap_param_info_t* info) {
    if (!info || index != 0) return false;
    std::memset(info, 0, sizeof(*info));
    info->id = kPitchParamId;
    info->flags = CLAP_PARAM_IS_AUTOMATABLE | CLAP_PARAM_REQUIRES_PROCESS;
    info->cookie = nullptr;
    std::snprintf(info->name, sizeof(info->name), "%s", "Pitch");
    info->module[0] = '\0';
    info->min_value = -24.0;
    info->max_value = 24.0;
    info->default_value = 0.0;
    return true;
}

bool CLAP_ABI params_get_value(const clap_plugin_t* clap, clap_id param_id, double* out_value) {
    if (!out_value || param_id != kPitchParamId) return false;
    *out_value = requested_pitch(self(clap));
    return true;
}

bool CLAP_ABI params_value_to_text(
    const clap_plugin_t* /*plugin*/, clap_id param_id, double value,
    char* out_buffer, uint32_t capacity) {
    if (param_id != kPitchParamId || !out_buffer || capacity == 0 || !std::isfinite(value)) return false;
    const int written = std::snprintf(out_buffer, capacity, "%.2f st", value);
    return written >= 0 && static_cast<uint32_t>(written) < capacity;
}

bool CLAP_ABI params_text_to_value(
    const clap_plugin_t* /*plugin*/, clap_id param_id, const char* text, double* out_value) {
    if (param_id != kPitchParamId || !text || !out_value) return false;
    char* end = nullptr;
    const double parsed = std::strtod(text, &end);
    if (end == text || !std::isfinite(parsed) || parsed < -24.0 || parsed > 24.0) return false;
    *out_value = parsed;
    return true;
}

void CLAP_ABI params_flush(
    const clap_plugin_t* clap, const clap_input_events_t* input, const clap_output_events_t* /*output*/) {
    flush_param_list(self(clap), input);
}

uint32_t CLAP_ABI latency_get(const clap_plugin_t* clap) {
    const auto* plugin = self(clap);
    return plugin && plugin->core ? plugin->runtime.realtime_latency_frames : 0;
}

uint32_t CLAP_ABI tail_get(const clap_plugin_t* clap) {
    const auto* plugin = self(clap);
    return plugin && plugin->core ? plugin->runtime.realtime_tail_frames : 0;
}

bool CLAP_ABI state_save(const clap_plugin_t* clap, const clap_ostream_t* stream) {
    const SavedState state{kStateMagic, kStateVersion, requested_pitch(self(clap)), 0};
    return stream_write_all(stream, &state, sizeof(state));
}

bool CLAP_ABI state_load(const clap_plugin_t* clap, const clap_istream_t* stream) {
    auto* plugin = self(clap);
    SavedState state{};
    if (!stream_read_all(stream, &state, sizeof(state)) || state.magic != kStateMagic ||
        state.version != kStateVersion || !set_pitch(plugin, state.pitch_semitones)) return false;
    if (plugin->host_params && plugin->host_params->rescan) {
        plugin->host_params->rescan(plugin->host, CLAP_PARAM_RESCAN_VALUES);
    }
    return true;
}

const clap_plugin_audio_ports_t kAudioPorts{audio_ports_count, audio_ports_get};
const clap_plugin_params_t kParams{
    params_count, params_get_info, params_get_value, params_value_to_text, params_text_to_value, params_flush};
const clap_plugin_latency_t kLatency{latency_get};
const clap_plugin_tail_t kTail{tail_get};
const clap_plugin_state_t kState{state_save, state_load};

const void* CLAP_ABI plugin_get_extension(const clap_plugin_t* /*clap*/, const char* id) {
    if (!id) return nullptr;
    if (std::strcmp(id, CLAP_EXT_AUDIO_PORTS) == 0) return &kAudioPorts;
    if (std::strcmp(id, CLAP_EXT_PARAMS) == 0) return &kParams;
    if (std::strcmp(id, CLAP_EXT_LATENCY) == 0) return &kLatency;
    if (std::strcmp(id, CLAP_EXT_TAIL) == 0) return &kTail;
    if (std::strcmp(id, CLAP_EXT_STATE) == 0) return &kState;
    return nullptr;
}

void CLAP_ABI plugin_on_main_thread(const clap_plugin_t* /*clap*/) {}

const char* const kFeatures[] = {
    CLAP_PLUGIN_FEATURE_AUDIO_EFFECT,
    CLAP_PLUGIN_FEATURE_PITCH_SHIFTER,
    CLAP_PLUGIN_FEATURE_STEREO,
    nullptr,
};

const clap_plugin_descriptor_t kDescriptor{
    CLAP_VERSION_INIT,
    "io.github.zkamiyama.boiled-egg",
    "boiled egg",
    "zkamiyama",
    "https://github.com/zkamiyama/boiled-egg",
    "",
    "https://github.com/zkamiyama/boiled-egg/issues",
    "0.1.2",
    "Realtime stereo pitch shifter research plugin",
    kFeatures,
};

uint32_t CLAP_ABI factory_count(const clap_plugin_factory_t* /*factory*/) { return 1; }

const clap_plugin_descriptor_t* CLAP_ABI factory_descriptor(
    const clap_plugin_factory_t* /*factory*/, uint32_t index) {
    return index == 0 ? &kDescriptor : nullptr;
}

const clap_plugin_t* CLAP_ABI factory_create(
    const clap_plugin_factory_t* /*factory*/, const clap_host_t* host, const char* plugin_id) {
    if (!host || !plugin_id || std::strcmp(plugin_id, kDescriptor.id) != 0 ||
        !clap_version_is_compatible(host->clap_version)) return nullptr;
    auto* plugin = new (std::nothrow) Plugin(host);
    if (!plugin) return nullptr;
    plugin->clap.desc = &kDescriptor;
    plugin->clap.plugin_data = plugin;
    plugin->clap.init = plugin_init;
    plugin->clap.destroy = plugin_destroy;
    plugin->clap.activate = plugin_activate;
    plugin->clap.deactivate = plugin_deactivate;
    plugin->clap.start_processing = plugin_start_processing;
    plugin->clap.stop_processing = plugin_stop_processing;
    plugin->clap.reset = plugin_reset;
    plugin->clap.process = plugin_process;
    plugin->clap.get_extension = plugin_get_extension;
    plugin->clap.on_main_thread = plugin_on_main_thread;
    return &plugin->clap;
}

const clap_plugin_factory_t kFactory{factory_count, factory_descriptor, factory_create};

bool CLAP_ABI entry_init(const char* /*plugin_path*/) { return true; }
void CLAP_ABI entry_deinit() {}
const void* CLAP_ABI entry_get_factory(const char* factory_id) {
    return factory_id && std::strcmp(factory_id, CLAP_PLUGIN_FACTORY_ID) == 0 ? &kFactory : nullptr;
}

} // namespace

extern "C" CLAP_EXPORT const clap_plugin_entry_t clap_entry = {
    CLAP_VERSION_INIT,
    entry_init,
    entry_deinit,
    entry_get_factory,
};
