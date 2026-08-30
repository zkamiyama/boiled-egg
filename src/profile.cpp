#include <boiled_egg/boiled_egg.h>

#include <algorithm>
#include <cstdint>

namespace {

bool valid_profile_shape(const boiledegg_profile_config& profile) noexcept {
    return profile.struct_size >= sizeof(boiledegg_profile_config) &&
           profile.quality_mode <= BOILEDEGG_QUALITY_MONOPHONIC &&
           profile.formant_mode <= BOILEDEGG_FORMANT_PRESERVE &&
           profile.reserved == 0u;
}

bool supported_profile(const boiledegg_profile_config& profile) noexcept {
    if (!valid_profile_shape(profile)) return false;
    // The production v0.1 WSOLA backend has no spectral-envelope/formant path.
    // Keep this explicit rather than silently accepting a no-op switch.
    if (profile.formant_mode != BOILEDEGG_FORMANT_OFF) return false;
    if (profile.quality_mode == BOILEDEGG_QUALITY_MONOPHONIC) return false;
    return true;
}

boiledegg_config adjusted_config(boiledegg_config config, uint32_t quality_mode) noexcept {
    switch (quality_mode) {
        case BOILEDEGG_QUALITY_GENERAL:
            // Existing balanced WSOLA profile.
            break;
        case BOILEDEGG_QUALITY_TRANSIENT: {
            // Shorter correlation/overlap footprint improves attack locality and
            // reduces lookahead. Keep an even window because overlap is N/2.
            uint32_t window = std::max<uint32_t>(256u, (config.window_frames * 3u) / 4u);
            window &= ~1u;
            config.window_frames = window;
            config.search_frames = std::min<uint32_t>(config.search_frames, std::max<uint32_t>(16u, window / 8u));
            break;
        }
        case BOILEDEGG_QUALITY_EFFICIENT:
            // Preserve the synthesis window but reduce correlation-search work.
            config.search_frames = std::max<uint32_t>(8u, config.search_frames / 2u);
            break;
        default:
            break;
    }
    return config;
}

} // namespace

extern "C" {

boiledegg_profile_config boiledegg_default_profile(void) {
    boiledegg_profile_config profile{};
    profile.struct_size = sizeof(profile);
    profile.quality_mode = BOILEDEGG_QUALITY_GENERAL;
    profile.formant_mode = BOILEDEGG_FORMANT_OFF;
    profile.reserved = 0u;
    return profile;
}

int boiledegg_profile_is_supported(const boiledegg_profile_config* profile) {
    return profile && supported_profile(*profile) ? 1 : 0;
}

boiledegg_handle* boiledegg_create_ex(
    const boiledegg_config* config,
    const boiledegg_profile_config* profile,
    boiledegg_result* out_result) {
    if (out_result) *out_result = BOILEDEGG_INVALID_ARGUMENT;
    if (!config || !profile || !valid_profile_shape(*profile)) return nullptr;
    if (!supported_profile(*profile)) {
        if (out_result) *out_result = BOILEDEGG_UNSUPPORTED_MODE;
        return nullptr;
    }
    boiledegg_config adjusted = adjusted_config(*config, profile->quality_mode);
    return boiledegg_create(&adjusted, out_result);
}

} // extern "C"
