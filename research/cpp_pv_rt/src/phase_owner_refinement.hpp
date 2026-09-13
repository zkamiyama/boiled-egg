#ifndef BOILED_EGG_RESEARCH_PHASE_OWNER_REFINEMENT_HPP
#define BOILED_EGG_RESEARCH_PHASE_OWNER_REFINEMENT_HPP
#include <algorithm>
#include <cmath>
#include <cstdint>
#include <limits>
#include <numbers>

namespace boiled_egg::research::detail::phase_owner_refinement {
// Opt-in research helper. Caller has already rejected the geometric owner.
// Arrays have bins entries, bins>=2, hop>0, and every owner is in [0,bins).
// Frequencies are radians/input sample; compare modulo analysis-hop aliases.
// A +/-4-bin neighborhood is fixed, allocation-free and independent of channel
// count. Preserve the original own-bin fallback when no compatible peak exists.
inline float wrap(float value) noexcept {
    constexpr float pi=std::numbers::pi_v<float>;
    value=std::fmod(value+pi,2.0F*pi);
    if(value<0.0F)value+=2.0F*pi;
    return value-pi;
}
inline std::uint32_t select(std::uint32_t k,std::uint32_t bins,float hop,
                           const float* frequency,const std::uint32_t* owners) noexcept {
    std::uint32_t selected=k,previous=std::numeric_limits<std::uint32_t>::max();
    float best=std::numbers::pi_v<float>/static_cast<float>(2U*(bins-1U));
    for(int offset=-4;offset<=4;++offset) {
        const auto neighbor=static_cast<std::uint32_t>(std::clamp(
            static_cast<int>(k)+offset,0,static_cast<int>(bins)-1));
        const auto candidate=owners[neighbor];
        if(candidate==previous)continue;
        previous=candidate;
        const float distance=std::abs(wrap((frequency[k]-frequency[candidate])*hop))/hop;
        if(distance<best){best=distance;selected=candidate;}
    }
    return selected;
}
}
#endif
