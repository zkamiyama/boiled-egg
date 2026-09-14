#include <boiled_egg/boiled_egg.hpp>
#include "boiled_egg_research_execution.h"
#include <array>
#include <cmath>
#include <cstring>
#include <iostream>
#include <limits>
#include <memory>
#include <stdexcept>
#include <vector>
using Audio=std::array<std::vector<float>,2>;
static void check(bool ok,const char* reason){if(!ok)throw std::runtime_error(reason);}
static Audio input(unsigned n){Audio x{std::vector<float>(n),std::vector<float>(n)};unsigned rng=1978;
    for(unsigned i=0;i<n;++i){rng=1664525*rng+1013904223;x[0][i]=.17f*std::sin(.03271f*float(i))+.02f*(float(rng>>8)/16777216.f-.5f);x[1][i]=-.5f*x[0][i];}return x;}
static boiledegg_backend_config options(unsigned quality,unsigned policy,float time,float pitch,unsigned io){
    auto b=boiledegg_default_backend_config();b.backend_id=BOILEDEGG_BACKEND_PHASE_VOCODER;b.flags=BOILEDEGG_BACKEND_ALLOW_EXPERIMENTAL;
    b.quality_mode=quality;b.formant_policy=policy;b.io_contract=io;b.initial_time_ratio=time;b.initial_pitch_ratio=pitch;return b;}
