#include <boiled_egg/backend.h>
#include <atomic>
#include <cmath>
#include <cstdlib>
#include <new>
#include <cstdio>
#include <initializer_list>
static std::atomic<unsigned> allocations{0};
static void* allocate(std::size_t n){allocations.fetch_add(1,std::memory_order_relaxed);if(void* p=std::malloc(n?n:1))return p;throw std::bad_alloc();}
void* operator new(std::size_t n){return allocate(n);}void* operator new[](std::size_t n){return allocate(n);}
void operator delete(void* p)noexcept{std::free(p);}void operator delete[](void* p)noexcept{std::free(p);}
void operator delete(void* p,std::size_t)noexcept{std::free(p);}void operator delete[](void* p,std::size_t)noexcept{std::free(p);}
void* operator new(std::size_t n,std::align_val_t a){allocations.fetch_add(1,std::memory_order_relaxed);void* p=nullptr;if(posix_memalign(&p,static_cast<size_t>(a),n?n:1))throw std::bad_alloc();return p;}
void* operator new[](std::size_t n,std::align_val_t a){return ::operator new(n,a);}
void operator delete(void* p,std::align_val_t)noexcept{std::free(p);}void operator delete[](void* p,std::align_val_t)noexcept{std::free(p);}
void operator delete(void* p,std::size_t,std::align_val_t)noexcept{std::free(p);}void operator delete[](void* p,std::size_t,std::align_val_t)noexcept{std::free(p);}
int main(){
    float l[64]{},r[64]{},ol[8192]{},orr[8192]{};const float* in[]={l,r};float* out[]={ol,orr};
    for(unsigned quality:{0u,1u})for(unsigned policy:{1u,2u})for(unsigned io:{1u,2u}){
        auto c=boiledegg_default_config(96000,2);c.max_block_size=64;auto b=boiledegg_default_backend_config();
        b.backend_id=1;b.flags=1;b.quality_mode=quality;b.formant_policy=policy;b.io_contract=io;b.initial_pitch_ratio=.5f;
        boiledegg_result result{};auto* h=boiledegg_create_backend(&c,&b,&result);if(!h||result)return 1;
        auto before=allocations.load();
        for(unsigned i=0;i<500;++i){for(unsigned k=0;k<64;++k){l[k]=.1f*std::sin(.027f*float(i*64+k));r[k]=-.5f*l[k];}
            if(boiledegg_set_formant_ratio(h,i%2?.75f:1.25f))return 2;
            if(io==2){boiledegg_parameter_event ev{sizeof(ev),17,BOILEDEGG_PARAMETER_FORMANT_RATIO,i%2?.5f:2.f};
                if(boiledegg_process_realtime(h,in,out,64,&ev,1))return 3;
            } else {uint32_t used=0;if(boiledegg_push(h,in,64,&used)||used!=64)return 4;
                while(boiledegg_available(h)){uint32_t n=0;if(boiledegg_pull(h,out,8192,&n)||!n)return 5;}}
            if(i==100&&boiledegg_reset(h))return 6;
            boiledegg_backend_parameter_state st{};st.struct_size=sizeof(st);
            if(boiledegg_get_backend_parameter_state(h,&st)||boiledegg_set_backend_parameter_state(h,&st))return 7;
        }
        if(io==1){if(boiledegg_flush(h))return 8;while(boiledegg_available(h)){uint32_t n=0;if(boiledegg_pull(h,out,8192,&n)||!n)return 9;}}
        if(boiledegg_reset(h)||allocations.load()!=before)return 10;
        boiledegg_destroy(h);
    }
    std::puts("eight spectral profile/policy/IO combinations: processing, state, events, flush and reset allocate zero");return 0;
}
