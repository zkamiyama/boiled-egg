// New ramp entry points have one audio owner per handle. UI may publish formants
// and read atomic target snapshots, but must not inspect audio-owned ramp state.
#include <boiled_egg/automation.h>
#include <atomic>
#include <array>
#include <cmath>
#include <cstdio>
#include <thread>
int main() {
    std::array<boiledegg_handle*,2> handles{};
    for(unsigned i=0;i<2;++i) {
        auto c=boiledegg_default_config(96000,2);c.max_block_size=32;
        auto b=boiledegg_default_backend_config();b.backend_id=1;b.quality_mode=1;b.formant_policy=1;
        b.io_contract=i?BOILEDEGG_IO_STREAMING:BOILEDEGG_IO_REALTIME;b.flags=i?7u:3u;
        boiledegg_result r{};handles[i]=boiledegg_create_backend(&c,&b,&r);if(!handles[i]||r)return 1;
    }
    std::atomic<unsigned> ready{},failures{};std::atomic<bool> start{};
    auto audio=[&](unsigned i) {
        float x[32]{},y[32]{},ox[1024]{},oy[1024]{};const float* in[]={x,y};float* out[]={ox,oy};
        ready.fetch_add(1);while(!start.load())std::this_thread::yield();
        for(unsigned n=0;n<2000;++n) {
            for(unsigned k=0;k<32;++k){x[k]=.1f*std::sin(.031f*float(n*32+k));y[k]=-.5f*x[k];}
            boiledegg_ramp_event ev[2]={{sizeof(ev[0]),0,2,333,n%2,n%2?.75f:1.25f,{0,0}},
                {sizeof(ev[0]),17,i?1u:2u,1001,(n+1)%2,n%2?1.25f:.75f,{0,0}}};
            if(i) {
                uint32_t used=0;if(boiledegg_push_ramps(handles[i],in,32,ev,2,&used)||used!=32)++failures;
                while(boiledegg_available(handles[i])){uint32_t count=0;if(boiledegg_pull(handles[i],out,1024,&count)||!count){++failures;break;}}
            } else if(boiledegg_process_realtime_ramps(handles[i],in,out,32,ev,2))++failures;
            boiledegg_automation_info info{};info.struct_size=sizeof(info);
            if(boiledegg_get_automation_info(handles[i],&info)||info.input_frames!=uint64_t(n+1)*32)++failures;
        }
    };
    auto ui=[&] {
        ready.fetch_add(1);while(!start.load())std::this_thread::yield();
        for(unsigned n=0;n<10000;++n) for(unsigned i=0;i<2;++i) {
            if(boiledegg_set_formant_ratio(handles[i],n%2?.75f:1.5f))++failures;
            const auto p=boiledegg_get_pitch_ratio(handles[i]),t=boiledegg_get_time_ratio(handles[i]);
            if(!std::isfinite(p)||p<.5f||p>2.f||!std::isfinite(t)||t<.5f||t>2.f)++failures;
            if(i && boiledegg_set_pitch_ratio(handles[i],1.f)!=BOILEDEGG_UNSUPPORTED_MODE)++failures;
        }
    };
    std::thread a(audio,0),b(audio,1),c(ui);while(ready.load()!=3)std::this_thread::yield();start.store(true);
    a.join();b.join();c.join();for(auto* h:handles)boiledegg_destroy(h);
    if(failures.load())return 2;
    std::puts("realtime pitch + streaming time ramps, two owners and concurrent formant/target UI passed");
}