static Audio reference(const Audio& x,unsigned rate,const boiledegg_backend_config& b,bool events=false){
    auto c=boiledegg_research_pv_rt_default_config(rate,2,257);c.fft_size=b.quality_mode==0?2048:1024;c.analysis_hop=256;c.mode=1;
    c.formant_mode=b.formant_policy;c.initial_time_ratio=b.initial_time_ratio;c.initial_pitch_ratio=b.initial_pitch_ratio;
    auto f=boiledegg_research_default_features();f.timing_policy=f.rate_policy=1;f.initial_formant_ratio=b.initial_formant_ratio;
    auto e=boiledegg_research_default_execution();boiledegg_research_pv_rt_result result{};
    std::unique_ptr<boiledegg_research_pv_rt_handle,decltype(&boiledegg_research_pv_rt_destroy)> h(boiledegg_research_pv_rt_create_exec(&c,&f,&e,&result),boiledegg_research_pv_rt_destroy);
    check(h && !result,"oracle creation");Audio y;float l[8192],r[8192];float* out[]={l,r};
    auto drain=[&]{while(boiledegg_research_pv_rt_available(h.get())){auto n=boiledegg_research_pv_rt_pull(h.get(),out,8192);check(n>0,"oracle progress");y[0].insert(y[0].end(),l,l+n);y[1].insert(y[1].end(),r,r+n);}};
    for(unsigned i=0;i<x[0].size();++i){if(events&&(i==799||i==1739||i==4011))check(!boiledegg_research_pv_rt_set_formant_ratio(h.get(),i==1739?2.f:.5f),"oracle event");
        const float* in[]={x[0].data()+i,x[1].data()+i};check(!boiledegg_research_pv_rt_push(h.get(),in,1),"oracle push");drain();}
    check(!boiledegg_research_pv_rt_flush(h.get()),"oracle flush");drain();return y;
}
static Audio stream(boiled_egg::engine& e,const Audio& x,unsigned block,bool delay_pull=false){
    Audio y;float l[4096],r[4096];float* out[]={l,r};
    auto drain=[&]{while(e.available()){auto n=e.pull(out,4096);check(n>0,"stream progress");y[0].insert(y[0].end(),l,l+n);y[1].insert(y[1].end(),r,r+n);}};
    for(unsigned i=0;i<x[0].size();){auto n=std::min<unsigned>(block,unsigned(x[0].size())-i);const float* in[]={x[0].data()+i,x[1].data()+i};
        auto used=e.push(in,n);i+=used;if(!delay_pull||!used||used<n)drain();}
    e.flush();drain();check(e.drained(),"exact EOS");return y;
}
static Audio realtime(boiled_egg::engine& e,Audio x,unsigned block,bool events){
    for(unsigned i=0;i<x[0].size();i+=block){auto n=std::min<unsigned>(block,unsigned(x[0].size())-i);
        std::array<boiled_egg::parameter_event,3> ev{};unsigned count=0;
        if(events)for(unsigned at:{799u,1739u,4011u})if(at>=i&&at<i+n)ev[count++]=boiled_egg::parameter_event::formant_ratio(at-i,at==1739?2.f:.5f);
        const float* in[]={x[0].data()+i,x[1].data()+i};float* out[]={x[0].data()+i,x[1].data()+i};
        check(e.process_realtime_nothrow(in,out,n,std::span(ev.data(),count))==BOILEDEGG_OK,"realtime call");}
    return x;
}
int main(){try{
    unsigned comparisons=0;auto x=input(6011);
    for(unsigned rate:{44100u,48000u,88200u,96000u})for(unsigned quality:{0u,1u})for(unsigned policy:{0u,1u,2u})
    for(float time:{.5f,1.f,2.f})for(float pitch:{.5f,1.f,2.f}){
        if(time*pitch>2.f)continue;auto b=options(quality,policy,time,pitch,BOILEDEGG_IO_STREAMING);
        auto c=boiledegg_default_config(rate,2);c.max_block_size=257;
        boiled_egg::engine e(c,b);auto original=reference(x,rate,b),actual=stream(e,x,32);
        check(actual==original,"research vs public stream must be byte-exact");check(actual[0].size()==std::llround(x[0].size()*double(time)),"exact duration");
        e.reset();check(stream(e,x,257)==original,"reset/partition equality");
        auto info=e.runtime_info();check(!(info.capabilities&BOILEDEGG_CAP_FIXED_REALTIME_IO)&&!info.realtime_latency_frames,"stream runtime truth");++comparisons;
    }
    for(unsigned rate:{48000u,96000u})for(unsigned quality:{0u,1u})for(float pitch:{.5f,1.f,2.f})for(unsigned policy:{1u,2u}){
        auto b=options(quality,policy,1,pitch,BOILEDEGG_IO_REALTIME);auto c=boiledegg_default_config(rate,2);c.max_block_size=257;
        boiled_egg::engine e(c,b);auto L=e.runtime_info().realtime_latency_frames;auto padded=input(7001);for(auto& a:padded)a.resize(a.size()+L,0);
        auto oracle=reference(padded,rate,b,true),actual=realtime(e,padded,32,true);
        for(unsigned ch=0;ch<2;++ch){for(unsigned i=0;i<L;++i)check(actual[ch][i]==0,"declared zero prefix");
            check(std::equal(actual[ch].begin()+L,actual[ch].end(),oracle[ch].begin()),"fixed delay event equality");}
        e.set_formant_ratio(1);e.reset();check(realtime(e,padded,257,true)==actual,"inplace/event block invariance");
        check(e.runtime_info().realtime_latency_frames==L,"automation keeps fixed delay");++comparisons;
    }
    auto c=boiledegg_default_config(48000,2);c.max_block_size=1024;auto b=options(1,1,1,1,BOILEDEGG_IO_STREAMING);
    boiled_egg::engine pressure(c,b);auto long_input=input(200001);check(stream(pressure,long_input,1024,true)==reference(long_input,48000,b),"full-buffer backpressure no loss");
    b.io_contract=BOILEDEGG_IO_REALTIME;boiled_egg::engine h(c,b);float l[64]{},r[64]{};const float* in[]={l,r};float* out[]={l,r};
    check(boiledegg_set_pitch_ratio(h.native_handle(),2)==BOILEDEGG_UNSUPPORTED_MODE,"static setter rejected before start");
    auto ev=boiled_egg::parameter_event::pitch_ratio(0,2);check(h.process_realtime_nothrow(in,out,64,std::span(&ev,1))==BOILEDEGG_UNSUPPORTED_MODE,"static event not accepted");
    check(h.pitch_ratio()==1,"rejected event unchanged");h.set_formant_ratio(.75f);
    auto state=h.backend_parameter_state();state.pitch_ratio=2;state.formant_ratio=1.5f;
    check(boiledegg_set_backend_parameter_state(h.native_handle(),&state)==BOILEDEGG_UNSUPPORTED_MODE,"state validated before stores");
    check(h.formant_ratio()==.75f,"bad state preserves formant");
    auto legacy=h.parameter_state();h.set_parameter_state(legacy);check(h.formant_ratio()==.75f,"legacy state does not clear formants");
    state=h.backend_parameter_state();state.formant_ratio=1.2f;h.set_backend_parameter_state(state);check(h.formant_ratio()==1.2f,"complete state restore");
    state.formant_policy=0;check(boiledegg_set_backend_parameter_state(h.native_handle(),&state)==BOILEDEGG_UNSUPPORTED_MODE,"no silent policy switch");
    auto bad=boiled_egg::parameter_event::formant_ratio(0,.5f);l[63]=std::numeric_limits<float>::quiet_NaN();
    check(h.process_realtime_nothrow(in,out,64,std::span(&bad,1))==BOILEDEGG_INVALID_ARGUMENT,"nonfinite preflight");
    check(h.formant_ratio()==1.2f,"no event publication on bad input");l[63]=0;
    b.flags=0;check(boiledegg_validate_backend_config(&c,&b)==BOILEDEGG_UNSUPPORTED_MODE,"requires explicit experimental consent");
    b.flags=1;b.io_contract=BOILEDEGG_IO_AUTO;check(boiledegg_validate_backend_config(&c,&b)==BOILEDEGG_UNSUPPORTED_MODE,"explicit IO required");
    b.io_contract=BOILEDEGG_IO_STREAMING;b.initial_time_ratio=b.initial_pitch_ratio=2;
    check(boiledegg_validate_backend_config(&c,&b)==BOILEDEGG_UNSUPPORTED_MODE,"unsupported combined stretch not rendered");
    std::cout<<comparisons<<" research/public and fixed-delay event comparisons, 200001-frame backpressure, state and fail-closed controls passed\n";
}catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}}
