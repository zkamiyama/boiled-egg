#include "heap_integrator.hpp"
#include <atomic>
#include <array>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <new>
static std::atomic<unsigned> allocations{};
void* operator new(std::size_t n){++allocations;if(auto* p=std::malloc(n?n:1))return p;throw std::bad_alloc();}
void* operator new[](std::size_t n){return ::operator new(n);}
void operator delete(void* p)noexcept{std::free(p);}void operator delete[](void* p)noexcept{std::free(p);}
void operator delete(void* p,std::size_t)noexcept{std::free(p);}void operator delete[](void* p,std::size_t)noexcept{std::free(p);}
int main(){
    constexpr unsigned bins=513;std::array<double,bins> m{},pm{},dt{},df{},phase{},out{};
    boiled_egg::experiment::phase_heap h(bins);unsigned state=19;const auto before=allocations.load();unsigned pops=0;
    for(unsigned n=0;n<1000;++n) {
        for(unsigned k=0;k<bins;++k){state=1664525U*state+1013904223U;m[k]=1+state%31;pm[k]=1+(state>>8)%31;dt[k]=.03;df[k]=.02;phase[k]=.03*k;}
        const auto s=h.integrate(m.data(),pm.data(),dt.data(),dt.data(),df.data(),phase.data(),phase.data(),17.,1.5,1e-6,out.data());
        if(s.pops>2*bins||s.temporal+s.frequency!=bins)return 1;pops+=s.pops;
        for(unsigned k=0;k<bins;++k)if(std::abs(out[k]-(phase[k]+17*.03))>1e-12)return 2;
    }
    if(allocations.load()!=before)return 3;
    m.fill(0);pm.fill(0);auto s=h.integrate(m.data(),pm.data(),dt.data(),dt.data(),df.data(),phase.data(),phase.data(),17.,1.5,1e-6,out.data());
    if(s.pops||out!=phase)return 4;
    try{boiled_egg::experiment::phase_heap invalid(1);return 5;}catch(const std::invalid_argument&){}
    std::printf("513000 affine phase values; %u bounded heap removals; zero processing allocations; silence/invalid dimensions passed\n",pops);
}
