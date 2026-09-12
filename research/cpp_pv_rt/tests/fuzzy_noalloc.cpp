#include "boiled_egg_pv_rt.h"
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
    constexpr std::uint32_t block=32;
    std::array<float,block> a{},b{};std::array<float,block*8> oa{},ob{};
    const float* in[]={a.data(),b.data()};float* out[]={oa.data(),ob.data()};
    for(auto mode:{BOILEDEGG_RESEARCH_PV_RT_FUZZY,BOILEDEGG_RESEARCH_PV_RT_FUZZY_NOISE})
      for(std::uint32_t formant:{0U,1U,2U}){
        auto c=boiledegg_research_pv_rt_default_config(96000,2,block);
        c.fft_size=1024;c.analysis_hop=256;c.mode=mode;c.formant_mode=formant;c.initial_pitch_ratio=1.5F;
        boiledegg_research_pv_rt_result result{};
        auto* h=boiledegg_research_pv_rt_create(&c,&result);if(!h)return 1;
        enabled.store(true);
        // Include cold first push, automation, flush and reset, not just warm steady-state.
        for(int cycle=0;cycle<2;++cycle){
          for(int j=0;j<700;++j){
            for(std::uint32_t i=0;i<block;++i){a[i]=std::sin(.017F*static_cast<float>(j*32+i));b[i]=-.5F*a[i];}
            if(j%101==0 && boiledegg_research_pv_rt_set_pitch_ratio(h,j%2?0.5F:2.0F))return 2;
            if(j%137==0 && boiledegg_research_pv_rt_set_time_ratio(h,j%2?0.75F:1.25F))return 3;
            if(boiledegg_research_pv_rt_push(h,in,block))return 4;
            while(boiledegg_research_pv_rt_available(h))boiledegg_research_pv_rt_pull(h,out,block*8);
          }
          if(boiledegg_research_pv_rt_flush(h))return 5;
          while(boiledegg_research_pv_rt_available(h))boiledegg_research_pv_rt_pull(h,out,block*8);
          if(boiledegg_research_pv_rt_reset(h))return 6;
        }
        enabled.store(false);boiledegg_research_pv_rt_destroy(h);
      }
    return allocations.load()==0?0:7;
}
