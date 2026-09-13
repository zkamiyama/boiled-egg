#include "boiled_egg_pv_rt.hpp"
#include "boiled_egg_multires_rt.hpp"
#include <algorithm>
#include <array>
#include <cmath>
#include <iostream>
#include <stdexcept>
#include <vector>
using namespace boiled_egg::research;
using audio=std::array<std::vector<float>,2>;
static void require(bool value,const char* reason) { if(!value) throw std::runtime_error(reason); }
static audio source(unsigned length) {
    audio a{std::vector<float>(length),std::vector<float>(length)};unsigned random=991;
    for(unsigned i=0;i<length;++i) {
        random=random*1664525U+1013904223U;
        a[0][i]=.2F*std::sin(.0213F*static_cast<float>(i))+.04F*(static_cast<float>(random>>8U)/16777216.F-.5F);
        a[1][i]=-.5F*a[0][i];
    }
    return a;
}
template<class Engine> audio render(Engine& h,const audio& x,unsigned block,bool automate=false,bool reset_mid=false) {
    audio y;std::array<std::vector<float>,2> scratch{std::vector<float>(16384),std::vector<float>(16384)};
    float* out[]={scratch[0].data(),scratch[1].data()};
    auto drain=[&] { while(h.available()) {
        auto n=h.pull(out,16384); require(n>0,"pull progress");
        for(unsigned ch=0;ch<2;++ch) y[ch].insert(y[ch].end(),scratch[ch].begin(),scratch[ch].begin()+n);
    }};
    if(reset_mid) { const float* p[]={x[0].data(),x[1].data()};for(unsigned i=0;i<1100;++i)h.push(p,1); h.reset(); }
    const unsigned event_positions[]={777U,1281U,2176U,3719U};unsigned event=0;
    for(unsigned pos=0;pos<x[0].size();) {
        if(automate && event<4 && pos==event_positions[event]) { h.set_formant_ratio(event%2?2.F:.5F); ++event; }
        auto n=std::min<unsigned>(block,static_cast<unsigned>(x[0].size())-pos);
        if(automate && event<4 && event_positions[event]>pos)n=std::min(n,event_positions[event]-pos);
        const float* p[]={x[0].data()+pos,x[1].data()+pos}; h.push(p,n); drain(); pos+=n;
    }
    h.flush();drain();require(y[0].size()==x[0].size(),"exact duration");
    for(auto& ch:y)for(float v:ch)require(std::isfinite(v),"finite output");
    const auto stats=h.execution_stats();require(stats.frame_overruns==0,"cooperative overrun");
    return y;
}
int main() { try {
    unsigned comparisons=0;
    auto f=boiledegg_research_default_features();f.timing_policy=1;f.rate_policy=1;
    for(unsigned rate:{48000U,96000U})for(unsigned mode:{1U,3U,4U,9U})for(unsigned formant:{0U,1U,2U}) {
        const auto x=source(6001);
        for(float pitch:{.5F,2.F})for(bool automate:{false,true}) {
            if(automate && !formant)continue;
            audio expected;
            for(unsigned variant=0;variant<4;++variant) {
                auto e=boiledegg_research_default_execution();e.scheduled=variant>=2;e.simd=variant%2;
                audio actual;
                if(mode==9) {
                    auto c=boiledegg_research_multires_rt_default_config(rate,2,257);c.formant_mode=formant;c.initial_pitch_ratio=pitch;
                    multires_rt_engine h(c,f,e);actual=render(h,x,variant==3?257:32,automate);
                } else {
                    auto c=boiledegg_research_pv_rt_default_config(rate,2,257);c.fft_size=1024;c.analysis_hop=256;
                    c.mode=mode;c.formant_mode=formant;c.initial_pitch_ratio=pitch;
                    pv_rt_engine h(c,f,e);actual=render(h,x,variant==3?257:32,automate);
                }
                if(!variant)expected=actual;else {require(expected==actual,"scheduled/SIMD/automation exact equality");++comparisons;}
            }
        }
    }
    for(unsigned mode:{1U,3U,4U,9U})for(unsigned n:{0U,1U,31U,1031U,4099U}) {
        auto x=source(std::max(1101U,n));auto short_x=x;for(auto& ch:short_x)ch.resize(n);
        auto e=boiledegg_research_default_execution();e.scheduled=e.simd=1;
        if(mode==9) {
            auto c=boiledegg_research_multires_rt_default_config(48000,2,64);c.initial_pitch_ratio=.5F;
            multires_rt_engine h(c,f,e);auto a=render(h,short_x,31);h.reset();auto b=render(h,short_x,64);require(a==b,"reset and short input");
        } else {
            auto c=boiledegg_research_pv_rt_default_config(48000,2,64);c.fft_size=1024;c.mode=mode;c.initial_pitch_ratio=.5F;
            pv_rt_engine h(c,f,e);auto a=render(h,short_x,31);h.reset();auto b=render(h,short_x,64);require(a==b,"reset and short input");
            h.reset();auto clean=render(h,x,31);h.reset();auto mid=render(h,x,31,false,true);require(clean==mid,"in-flight reset");
        }
    }
    auto c=boiledegg_research_pv_rt_default_config(48000,1,64);auto e=boiledegg_research_default_execution();e.scheduled=1;
    boiledegg_research_pv_rt_result status{};c.initial_time_ratio=2;
    require(!boiledegg_research_pv_rt_create_exec(&c,&f,&e,&status),"scheduled time restriction");
    c.initial_time_ratio=1;c.analysis_hop=32;
    require(!boiledegg_research_pv_rt_create_exec(&c,&f,&e,&status),"minimum scheduling hop");
    c.analysis_hop=256;auto* h=boiledegg_research_pv_rt_create_exec(&c,&f,&e,&status);require(h,"create");
    float z=0;const float* in[]={&z};require(boiledegg_research_pv_rt_push(h,in,1)==0,"first input");
    require(boiledegg_research_pv_rt_set_pitch_ratio(h,2)!=0,"dynamic pitch explicitly rejected");
    require(boiledegg_research_pv_rt_set_time_ratio(h,2)!=0,"dynamic time explicitly rejected");
    boiledegg_research_pv_rt_destroy(h);
    std::cout<<comparisons<<" exact scheduling/SIMD comparisons; short/reset/automation contracts passed\n";
} catch(const std::exception& e) {std::cerr<<e.what()<<'\n';return 1;} }
