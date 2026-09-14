#ifndef BOILED_EGG_RESEARCH_FEATURE_HELPERS_HPP
#define BOILED_EGG_RESEARCH_FEATURE_HELPERS_HPP
#include "boiled_egg_research_features.h"
#include <cmath>
#include <cstdint>
#include <limits>

namespace boiled_egg::research::features {
inline bool ratio_valid(float value) noexcept {
    return std::isfinite(value) && value >= 0.5F && value <= 2.0F;
}
inline bool valid(const boiledegg_research_features* f, uint32_t formant) noexcept {
    return f && f->struct_size >= sizeof(*f) && f->version == BOILEDEGG_RESEARCH_FEATURES_VERSION
        && f->timing_policy <= BOILEDEGG_RESEARCH_TIMING_CENTERED
        && f->rate_policy <= BOILEDEGG_RESEARCH_RATE_SCALED
        && ratio_valid(f->initial_formant_ratio)
        && (formant != BOILEDEGG_RESEARCH_PV_RT_FORMANT_OFF || f->initial_formant_ratio == 1.0F);
}
inline uint32_t scale(uint32_t rate, const boiledegg_research_features& f) noexcept {
    uint32_t result = 1;
    if (f.rate_policy == BOILEDEGG_RESEARCH_RATE_SCALED)
        while (result < 8U && rate > 48000U * result) result *= 2U;
    return result;
}
inline bool scale_pv(boiledegg_research_pv_rt_config& c, const boiledegg_research_features& f) noexcept {
    const auto s = scale(c.sample_rate, f);
    if (c.fft_size > 16384U / s || c.analysis_hop > 16384U / s ||
        c.formant_cepstral_order > 8191U / s) return false;
    c.fft_size *= s; c.analysis_hop *= s; c.formant_cepstral_order *= s;
    return true;
}
} // namespace
#endif
