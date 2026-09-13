#include "boiled_egg_research_host.h"
#include <array>
#include <atomic>
#include <cmath>
#include <cstdlib>
#include <iostream>
#include <thread>
static void check(bool x){if(!x)std::abort();}
int main(){
    std::array<boiledegg_research_host_handle*,2> handles{};
    for(auto& h:handles){auto c=boiledegg_research_host_default_config(96000,2,32);boiledegg_research_pv_rt_result s{};h=boiledegg_research_host_create(&c,&s);check(h && !s);}
    std::atomic<unsigned> ready{0};std::atomic<bool> start{false};
    auto audio=[&](unsigned i){float x[32]{},y[32]{};const float* in[]={x,y};float* out[]={x,y};++ready;while(!start.load())std::this_thread::yield();
        for(unsigned n=0;n<4000;++n){for(unsigned k=0;k<32;++k){x[k]=.1F*std::sin(.03F*static_cast<float>(n*32+k));y[k]=-.5F*x[k];}
            check(boiledegg_research_host_process(handles[i],in,out,32,nullptr,0)==0);}
    };
    auto ui=[&]{++ready;while(!start.load())std::this_thread::yield();for(unsigned i=0;i<40000;++i)for(auto* h:handles){
        check(boiledegg_research_host_request_formant(h,i%2?.5F:2.F)==0);auto v=boiledegg_research_host_get_target(h);check(v>=.5F && v<=2.F);
        boiledegg_research_host_state s{};s.struct_size=sizeof(s);check(boiledegg_research_host_state_get(h,&s)==0);check(boiledegg_research_host_state_request(h,&s)==0);
    }};
    std::thread a(audio,0),b(audio,1),c(ui);while(ready.load()!=3)std::this_thread::yield();start.store(true);a.join();b.join();c.join();
    for(auto* h:handles){boiledegg_research_host_stats s{};s.struct_size=sizeof(s);check(boiledegg_research_host_get_stats(h,&s)==0);check(!s.underruns && !s.execution.frame_overruns);boiledegg_research_host_destroy(h);}
    std::cout<<"two audio owners plus concurrent UI/state mailbox passed\n";
}
