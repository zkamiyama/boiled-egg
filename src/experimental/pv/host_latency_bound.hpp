#ifndef BOILED_EGG_HOST_LATENCY_BOUND_HPP
#define BOILED_EGG_HOST_LATENCY_BOUND_HPP
#include <algorithm>
#include <cmath>
#include <cstdint>
namespace boiled_egg::research::detail {
// Static time=1, pitch in[.5,2]. Conditional on zero scheduler overruns:
// frame k completes by N/2+(k+1)H input ticks. The published safe OLA index
// is round(k*H*p); thus safe(t) >= p*(t-N/2-2H)-.5. Cleanup service 8/tick
// dominates slope p<=2, and final resampling service 2/tick dominates slope1.
// Crop N/2 plus resampler right support22 plus rounding slack gives D below.
// This bounds sample availability, not execution time. No audio measurement,
// model-specific silence detection, or minimum observed delay sets this value.
inline std::uint32_t child_latency_bound(std::uint32_t n,std::uint32_t hop,float pitch) noexcept {
    const double d=static_cast<double>(n)/2+2.0*hop+(static_cast<double>(n)/2+24.0)/pitch+2.0;
    return static_cast<std::uint32_t>(std::ceil(d));
}
inline std::uint32_t compact_host_latency(std::uint32_t scale,std::uint32_t profile,float pitch) noexcept {
    auto result=child_latency_bound((profile==0?2048U:1024U)*scale,256U*scale,pitch);
    if(profile==3){result=std::max(result,child_latency_bound(512U*scale,192U*scale,pitch));result+=64U*scale+2U;}
    return (result+31U)&~31U;
}
}
#endif
