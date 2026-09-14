#include "heap_integrator.hpp"
extern "C" {
void* phase_heap_create(unsigned bins)noexcept {try{return new boiled_egg::experiment::phase_heap(bins);}catch(...){return nullptr;}}
void phase_heap_destroy(void* h)noexcept {delete static_cast<boiled_egg::experiment::phase_heap*>(h);}
unsigned phase_heap_process(void* h,const double* m,const double* pm,const double* dt,const double* pdt,
 const double* df,const double* pp,const double* p,double hs,double alpha,double tol,double* out)noexcept {
 return static_cast<boiled_egg::experiment::phase_heap*>(h)->integrate(m,pm,dt,pdt,df,pp,p,hs,alpha,tol,out).frequency;
}
}
