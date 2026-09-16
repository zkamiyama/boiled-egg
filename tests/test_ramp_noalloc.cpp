#include <boiled_egg/automation.h>
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
    float a[64]{},b[64]{},oa[8192]{},ob[8192]{};const float* input[]={a,b};float* output[]={oa,ob};
    for(unsigned io:{1U,2U})for(unsigned q:{0U,1U})for(unsigned policy:{0U,1U,2U}) {
        auto c=boiledegg_default_config(96000,2);c.max_block_size=64;
        auto backend=boiledegg_default_backend_config();backend.backend_id=1;backend.flags=io==1?7U:3U;
        backend.io_contract=io;backend.quality_mode=q;backend.formant_policy=policy;
        boiledegg_result result{};auto* h=boiledegg_create_backend(&c,&backend,&result);if(!h||result)return 1;
        const auto before=allocations.load();
        for(unsigned n=0;n<1000;++n) {
            for(unsigned i=0;i<64;++i){a[i]=.1f*std::sin(.027f*float(n*64+i));b[i]=-.5f*a[i];}
            boiledegg_ramp_event ev[2]={{sizeof(ev[0]),0,BOILEDEGG_PARAMETER_PITCH_RATIO,333,n%2,n%2?.75f:1.25f,{0,0}},
                {sizeof(ev[0]),31,io==1?BOILEDEGG_PARAMETER_TIME_RATIO:BOILEDEGG_PARAMETER_PITCH_RATIO,777,(n+1)%2,n%2?1.25f:.75f,{0,0}}};
            if(io==1){uint32_t used=0;if(boiledegg_push_ramps(h,input,64,ev,2,&used)||used!=64)return 2;
                while(boiledegg_available(h)){uint32_t count=0;if(boiledegg_pull(h,output,8192,&count)||!count)return 3;}}
            else if(boiledegg_process_realtime_ramps(h,input,output,64,ev,2))return 4;
            boiledegg_automation_info info{};info.struct_size=sizeof(info);if(boiledegg_get_automation_info(h,&info))return 5;
            if(n==400&&boiledegg_reset(h))return 6;
        }
        if(io==1){if(boiledegg_flush(h))return 7;while(boiledegg_available(h)){uint32_t n=0;if(boiledegg_pull(h,output,8192,&n)||!n)return 8;}}
        if(allocations.load()!=before)return 9;boiledegg_destroy(h);
    }
    std::puts("12 ramp policy/quality/IO configurations: processing, clocks, EOS and reset allocate zero");
}
