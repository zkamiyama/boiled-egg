#include "anchor_map.hpp"
extern "C" int transient_map(const double* t,const double* u,unsigned knots,
                             const double* q,double* out,unsigned count) noexcept {
    return boiled_egg::research::map_anchors(t,u,knots,q,out,count)?0:1;
}
