#include <boiled_egg/boiled_egg.h>

#include <algorithm>
#include <cmath>
#include <cstdint>
#include <iostream>
#include <limits>
#include <vector>

namespace {

boiledegg_handle* make_handle(uint32_t block = 128, uint32_t sample_rate = 48000) {
    auto cfg = boiledegg_default_config(sample_rate, 1);
    cfg.max_block_size = block;
    boiledegg_result r = BOILEDEGG_INTERNAL_ERROR;
    auto* h = boiledegg_create(&cfg, &r);
    return r == BOILEDEGG_OK ? h : nullptr;
}

bool test_runtime_info() {
    auto* h = make_handle();
    if (!h) return false;
    boiledegg_runtime_info info{};
    info.struct_size = sizeof(info);
    const auto r = boiledegg_get_runtime_info(h, &info);
    const uint32_t required = BOILEDEGG_CAP_PARALLEL_INSTANCES |
                              BOILEDEGG_CAP_CONTROL_THREAD_PARAMETERS |
                              BOILEDEGG_CAP_FIXED_REALTIME_IO |
                              BOILEDEGG_CAP_SAMPLE_OFFSET_EVENTS |
                              BOILEDEGG_CAP_IN_PLACE_REALTIME_IO |
                              BOILEDEGG_CAP_REALTIME_RESET |
                              BOILEDEGG_CAP_HARD_REALTIME_PROCESSING |
                              BOILEDEGG_CAP_PARAMETER_ONLY_FLUSH;
    const bool ok = r == BOILEDEGG_OK && info.sample_rate == 48000 && info.channels == 1 &&
                    info.max_block_size == 128 && info.realtime_latency_frames > 0 &&
                    info.realtime_tail_frames == info.realtime_latency_frames &&
                    info.parameter_quantum_frames > 1 && (info.capabilities & required) == required &&
                    (info.capabilities & BOILEDEGG_CAP_SAMPLE_ACCURATE_AUTOMATION) == 0;
    boiledegg_destroy(h);
    return ok;
}

bool test_identity_latency_and_variable_blocks() {
    auto* h = make_handle(257);
    if (!h) return false;
    boiledegg_runtime_info info{};
    info.struct_size = sizeof(info);
    if (boiledegg_get_runtime_info(h, &info) != BOILEDEGG_OK) return false;

    constexpr uint32_t signal_frames = 4096;
    const uint32_t total = signal_frames + info.realtime_tail_frames + 512;
    std::vector<float> input(total, 0.0f), output(total, 0.0f);
    for (uint32_t i = 0; i < signal_frames; ++i) {
        input[i] = 0.15f * std::sin(2.0 * 3.141592653589793 * 997.0 * static_cast<double>(i) / 48000.0);
    }
    input[0] += 0.5f;

    uint32_t pos = 0;
    uint32_t pattern[] = {31, 64, 127, 257, 19, 251, 89};
    uint32_t p = 0;
    while (pos < total) {
        const uint32_t n = std::min<uint32_t>(pattern[p++ % 7], total - pos);
        const float* in[1] = {input.data() + pos};
        float* out[1] = {output.data() + pos};
        const auto r = boiledegg_process_realtime(h, in, out, n, nullptr, 0);
        if (r != BOILEDEGG_OK) {
            std::cerr << "realtime identity returned " << boiledegg_result_string(r) << " at " << pos << "\n";
            boiledegg_destroy(h);
            return false;
        }
        pos += n;
    }

    for (uint32_t i = 0; i < info.realtime_latency_frames; ++i) {
        if (std::abs(output[i]) > 1.0e-7f) {
            std::cerr << "nonzero before reported latency at " << i << "\n";
            boiledegg_destroy(h);
            return false;
        }
    }
    double max_error = 0.0;
    for (uint32_t i = 0; i < signal_frames; ++i) {
        max_error = std::max(max_error, std::abs(static_cast<double>(output[info.realtime_latency_frames + i] - input[i])));
    }
    boiledegg_destroy(h);
    if (max_error > 1.0e-5) {
        std::cerr << "identity latency alignment error " << max_error << "\n";
        return false;
    }
    return true;
}

bool test_mode_contract() {
    auto* h = make_handle();
    if (!h) return false;
    std::vector<float> x(128, 0.0f), y(128, 0.0f);
    const float* in[1] = {x.data()};
    float* out[1] = {y.data()};
    if (boiledegg_process_realtime(h, in, out, 128, nullptr, 0) != BOILEDEGG_OK) return false;
    uint32_t accepted = 0;
    if (boiledegg_push(h, in, 128, &accepted) != BOILEDEGG_INVALID_STATE) return false;
    if (boiledegg_set_time_ratio(h, 1.2f) != BOILEDEGG_UNSUPPORTED_MODE) return false;
    if (boiledegg_reset(h) != BOILEDEGG_OK) return false;
    if (boiledegg_set_time_ratio(h, 1.2f) != BOILEDEGG_OK) return false;
    if (boiledegg_push(h, in, 128, &accepted) != BOILEDEGG_OK || accepted != 128) return false;
    if (boiledegg_process_realtime(h, in, out, 128, nullptr, 0) != BOILEDEGG_INVALID_STATE) return false;
    boiledegg_destroy(h);
    return true;
}

bool test_events_and_in_place() {
    auto* h = make_handle();
    if (!h) return false;
    std::vector<float> x(128, 0.1f);
    const float* in[1] = {x.data()};
    float* out[1] = {x.data()};
    boiledegg_parameter_event events[3] = {
        {sizeof(boiledegg_parameter_event), 0, BOILEDEGG_PARAMETER_PITCH_SEMITONES, 0.0f},
        {sizeof(boiledegg_parameter_event), 32, BOILEDEGG_PARAMETER_PITCH_SEMITONES, 3.0f},
        {sizeof(boiledegg_parameter_event), 96, BOILEDEGG_PARAMETER_PITCH_RATIO, 1.0f},
    };
    const auto r = boiledegg_process_realtime(h, in, out, 128, events, 3);
    if (r != BOILEDEGG_OK || std::abs(boiledegg_get_pitch_ratio(h) - 1.0f) > 1.0e-6f) return false;

    boiledegg_parameter_event bad[2] = {
        {sizeof(boiledegg_parameter_event), 50, BOILEDEGG_PARAMETER_PITCH_RATIO, 1.0f},
        {sizeof(boiledegg_parameter_event), 40, BOILEDEGG_PARAMETER_PITCH_RATIO, 1.0f},
    };
    if (boiledegg_process_realtime(h, in, out, 128, bad, 2) != BOILEDEGG_INVALID_ARGUMENT) return false;
    boiledegg_parameter_event time_event{sizeof(boiledegg_parameter_event), 0, BOILEDEGG_PARAMETER_TIME_RATIO, 1.1f};
    if (boiledegg_process_realtime(h, in, out, 128, &time_event, 1) != BOILEDEGG_UNSUPPORTED_MODE) return false;
    boiledegg_destroy(h);
    return true;
}

bool test_parameter_only_flush_and_state() {
    auto* h = make_handle(64);
    if (!h) return false;

    boiledegg_parameter_event pitch{
        sizeof(boiledegg_parameter_event), 0, BOILEDEGG_PARAMETER_PITCH_SEMITONES, 5.0f};
    if (boiledegg_process_realtime(h, nullptr, nullptr, 0, &pitch, 1) != BOILEDEGG_OK) return false;
    const float expected = std::pow(2.0f, 5.0f / 12.0f);
    if (std::abs(boiledegg_get_pitch_ratio(h) - expected) > 1.0e-6f) return false;

    // A parameter-only flush must not select realtime mode.
    if (boiledegg_set_time_ratio(h, 1.25f) != BOILEDEGG_OK) return false;
    std::vector<float> x(64, 0.0f), y(64, 0.0f);
    const float* in[1] = {x.data()};
    uint32_t accepted = 0;
    if (boiledegg_push(h, in, 64, &accepted) != BOILEDEGG_OK || accepted != 64) return false;

    if (boiledegg_reset(h) != BOILEDEGG_OK) return false;
    boiledegg_parameter_state state{sizeof(boiledegg_parameter_state), 1.0f, 0.75f, 0};
    if (boiledegg_set_parameter_state(h, &state) != BOILEDEGG_OK) return false;
    boiledegg_parameter_state roundtrip{};
    roundtrip.struct_size = sizeof(roundtrip);
    if (boiledegg_get_parameter_state(h, &roundtrip) != BOILEDEGG_OK) return false;
    if (std::abs(roundtrip.time_ratio - 1.0f) > 1.0e-7f ||
        std::abs(roundtrip.pitch_ratio - 0.75f) > 1.0e-7f || roundtrip.reserved != 0) return false;

    float* out[1] = {y.data()};
    if (boiledegg_process_realtime(h, in, out, 64, nullptr, 0) != BOILEDEGG_OK) return false;

    boiledegg_parameter_event bad_time{
        sizeof(boiledegg_parameter_event), 0, BOILEDEGG_PARAMETER_TIME_RATIO, 1.1f};
    if (boiledegg_process_realtime(h, nullptr, nullptr, 0, &bad_time, 1) != BOILEDEGG_UNSUPPORTED_MODE) return false;

    // Validate the entire parameter-only batch before publishing anything.
    const float before = boiledegg_get_pitch_ratio(h);
    boiledegg_parameter_event atomic_batch[2] = {
        {sizeof(boiledegg_parameter_event), 0, BOILEDEGG_PARAMETER_PITCH_RATIO, 1.25f},
        {sizeof(boiledegg_parameter_event), 0, BOILEDEGG_PARAMETER_PITCH_RATIO,
         std::numeric_limits<float>::quiet_NaN()},
    };
    if (boiledegg_apply_parameter_events(h, atomic_batch, 2) != BOILEDEGG_INVALID_ARGUMENT) return false;
    if (std::abs(boiledegg_get_pitch_ratio(h) - before) > 1.0e-7f) return false;

    boiledegg_parameter_event bad_offset{
        sizeof(boiledegg_parameter_event), 1, BOILEDEGG_PARAMETER_PITCH_RATIO, 1.0f};
    if (boiledegg_process_realtime(h, nullptr, nullptr, 0, &bad_offset, 1) != BOILEDEGG_INVALID_ARGUMENT) return false;

    boiledegg_destroy(h);
    return true;
}

bool test_realtime_reset_preserves_parameters() {
    auto* h = make_handle(128);
    if (!h) return false;
    if (boiledegg_set_pitch_semitones(h, 7.0f) != BOILEDEGG_OK) return false;
    const float expected_pitch = boiledegg_get_pitch_ratio(h);

    std::vector<float> input(128, 0.25f), output(128, 0.0f);
    const float* in[1] = {input.data()};
    float* out[1] = {output.data()};
    for (int i = 0; i < 24; ++i) {
        if (boiledegg_process_realtime(h, in, out, 128, nullptr, 0) != BOILEDEGG_OK) return false;
    }

    if (boiledegg_reset(h) != BOILEDEGG_OK) return false;
    if (std::abs(boiledegg_get_pitch_ratio(h) - expected_pitch) > 1.0e-7f) return false;
    std::fill(output.begin(), output.end(), 1.0f);
    if (boiledegg_process_realtime(h, in, out, 128, nullptr, 0) != BOILEDEGG_OK) return false;
    for (float sample : output) {
        if (std::abs(sample) > 1.0e-8f) return false;
    }
    boiledegg_destroy(h);
    return true;
}

bool test_pitch_tail_contract() {
    for (float semitones : {-12.0f, 12.0f}) {
        auto* h = make_handle(128);
        if (!h) return false;
        if (boiledegg_set_pitch_semitones(h, semitones) != BOILEDEGG_OK) return false;
        boiledegg_runtime_info info{};
        info.struct_size = sizeof(info);
        if (boiledegg_get_runtime_info(h, &info) != BOILEDEGG_OK) return false;

        constexpr uint32_t signal_frames = 2048;
        constexpr uint32_t guard_frames = 512;
        const uint32_t total = signal_frames + info.realtime_tail_frames + guard_frames;
        std::vector<float> input(total, 0.0f), output(total, 0.0f);
        input[0] = 1.0f;
        for (uint32_t pos = 0; pos < total; pos += 128) {
            const uint32_t n = std::min<uint32_t>(128, total - pos);
            const float* in[1] = {input.data() + pos};
            float* out[1] = {output.data() + pos};
            const auto r = boiledegg_process_realtime(h, in, out, n, nullptr, 0);
            if (r != BOILEDEGG_OK) {
                std::cerr << "pitch tail processing error: " << boiledegg_result_string(r) << "\n";
                boiledegg_destroy(h);
                return false;
            }
        }
        double guard_peak = 0.0;
        for (uint32_t i = signal_frames + info.realtime_tail_frames; i < total; ++i) {
            guard_peak = std::max(guard_peak, std::abs(static_cast<double>(output[i])));
        }
        boiledegg_destroy(h);
        if (guard_peak > 1.0e-4) {
            std::cerr << "reported realtime tail too short at " << semitones
                      << " st; guard peak=" << guard_peak << "\n";
            return false;
        }
    }
    return true;
}

bool test_realtime_pitch_matrix_no_underrun() {
    const uint32_t sample_rates[] = {44100, 48000, 96000};
    const uint32_t blocks[] = {32, 64, 128, 257};
    const float semitones[] = {-12.0f, 0.0f, 12.0f};
    for (uint32_t sr : sample_rates) {
        for (uint32_t block : blocks) {
            for (float st : semitones) {
                auto* h = make_handle(block, sr);
                if (!h) return false;
                if (boiledegg_set_pitch_semitones(h, st) != BOILEDEGG_OK) return false;
                std::vector<float> input(block), output(block);
                const float* in[1] = {input.data()};
                float* out[1] = {output.data()};
                const uint32_t calls = (sr * 2u + block - 1u) / block;
                uint64_t absolute = 0;
                for (uint32_t call = 0; call < calls; ++call) {
                    for (uint32_t i = 0; i < block; ++i) {
                        input[i] = static_cast<float>(0.1 * std::sin(
                            2.0 * 3.141592653589793 * 523.25 * static_cast<double>(absolute + i) / sr));
                    }
                    boiledegg_parameter_event ev{};
                    const boiledegg_parameter_event* evp = nullptr;
                    uint32_t evn = 0;
                    if ((call % 37u) == 0u) {
                        ev = {sizeof(boiledegg_parameter_event), block / 2u,
                              BOILEDEGG_PARAMETER_PITCH_SEMITONES, st};
                        evp = &ev;
                        evn = 1;
                    }
                    const auto r = boiledegg_process_realtime(h, in, out, block, evp, evn);
                    if (r != BOILEDEGG_OK) {
                        std::cerr << "matrix underrun/error sr=" << sr << " block=" << block
                                  << " st=" << st << " result=" << boiledegg_result_string(r) << "\n";
                        boiledegg_destroy(h);
                        return false;
                    }
                    absolute += block;
                }
                boiledegg_destroy(h);
            }
        }
    }
    return true;
}

} // namespace

int main() {
    if (!test_runtime_info()) return 1;
    if (!test_identity_latency_and_variable_blocks()) return 2;
    if (!test_mode_contract()) return 3;
    if (!test_events_and_in_place()) return 4;
    if (!test_parameter_only_flush_and_state()) return 5;
    if (!test_realtime_reset_preserves_parameters()) return 6;
    if (!test_pitch_tail_contract()) return 7;
    if (!test_realtime_pitch_matrix_no_underrun()) return 8;
    std::cout << "DAW host contract tests passed\n";
    return 0;
}
