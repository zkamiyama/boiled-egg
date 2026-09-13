#include "boiled_egg_research_host.h"
#include <array>
#include <atomic>
#include <cmath>
#include <cstdlib>
#include <new>

static std::atomic<bool> enabled{false};
static std::atomic<unsigned long> allocations{0};
void* operator new(std::size_t n) {
    if(enabled.load(std::memory_order_relaxed)) allocations.fetch_add(1,std::memory_order_relaxed);
    if(void* p=std::malloc(n ? n : 1))return p;
    throw std::bad_alloc();
}
void* operator new[](std::size_t n){return ::operator new(n);}
void operator delete(void* p)noexcept{std::free(p);}
void operator delete[](void* p)noexcept{std::free(p);}
void operator delete(void* p,std::size_t)noexcept{std::free(p);}
void operator delete[](void* p,std::size_t)noexcept{std::free(p);}
void* operator new(std::size_t n,std::align_val_t a){
    if(enabled.load(std::memory_order_relaxed))allocations.fetch_add(1,std::memory_order_relaxed);
    void* p=nullptr;if(posix_memalign(&p,static_cast<std::size_t>(a),n?n:1)==0)return p;
    throw std::bad_alloc();
}
void* operator new[](std::size_t n,std::align_val_t a){return ::operator new(n,a);}
void operator delete(void* p,std::align_val_t)noexcept{std::free(p);}
void operator delete[](void* p,std::align_val_t)noexcept{std::free(p);}
void operator delete(void* p,std::size_t,std::align_val_t)noexcept{std::free(p);}
void operator delete[](void* p,std::size_t,std::align_val_t)noexcept{std::free(p);}
int main(){
    constexpr unsigned block=32;std::array<float,block> a{},b{};const float* in[]={a.data(),b.data()};float* out[]={a.data(),b.data()};
    for(unsigned profile:{0U,1U,2U,3U,4U}) {
        auto c=boiledegg_research_host_default_config(96000,2,block);c.profile=profile;c.pitch_ratio=.5F;
        boiledegg_research_pv_rt_result r{};auto* h=boiledegg_research_host_create(&c,&r);if(!h || r)return 1;
        enabled.store(true);
        for(unsigned n=0;n<1000;++n){
            boiledegg_research_host_event e{sizeof(e),13,n%2?2.F:.5F,0};
            if(boiledegg_research_host_request_formant(h,n%2?.8F:1.2F))return 2;
            if(boiledegg_research_host_process(h,in,out,block,&e,1))return 3;
            if(n==47 && boiledegg_research_host_reset(h))return 4;
        }
        enabled.store(false);boiledegg_research_host_destroy(h);
    }
    return allocations.load()==0?0:5;
}
