#include <boiled_egg/boiled_egg.h>

#include <array>
#include <cstdint>
#include <iostream>
#include <vector>

namespace {

bool make_and_probe(uint32_t mode, uint32_t& latency) {
    auto config = boiledegg_default_config(48000, 2);
    config.max_block_size = 128;
    auto profile = boiledegg_default_profile();
    profile.quality_mode = mode;
    if (!boiledegg_profile_is_supported(&profile)) return false;
    boiledegg_result result = BOILEDEGG_INTERNAL_ERROR;
    auto* handle = boiledegg_create_ex(&config, &profile, &result);
    if (!handle || result != BOILEDEGG_OK) return false;

    boiledegg_runtime_info info{};
    info.struct_size = sizeof(info);
    if (boiledegg_get_runtime_info(handle, &info) != BOILEDEGG_OK) {
        boiledegg_destroy(handle);
        return false;
    }
    latency = info.realtime_latency_frames;

    std::vector<float> left(128, 0.1f), right(128, -0.05f), out_left(128), out_right(128);
    const float* input[2] = {left.data(), right.data()};
    float* output[2] = {out_left.data(), out_right.data()};
    const auto process_result = boiledegg_process_realtime(handle, input, output, 128, nullptr, 0);
    boiledegg_destroy(handle);
    return process_result == BOILEDEGG_OK;
}

} // namespace

int main() {
    auto default_profile = boiledegg_default_profile();
    if (default_profile.struct_size != sizeof(boiledegg_profile_config) ||
        default_profile.quality_mode != BOILEDEGG_QUALITY_GENERAL ||
        default_profile.formant_mode != BOILEDEGG_FORMANT_OFF ||
        !boiledegg_profile_is_supported(&default_profile)) return 1;

    uint32_t general_latency = 0, transient_latency = 0, efficient_latency = 0;
    if (!make_and_probe(BOILEDEGG_QUALITY_GENERAL, general_latency)) return 2;
    if (!make_and_probe(BOILEDEGG_QUALITY_TRANSIENT, transient_latency)) return 3;
    if (!make_and_probe(BOILEDEGG_QUALITY_EFFICIENT, efficient_latency)) return 4;
    if (!(transient_latency < general_latency) || !(efficient_latency <= general_latency)) return 5;

    auto config = boiledegg_default_config(48000, 2);
    auto unsupported = boiledegg_default_profile();
    unsupported.quality_mode = BOILEDEGG_QUALITY_MONOPHONIC;
    if (boiledegg_profile_is_supported(&unsupported)) return 6;
    boiledegg_result result = BOILEDEGG_OK;
    if (boiledegg_create_ex(&config, &unsupported, &result) != nullptr || result != BOILEDEGG_UNSUPPORTED_MODE) return 7;

    unsupported = boiledegg_default_profile();
    unsupported.formant_mode = BOILEDEGG_FORMANT_PRESERVE;
    result = BOILEDEGG_OK;
    if (boiledegg_profile_is_supported(&unsupported) ||
        boiledegg_create_ex(&config, &unsupported, &result) != nullptr ||
        result != BOILEDEGG_UNSUPPORTED_MODE) return 8;

    auto invalid = boiledegg_default_profile();
    invalid.reserved = 1;
    result = BOILEDEGG_OK;
    if (boiledegg_profile_is_supported(&invalid) ||
        boiledegg_create_ex(&config, &invalid, &result) != nullptr ||
        result != BOILEDEGG_INVALID_ARGUMENT) return 9;

    std::cout << "manual profile tests passed: general=" << general_latency
              << " transient=" << transient_latency
              << " efficient=" << efficient_latency << '\n';
    return 0;
}
