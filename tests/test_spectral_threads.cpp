#include <boiled_egg/backend.h>
#include <atomic>
#include <cmath>
#include <cstdio>
#include <thread>
int exercise(bool continuous){
    boiledegg_handle* handles[2]{};
    for(auto& h:handles){auto c=boiledegg_default_config(48000,2);c.max_block_size=32;auto b=boiledegg_default_backend_config();
        b.backend_id=1;b.flags=1|(continuous?BOILEDEGG_BACKEND_CONTINUOUS_PITCH:0u);b.formant_policy=1;b.quality_mode=1;b.io_contract=2;boiledegg_result r{};h=boiledegg_create_backend(&c,&b,&r);if(!h||r)return 1;}
    std::atomic<bool> start{false};std::atomic<unsigned> failures{0};
    auto audio=[&](unsigned id){float l[32]{},r[32]{},ol[32]{},orr[32]{};const float* in[]={l,r};float* out[]={ol,orr};
        while(!start.load())std::this_thread::yield();
        for(unsigned n=0;n<1500;++n){for(unsigned k=0;k<32;++k){l[k]=.1f*std::sin(.031f*float(n*32+k));r[k]=-.5f*l[k];}
            boiledegg_parameter_event ev{sizeof(ev),11,BOILEDEGG_PARAMETER_FORMANT_RATIO,n%2?.6f:1.8f};
            if(boiledegg_process_realtime(handles[id],in,out,32,&ev,1))++failures;}};
    auto control=[&]{while(!start.load())std::this_thread::yield();for(unsigned n=0;n<5000;++n)for(auto* h:handles){
        if(boiledegg_set_formant_ratio(h,n%2?.75f:1.25f))++failures;
        if(boiledegg_set_pitch_ratio(h,n%2?.5f:2.f)!=(continuous?BOILEDEGG_OK:BOILEDEGG_UNSUPPORTED_MODE))++failures;
        boiledegg_backend_parameter_state state{};state.struct_size=sizeof(state);
        if(boiledegg_get_backend_parameter_state(h,&state)||boiledegg_set_backend_parameter_state(h,&state))++failures;
        boiledegg_backend_config b{};b.struct_size=sizeof(b);if(boiledegg_get_backend_configuration(h,&b))++failures;
    }};
    std::thread a(audio,0),b(audio,1),c(control);start.store(true);a.join();b.join();c.join();
    for(auto* h:handles)boiledegg_destroy(h);
    std::puts("two independent spectral audio owners plus concurrent UI/state checks completed");return failures.load()?2:0;
}

int main(){const int a=exercise(false);return a?a:exercise(true);}
