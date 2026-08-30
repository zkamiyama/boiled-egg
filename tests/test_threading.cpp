#include <boiled_egg/boiled_egg.h>

#include <atomic>
#include <cmath>
#include <cstdint>
#include <iostream>
#include <thread>
#include <vector>

namespace {

bool run_instance(int index) {
    constexpr uint32_t sample_rate = 48000;
    constexpr uint32_t channels = 2;
    constexpr uint32_t block = 128;
    constexpr uint32_t total_frames = 48000;

    auto config = boiledegg_default_config(sample_rate, channels);
    config.max_block_size = block;

    boiledegg_result create_result = BOILEDEGG_INTERNAL_ERROR;
    boiledegg_handle* handle = boiledegg_create(&config, &create_result);
    if (!handle || create_result != BOILEDEGG_OK) return false;

    const float time_ratio = 0.85f + 0.05f * static_cast<float>(index % 5);
    const float pitch_semitones = static_cast<float>((index % 7) - 3);
    if (boiledegg_set_time_ratio(handle, time_ratio) != BOILEDEGG_OK ||
        boiledegg_set_pitch_semitones(handle, pitch_semitones) != BOILEDEGG_OK) {
        boiledegg_destroy(handle);
        return false;
    }

    std::vector<float> left(block), right(block), out_left(block * 4u), out_right(block * 4u);
    const float* input[2] = {left.data(), right.data()};
    float* output[2] = {out_left.data(), out_right.data()};
    uint32_t input_position = 0;
    uint64_t output_total = 0;

    while (input_position < total_frames) {
        const uint32_t n = std::min<uint32_t>(block, total_frames - input_position);
        for (uint32_t i = 0; i < n; ++i) {
            const double t = static_cast<double>(input_position + i) / sample_rate;
            left[i] = static_cast<float>(0.2 * std::sin(2.0 * 3.141592653589793 * (220.0 + index * 9.0) * t));
            right[i] = 0.8f * left[i];
        }
        uint32_t accepted = 0;
        const auto push_result = boiledegg_push(handle, input, n, &accepted);
        if ((push_result != BOILEDEGG_OK && push_result != BOILEDEGG_BUFFER_FULL) || accepted == 0) {
            boiledegg_destroy(handle);
            return false;
        }
        input_position += accepted;

        for (;;) {
            uint32_t produced = 0;
            if (boiledegg_pull(handle, output, block * 4u, &produced) != BOILEDEGG_OK) {
                boiledegg_destroy(handle);
                return false;
            }
            output_total += produced;
            if (produced == 0) break;
        }
    }

    if (boiledegg_flush(handle) != BOILEDEGG_OK) {
        boiledegg_destroy(handle);
        return false;
    }
    for (int guard = 0; guard < 20000 && !boiledegg_is_drained(handle); ++guard) {
        uint32_t produced = 0;
        if (boiledegg_pull(handle, output, block * 4u, &produced) != BOILEDEGG_OK) {
            boiledegg_destroy(handle);
            return false;
        }
        output_total += produced;
        if (produced == 0) (void)boiledegg_flush(handle);
    }

    const bool ok = boiledegg_is_drained(handle) != 0 && output_total > 1000;
    boiledegg_destroy(handle);
    return ok;
}

bool test_parallel_instances() {
    constexpr int thread_count = 8;
    std::atomic<int> failures{0};
    std::vector<std::thread> threads;
    threads.reserve(thread_count);
    for (int i = 0; i < thread_count; ++i) {
        threads.emplace_back([i, &failures] {
            if (!run_instance(i)) failures.fetch_add(1, std::memory_order_relaxed);
        });
    }
    for (auto& thread : threads) thread.join();
    return failures.load(std::memory_order_relaxed) == 0;
}

bool test_control_thread_automation() {
    constexpr uint32_t sample_rate = 48000;
    constexpr uint32_t block = 64;
    auto config = boiledegg_default_config(sample_rate, 1);
    config.max_block_size = block;

    boiledegg_result create_result = BOILEDEGG_INTERNAL_ERROR;
    boiledegg_handle* handle = boiledegg_create(&config, &create_result);
    if (!handle || create_result != BOILEDEGG_OK) return false;

    std::atomic<bool> audio_done{false};
    std::atomic<bool> failed{false};

    std::thread control([&] {
        for (uint32_t i = 0; !audio_done.load(std::memory_order_acquire); ++i) {
            const float time_ratio = 0.75f + 0.05f * static_cast<float>(i % 11u);
            const float semitones = -7.0f + static_cast<float>(i % 15u);
            if (boiledegg_set_time_ratio(handle, time_ratio) != BOILEDEGG_OK ||
                boiledegg_set_pitch_semitones(handle, semitones) != BOILEDEGG_OK) {
                failed.store(true, std::memory_order_release);
                break;
            }
            const float tr = boiledegg_get_time_ratio(handle);
            const float pr = boiledegg_get_pitch_ratio(handle);
            if (!std::isfinite(tr) || !std::isfinite(pr) || tr <= 0.0f || pr <= 0.0f) {
                failed.store(true, std::memory_order_release);
                break;
            }
        }
    });

    std::vector<float> input_storage(block), output_storage(block * 8u);
    const float* input[1] = {input_storage.data()};
    float* output[1] = {output_storage.data()};
    uint32_t position = 0;
    constexpr uint32_t total_frames = sample_rate * 2u;

    while (position < total_frames && !failed.load(std::memory_order_acquire)) {
        const uint32_t n = std::min<uint32_t>(block, total_frames - position);
        for (uint32_t i = 0; i < n; ++i) {
            input_storage[i] = static_cast<float>(0.15 * std::sin(
                2.0 * 3.141592653589793 * 330.0 * static_cast<double>(position + i) / sample_rate));
        }
        uint32_t accepted = 0;
        const auto result = boiledegg_push(handle, input, n, &accepted);
        if ((result != BOILEDEGG_OK && result != BOILEDEGG_BUFFER_FULL) || accepted == 0) {
            failed.store(true, std::memory_order_release);
            break;
        }
        position += accepted;
        uint32_t produced = 0;
        if (boiledegg_pull(handle, output, block * 8u, &produced) != BOILEDEGG_OK) {
            failed.store(true, std::memory_order_release);
            break;
        }
    }

    audio_done.store(true, std::memory_order_release);
    control.join();
    boiledegg_destroy(handle);
    return !failed.load(std::memory_order_acquire);
}

} // namespace

int main() {
    if (!test_parallel_instances()) {
        std::cerr << "parallel independent instance test failed\n";
        return 1;
    }
    if (!test_control_thread_automation()) {
        std::cerr << "concurrent control/audio automation test failed\n";
        return 1;
    }
    std::cout << "threading contract tests passed\n";
    return 0;
}
