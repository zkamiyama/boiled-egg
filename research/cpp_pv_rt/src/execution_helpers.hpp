#ifndef BOILED_EGG_EXECUTION_HELPERS_HPP
#define BOILED_EGG_EXECUTION_HELPERS_HPP
#include "boiled_egg_research_execution.h"
namespace boiled_egg::research::execution {
inline bool valid(const boiledegg_research_execution* e, float time, float pitch) noexcept {
    return e && e->struct_size>=sizeof(*e) && e->version==BOILEDEGG_RESEARCH_EXECUTION_VERSION
        && e->scheduled<=1 && e->simd<=1 && (!e->scheduled || (time==1.F && pitch>=.5F && pitch<=2.F));
}
}
#endif
