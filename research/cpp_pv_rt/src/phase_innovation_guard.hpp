#ifndef BOILED_EGG_RESEARCH_PHASE_INNOVATION_GUARD_HPP
#define BOILED_EGG_RESEARCH_PHASE_INNOVATION_GUARD_HPP
#include <algorithm>
#include <cmath>
#include <cstdint>
#include <numbers>

namespace boiled_egg::research::detail::phase_innovation_guard {
// Research-only confidence for the EXISTING optional coherence correction.
// Compare two successive IF estimates, in radians/input sample, modulo the
// analysis-hop alias period. A half-bin innovation removes confidence. This is
// neither a calibrated probability nor a source-type/profile classifier.
// Caller contract: finite frequencies, hop>0, bins>=2. No allocation or state.
inline float wrap(float value) noexcept {
    constexpr float pi=std::numbers::pi_v<float>;
    value=std::fmod(value+pi,2.0F*pi);
    if(value<0.0F)value+=2.0F*pi;
    return value-pi;
}
inline float reliability(float current,float previous,float hop,
                         std::uint32_t bins,bool initialized) noexcept {
    if(!initialized)return 0.0F;
    const float innovation=std::abs(wrap((current-previous)*hop))/hop;
    const float tolerance=std::numbers::pi_v<float>/static_cast<float>(2U*(bins-1U));
    return std::clamp(1.0F-innovation/tolerance,0.0F,1.0F);
}
// Interpolate on the phase circle, not through the branch cut. This changes
// phase only; it is not waveform mixing, output normalization or a limiter.
inline float blend(float ordinary,float corrected,float confidence) noexcept {
    return wrap(ordinary+confidence*wrap(corrected-ordinary));
}
}
#endif
