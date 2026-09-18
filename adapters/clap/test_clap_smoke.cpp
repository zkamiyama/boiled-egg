#include <clap/clap.h>

#include <algorithm>
#include <array>
#include <cmath>
#include <cstdint>
#include <cstring>
#include <dlfcn.h>
#include <iostream>

namespace {

const void* CLAP_ABI host_get_extension(const clap_host_t*, const char*) { return nullptr; }
void CLAP_ABI host_request_restart(const clap_host_t*) {}
void CLAP_ABI host_request_process(const clap_host_t*) {}
void CLAP_ABI host_request_callback(const clap_host_t*) {}

struct InputEvents {
    clap_input_events_t iface{};
    std::array<const clap_event_header_t*, 4> entries{};
    uint32_t count = 0;

    InputEvents() {
        iface.ctx = this;
        iface.size = [](const clap_input_events_t* list) -> uint32_t {
            return static_cast<const InputEvents*>(list->ctx)->count;
        };
        iface.get = [](const clap_input_events_t* list, uint32_t index) -> const clap_event_header_t* {
            const auto* self = static_cast<const InputEvents*>(list->ctx);
            return index < self->count ? self->entries[index] : nullptr;
        };
    }
};

struct MemoryOutput {
    clap_ostream_t stream{};
    std::array<uint8_t, 128> bytes{};
    uint64_t position = 0;

    MemoryOutput() {
        stream.ctx = this;
        stream.write = [](const clap_ostream_t* stream, const void* data, uint64_t size) -> int64_t {
            auto* self = static_cast<MemoryOutput*>(stream->ctx);
            const uint64_t available = self->bytes.size() - self->position;
            const uint64_t n = std::min(size, available);
            if (n == 0) return -1;
            std::memcpy(self->bytes.data() + self->position, data, static_cast<size_t>(n));
            self->position += n;
            return static_cast<int64_t>(n);
        };
    }
};

struct MemoryInput {
    clap_istream_t stream{};
    const uint8_t* bytes = nullptr;
    uint64_t size = 0;
    uint64_t position = 0;

    MemoryInput(const uint8_t* data, uint64_t data_size) : bytes(data), size(data_size) {
        stream.ctx = this;
        stream.read = [](const clap_istream_t* stream, void* data, uint64_t requested) -> int64_t {
            auto* self = static_cast<MemoryInput*>(stream->ctx);
            const uint64_t available = self->size - self->position;
            const uint64_t n = std::min(requested, available);
            if (n == 0) return 0;
            std::memcpy(data, self->bytes + self->position, static_cast<size_t>(n));
            self->position += n;
            return static_cast<int64_t>(n);
        };
    }
};

bool check(bool condition, const char* message) {
    if (!condition) std::cerr << message << '\n';
    return condition;
}

} // namespace

