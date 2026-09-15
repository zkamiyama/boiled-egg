#include <boiled_egg/boiled_egg.hpp>
#include "ramp_randomized_checks.hpp"
#include <algorithm>
#include <array>
#include <cmath>
#include <cstdint>
#include <iostream>
#include <stdexcept>
#include <vector>
static void check(bool ok,const char* why){if(!ok)throw std::runtime_error(why);}
static boiledegg_ramp_event ev(unsigned at,unsigned id,float v,unsigned n,unsigned curve=0){return {sizeof(boiledegg_ramp_event),at,id,n,curve,v,{0,0}};}
static boiledegg_backend_config cfg(unsigned quality=1,unsigned policy=0){
    auto b=boiledegg_default_backend_config();b.backend_id=1;b.flags=7;b.io_contract=BOILEDEGG_IO_STREAMING;
    b.quality_mode=quality;b.formant_policy=policy;return b;
}
using Audio=std::array<std::vector<float>,2>;
static Audio run(unsigned rate,unsigned quality,unsigned policy,unsigned block,bool stalled) {
    auto c=boiledegg_default_config(rate,2);c.max_block_size=257;boiled_egg::engine h(c,cfg(quality,policy));
    const unsigned length=stalled?110003U:12003U;
    Audio x{std::vector<float>(length),std::vector<float>(length)},y;
    for(unsigned i=0;i<length;++i){x[0][i]=.2f*std::sin(.021f*float(i));x[1][i]=-.5f*x[0][i];}
    const std::array events{ev(0,1,.5f,777,1),ev(888,1,2.f,4001),ev(1233,2,.75f,700),
        ev(7777,1,1.f,31),ev(8888,1,2.f,0),ev(8888,2,.5f,0)};
    float a[4096],b[4096];float* out[]={a,b};unsigned pos=0,backpressure=0;
    auto drain=[&]{while(h.available()){auto n=h.pull(out,4096);check(n>0,"pull progress");y[0].insert(y[0].end(),a,a+n);y[1].insert(y[1].end(),b,b+n);}};
    while(pos<length) {
        unsigned n=std::min(block,length-pos);std::array<boiledegg_ramp_event,6> batch{};unsigned count=0;
        for(auto e:events)if(e.sample_offset>=pos&&e.sample_offset<pos+n){e.sample_offset-=pos;batch[count++]=e;}
        const float* in[]={x[0].data()+pos,x[1].data()+pos};
        auto used=h.push_ramps(in,n,std::span(batch.data(),count));
        if(used<n)++backpressure;
        pos+=used;
        if(!stalled||used<n)drain();
    }
    drain();const auto before=h.automation_info();h.flush();drain();const auto after=h.automation_info();
    check(h.drained()&&y[0].size()==static_cast<std::size_t>(std::llround(before.output_position)),"variable-time final duration");
    check(before.input_frames==after.input_frames&&before.effective_time_ratio==after.effective_time_ratio,"flush does not advance T clock");
    if(stalled)check(backpressure>0,"backpressure really exercised");
    for(unsigned i=0;i<y[0].size();++i)check(std::isfinite(y[0][i])&&std::abs(y[1][i]+.5f*y[0][i])<2e-6f,"finite linked output");
    return y;
}
int main(){try{
    const auto randomized = boiled_egg::test::ramp_randomized::verify();
    std::cout << randomized << " randomized accepted-prefix checkpoints passed\n";
    unsigned samples=0,comparisons=0;
    for(unsigned curve:{0U,1U}) {
        auto c=boiledegg_default_config(48000,1);c.max_block_size=1;boiled_egg::engine h(c,cfg());
        std::array events{ev(0,1,.5f,2001,curve),ev(0,2,1.5f,1001,curve)};
        // Envelope maxT=1 * maxP=1.5 remains within 2 for the full trajectories.
        h.push_ramps(nullptr,0,events);
        long double w=0,v=0;float x=.1f,outbuf[16];const float* in[]={&x};float* out[]={outbuf};
        for(unsigned i=1;i<=4000;++i) {
            const long double ft=std::min(1.L,static_cast<long double>(i)/2001),fp=std::min(1.L,static_cast<long double>(i)/1001);
            const long double t=curve?std::pow(.5L,ft):1.L-.5L*ft;
            const long double p=curve?std::pow(1.5L,fp):1.L+.5L*fp;
            w+=t;v+=t*p;check(h.push_ramps(in,1)==1,"sample accepted");while(h.available())h.pull(out,16);
            const auto s=h.automation_info();
            check(std::abs(s.output_position-double(w))<2e-7&&std::abs(s.intermediate_position-double(v))<2e-7,"independent dual integrals");
            check(std::abs(s.effective_time_ratio-double(t))<1e-10&&std::abs(s.effective_pitch_ratio-double(p))<1e-10,"independent effective T and p");++samples;
        }
        auto before=h.automation_info();auto bad=ev(0,1,2.f,500);
        uint32_t used=44;check(boiledegg_push_ramps(h.native_handle(),in,1,&bad,1,&used)==BOILEDEGG_UNSUPPORTED_MODE&&used==0,"unsafe future product rejected");
        auto after=h.automation_info();check(before.output_position==after.output_position&&before.target_time_ratio==after.target_time_ratio,"coupled rejection transactional");
        std::array safe{ev(0,1,2.f,0),ev(0,2,.5f,0)};h.push_ramps(in,1,safe);
        check(h.automation_info().effective_time_ratio==2.&&h.automation_info().effective_pitch_ratio==.5,"atomic same-offset coupled steps");
        auto unfinished=ev(0,1,.5f,0xffffffffU,curve);h.push_ramps(in,1,std::span(&unfinished,1));before=h.automation_info();
        h.flush();while(h.available())h.pull(out,16);after=h.automation_info();
        check(before.time_remaining_frames==after.time_remaining_frames&&before.output_position==after.output_position,"EOS freezes unfinished time ramp");
        h.reset();after=h.automation_info();check(!after.input_frames&&!after.time_remaining_frames&&after.effective_time_ratio==.5,"time reset retains target");
        check(boiledegg_set_time_ratio(h.native_handle(),1.f)==BOILEDEGG_UNSUPPORTED_MODE&&boiledegg_set_pitch_ratio(h.native_handle(),1.f)==BOILEDEGG_UNSUPPORTED_MODE,"time handles reject uncoupled UI setters");
    }
    for(unsigned rate:{44100U,48000U,88200U,96000U})for(unsigned q:{0U,1U})for(unsigned policy:{0U,1U,2U}) {
        check(run(rate,q,policy,32,false)==run(rate,q,policy,257,false),"time ramp block invariance");++comparisons;
    }
    check(run(48000,1,1,32,true)==run(48000,1,1,257,true),"rebased partial input equivalence");++comparisons;
    auto c=boiledegg_default_config(48000,1);c.max_block_size=32;auto b=cfg();b.io_contract=2;
    check(boiledegg_validate_backend_config(&c,&b)==BOILEDEGG_UNSUPPORTED_MODE,"time automation not a fixed-I/O mode");
    std::cout<<samples<<" independent T/p integral samples; "<<comparisons<<" paired output tests; bounds/EOS/backpressure passed\n";
}catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}}
