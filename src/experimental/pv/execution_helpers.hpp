#ifndef BOILED_EGG_EXECUTION_HELPERS_HPP
#define BOILED_EGG_EXECUTION_HELPERS_HPP
#include "boiled_egg_research_execution.h"
#include <cstdint>
namespace boiled_egg::research::execution {
inline bool valid(const boiledegg_research_execution* e, float time, float pitch) noexcept {
    return e && e->struct_size>=sizeof(*e) && e->version==BOILEDEGG_RESEARCH_EXECUTION_VERSION
        && e->scheduled<=1 && e->simd<=1 && (!e->scheduled || (time==1.F && pitch>=.5F && pitch<=2.F));
}
// Conservative count of persistent frame_sequence yields, not CPU cycles.
// Include FFT permutations/normalization, all per-channel loops, worst-case
// monophonic quefrency scan, first-frame fuzzy initialization and state copies.
inline std::uint32_t frame_step_bound(std::uint32_t n,std::uint32_t channels,
    std::uint32_t formant,std::uint32_t mode) noexcept {
    unsigned levels=0;for(auto v=n;v>1;v>>=1)++levels;
    auto ceildiv=[](std::uint64_t a,std::uint64_t b){return (a+b-1)/b;};
    const std::uint64_t bins=n/2U+1U,n32=ceildiv(n,32),b32=ceildiv(bins,32);
    const auto forward=ceildiv(n+std::uint64_t(n)*levels/2,128)+1;
    const auto inverse=ceildiv(2ULL*n+std::uint64_t(n)*levels/2,128)+1;
    std::uint64_t bound=channels*(2*n32+ceildiv(n-bins,32)+4*b32+forward+inverse);
    if(formant)bound+=2*n32+4*b32+(formant==2?b32:0)+forward+inverse;
    bound+=4*b32+n32+2*ceildiv(channels*bins,64)+ceildiv(bins,64)+32;
    if(mode>=3)bound+=5*b32;
    return static_cast<std::uint32_t>(bound);
}
}
#endif