int main(int argc, char** argv) {
    if (argc != 2) return 100;
    void* library = dlopen(argv[1], RTLD_NOW | RTLD_LOCAL);
    if (!check(library != nullptr, dlerror() ? dlerror() : "dlopen failed")) return 1;

    auto* entry = static_cast<const clap_plugin_entry_t*>(dlsym(library, "clap_entry"));
    if (!check(entry != nullptr, "clap_entry not exported")) return 2;
    if (!check(entry->init(argv[1]), "entry init failed")) return 3;

    const auto* factory = static_cast<const clap_plugin_factory_t*>(
        entry->get_factory(CLAP_PLUGIN_FACTORY_ID));
    if (!check(factory != nullptr && factory->get_plugin_count(factory) == 1, "factory failed")) return 4;
    const auto* descriptor = factory->get_plugin_descriptor(factory, 0);
    if (!check(descriptor != nullptr && descriptor->id != nullptr, "descriptor failed")) return 5;

    clap_host_t host{
        CLAP_VERSION_INIT,
        nullptr,
        "boiled egg test host",
        "zkamiyama",
        "https://github.com/zkamiyama/boiled-egg",
        "0.1",
        host_get_extension,
        host_request_restart,
        host_request_process,
        host_request_callback,
    };

    const clap_plugin_t* plugin = factory->create_plugin(factory, &host, descriptor->id);
    if (!check(plugin != nullptr && plugin->init(plugin), "plugin create/init failed")) return 6;

    const auto* ports = static_cast<const clap_plugin_audio_ports_t*>(
        plugin->get_extension(plugin, CLAP_EXT_AUDIO_PORTS));
    const auto* params = static_cast<const clap_plugin_params_t*>(
        plugin->get_extension(plugin, CLAP_EXT_PARAMS));
    const auto* latency = static_cast<const clap_plugin_latency_t*>(
        plugin->get_extension(plugin, CLAP_EXT_LATENCY));
    const auto* tail = static_cast<const clap_plugin_tail_t*>(
        plugin->get_extension(plugin, CLAP_EXT_TAIL));
    const auto* state = static_cast<const clap_plugin_state_t*>(
        plugin->get_extension(plugin, CLAP_EXT_STATE));
    if (!check(ports && params && latency && tail && state, "required extensions missing")) return 7;

    clap_audio_port_info_t port_info{};
    if (!check(ports->count(plugin, true) == 1 && ports->count(plugin, false) == 1 &&
               ports->get(plugin, 0, true, &port_info) && port_info.channel_count == 2 &&
               port_info.port_type && std::strcmp(port_info.port_type, CLAP_PORT_STEREO) == 0,
               "stereo audio port contract failed")) return 8;

    clap_param_info_t param_info{};
    if (!check(params->count(plugin) == 12 && params->get_info(plugin, 0, &param_info) &&
               param_info.min_value == -24.0 && param_info.max_value == 24.0,
               "parameter contract failed")) return 9;

    if (!check(plugin->activate(plugin, 48000.0, 1, 128), "activation failed")) return 10;
    if (!check(latency->get(plugin) > 0 && tail->get(plugin) > 0, "latency/tail missing")) return 11;
    if (!check(plugin->start_processing(plugin), "start_processing failed")) return 12;

    std::array<float, 128> left{}, right{}, out_left{}, out_right{};
    for (uint32_t i = 0; i < left.size(); ++i) {
        left[i] = static_cast<float>(0.1 * std::sin(2.0 * 3.141592653589793 * 440.0 * i / 48000.0));
        right[i] = left[i] * 0.8f;
    }
    float* input_channels[2] = {left.data(), right.data()};
    float* output_channels[2] = {out_left.data(), out_right.data()};
    clap_audio_buffer_t input_buffer{input_channels, nullptr, 2, 0, 0};
    clap_audio_buffer_t output_buffer{output_channels, nullptr, 2, 0, 0};

    clap_event_param_value_t pitch_event{};
    pitch_event.header.size = sizeof(pitch_event);
    pitch_event.header.time = 32;
    pitch_event.header.space_id = CLAP_CORE_EVENT_SPACE_ID;
    pitch_event.header.type = CLAP_EVENT_PARAM_VALUE;
    pitch_event.param_id = param_info.id;
    pitch_event.cookie = nullptr;
    pitch_event.note_id = -1;
    pitch_event.port_index = -1;
    pitch_event.channel = -1;
    pitch_event.key = -1;
    pitch_event.value = 5.0;
    InputEvents events;
    events.entries[0] = &pitch_event.header;
    events.count = 1;

    clap_process_t process{};
    process.steady_time = 0;
    process.frames_count = 128;
    process.audio_inputs = &input_buffer;
    process.audio_outputs = &output_buffer;
    process.audio_inputs_count = 1;
    process.audio_outputs_count = 1;
    process.in_events = &events.iface;
    if (!check(plugin->process(plugin, &process) == CLAP_PROCESS_CONTINUE, "process failed")) return 13;

    double value = 0.0;
    if (!check(params->get_value(plugin, param_info.id, &value) && std::abs(value - 5.0) < 1e-9,
               "automation value not published")) return 14;

    // CLAP reset is an audio-thread operation and must retain parameter values.
    plugin->reset(plugin);
    if (!check(params->get_value(plugin, param_info.id, &value) && std::abs(value - 5.0) < 1e-9,
               "reset did not retain parameter value")) return 15;

    // Exercise the separate params.flush path while active.
    pitch_event.header.time = 0;
    pitch_event.value = -3.0;
    params->flush(plugin, &events.iface, nullptr);
    if (!check(params->get_value(plugin, param_info.id, &value) && std::abs(value + 3.0) < 1e-9,
               "params flush failed")) return 16;

    MemoryOutput saved;
    if (!check(state->save(plugin, &saved.stream) && saved.position > 0, "state save failed")) return 17;
    pitch_event.value = 9.0;
    params->flush(plugin, &events.iface, nullptr);
    MemoryInput restore(saved.bytes.data(), saved.position);
    if (!check(state->load(plugin, &restore.stream), "state load failed")) return 18;
    if (!check(params->get_value(plugin, param_info.id, &value) && std::abs(value + 3.0) < 1e-9,
               "state roundtrip mismatch")) return 19;

    plugin->stop_processing(plugin);
    plugin->deactivate(plugin);
    plugin->destroy(plugin);
    entry->deinit();
    dlclose(library);
    std::cout << "CLAP adapter smoke test passed\n";
    return 0;
}
