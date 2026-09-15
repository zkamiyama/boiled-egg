#ifndef BOILED_EGG_RESEARCH_ANCHOR_MAP_HPP
#define BOILED_EGG_RESEARCH_ANCHOR_MAP_HPP
#include <algorithm>
#include <cmath>
#include <cstddef>
namespace boiled_egg::research {
// Validate before output mutation. No allocation; O(K+Q log K) bounded lookup.
// Storage belongs to caller. Output must not alias queries or knots.
inline bool map_anchors(const double* t,const double* u,std::size_t knots,
                        const double* q,double* out,std::size_t count) noexcept {
    if(knots<2 || !t || !u || (count && (!q || !out)))return false;
    for(std::size_t k=0;k<knots;++k)
        if(!std::isfinite(t[k]) || !std::isfinite(u[k]) ||
           (k && (t[k]<=t[k-1] || u[k]<=u[k-1])))return false;
    for(std::size_t i=0;i<count;++i)if(!std::isfinite(q[i]))return false;
    for(std::size_t i=0;i<count;++i){
        const auto* p=std::upper_bound(t,t+knots,q[i]);
        const auto k=p==t?0U:std::min(static_cast<std::size_t>(p-t-1),knots-2);
        out[i]=u[k]+(q[i]-t[k])*(u[k+1]-u[k])/(t[k+1]-t[k]);
    }
    return true;
}
}
#endif
