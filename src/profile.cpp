#include <boiled_egg/backend.h>

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
    if (!config || config->struct_size<sizeof(*config) || !profile || !valid_profile_shape(*profile)) return nullptr;
    if (!supported_profile(*profile)) {
        if (out_result) *out_result = BOILEDEGG_UNSUPPORTED_MODE;
        return nullptr;
    }
    auto backend=boiledegg_default_backend_config();
    backend.quality_mode=profile->quality_mode;
    return boiledegg_create_backend(config,&backend,out_result);
}

} // extern "C"
