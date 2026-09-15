#include "edge_heap.hpp"
#include <cmath>
#include <cstdint>
struct edge_handle {std::uint32_t bins;boiled_egg::experiment::edge_heap heap;explicit edge_handle(std::uint32_t n):bins(n),heap(n){}};
extern "C" {
void* phase_edge_create(std::uint32_t n) noexcept {try{return new edge_handle(n);}catch(...){return nullptr;}}
void phase_edge_destroy(void* p) noexcept {delete static_cast<edge_handle*>(p);}
// Research FFI only, not a product ABI. Return0 on success,1 on invalid input.
int phase_edge_process(void* p,const double* mag,const double* oldmag,const double* dt,
 const double* df,const double* oldphase,const double* inputphase,double tolerance,
 double* out,std::uint32_t* stats) noexcept {
    if(!p||!mag||!oldmag||!dt||!df||!oldphase||!inputphase||!out||!stats||!std::isfinite(tolerance)||tolerance<0)return 1;
    const auto n=static_cast<edge_handle*>(p)->bins;
    for(std::uint32_t k=0;k<n;++k)
        if(!std::isfinite(mag[k])||mag[k]<0||!std::isfinite(oldmag[k])||oldmag[k]<0||
           !std::isfinite(dt[k])||!std::isfinite(oldphase[k])||!std::isfinite(inputphase[k]))return 1;
    for(std::uint32_t k=0;k+1<n;++k)if(!std::isfinite(df[k]))return 1;
    const auto s=static_cast<edge_handle*>(p)->heap.integrate(mag,oldmag,dt,df,oldphase,inputphase,tolerance,out);
    stats[0]=s.temporal;stats[1]=s.frequency;stats[2]=s.pops;return 0;
}
}
