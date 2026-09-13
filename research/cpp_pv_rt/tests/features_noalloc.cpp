#include "boiled_egg_research_features.h"
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
    constexpr unsigned block=32;
    std::array<float,block> a{},b{};std::array<float,block*32> oa{},ob{};
    const float* in[]={a.data(),b.data()};float* out[]={oa.data(),ob.data()};
    for(unsigned backend:{1U,3U,4U,9U}) for(unsigned formant:{1U,2U}) {
        auto f=boiledegg_research_default_features();f.timing_policy=1;f.rate_policy=1;f.initial_formant_ratio=.75F;
        auto c=boiledegg_research_pv_rt_default_config(96000,2,block);
        c.fft_size=1024;c.analysis_hop=256;c.mode=backend==9?1:backend;c.formant_mode=formant;c.initial_pitch_ratio=.5F;
        auto m=boiledegg_research_multires_rt_default_config(96000,2,block);m.formant_mode=formant;m.initial_pitch_ratio=.5F;
        boiledegg_research_pv_rt_result result{};
        auto* p=backend==9?nullptr:boiledegg_research_pv_rt_create_ex(&c,&f,&result);
        auto* h=backend==9?boiledegg_research_multires_rt_create_ex(&m,&f,&result):nullptr;
        if((backend==9 && !h)||(backend!=9 && !p))return 1;
        auto available=[&]{return h?boiledegg_research_multires_rt_available(h):boiledegg_research_pv_rt_available(p);};
        auto drain=[&]{while(available()) {
            auto n=h?boiledegg_research_multires_rt_pull(h,out,block*32):boiledegg_research_pv_rt_pull(p,out,block*32);
            if(!n)std::abort();
            for(unsigned k=0;k<n;++k)if(!std::isfinite(oa[k])||!std::isfinite(ob[k]))std::abort();
        }};
        enabled.store(true);
        for(int cycle=0;cycle<2;++cycle){
            for(int j=0;j<700;++j){
                for(unsigned i=0;i<block;++i){a[i]=.2F*std::sin(.017F*static_cast<float>(j*32+i));b[i]=-.5F*a[i];}
                if(j%101==0){float v=j%2?.5F:2.F;if(h?boiledegg_research_multires_rt_set_pitch_ratio(h,v):boiledegg_research_pv_rt_set_pitch_ratio(p,v))return 2;}
                if(j%137==0){float v=j%2?.75F:1.25F;if(h?boiledegg_research_multires_rt_set_time_ratio(h,v):boiledegg_research_pv_rt_set_time_ratio(p,v))return 3;}
                if(j%43==0){float v=j%2?.5F:2.F;if(h?boiledegg_research_multires_rt_set_formant_ratio(h,v):boiledegg_research_pv_rt_set_formant_ratio(p,v))return 4;}
                if(h?boiledegg_research_multires_rt_push(h,in,block):boiledegg_research_pv_rt_push(p,in,block))return 5;
                drain();
            }
            if(h?boiledegg_research_multires_rt_flush(h):boiledegg_research_pv_rt_flush(p))return 6;
            drain();
            if(h?boiledegg_research_multires_rt_reset(h):boiledegg_research_pv_rt_reset(p))return 7;
        }
        enabled.store(false);boiledegg_research_pv_rt_destroy(p);boiledegg_research_multires_rt_destroy(h);
    }
    return allocations.load()==0?0:8;
}
