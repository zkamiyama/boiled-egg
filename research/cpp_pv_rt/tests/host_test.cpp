#include "boiled_egg_research_host.hpp"
#include "boiled_egg_pv_rt.hpp"
#include "boiled_egg_multires_rt.hpp"
#include <algorithm>
#include <array>
#include <cmath>
#include <iostream>
#include <limits>
#include <memory>
#include <stdexcept>
#include <vector>
using audio=std::array<std::vector<float>,2>;
using host_ptr=std::unique_ptr<boiledegg_research_host_handle,decltype(&boiledegg_research_host_destroy)>;
static void check(bool x,const char* what){if(!x)throw std::runtime_error(what);}
static audio source(unsigned length) {
    audio a{std::vector<float>(length),std::vector<float>(length)};unsigned r=2017;
    for(unsigned i=0;i<length;++i){r=1664525U*r+1013904223U;a[0][i]=.13F*std::sin(.0571F*static_cast<float>(i))+.01F*(static_cast<float>(r>>8U)/16777216.F-.5F);a[1][i]=-.5F*a[0][i];}
    return a;
}
static const std::array<std::pair<unsigned,float>,5> changes{{{0,1.2F},{799,.5F},{1639,2.F},{4097,.8F},{6011,1.F}}};
static audio run_host(boiledegg_research_host_handle* h,const audio& x,unsigned block,bool events,bool inplace=false) {
    auto n=static_cast<unsigned>(x[0].size());audio y{std::vector<float>(n),std::vector<float>(n)};
    if(inplace)y=x;
    for(unsigned pos=0;pos<n;pos+=block){unsigned count=std::min(block,n-pos);
        std::array<boiledegg_research_host_event,5> ev{};unsigned e=0;
        if(events)for(auto [at,v]:changes)if(at>=pos && at<pos+count)ev[e++]={sizeof(ev[0]),at-pos,v,0};
        const float* in[]={inplace?y[0].data()+pos:x[0].data()+pos,inplace?y[1].data()+pos:x[1].data()+pos};float* out[]={y[0].data()+pos,y[1].data()+pos};
        check(boiledegg_research_host_process(h,in,out,count,ev.data(),e)==0,"fixed host process");
    }
    boiledegg_research_host_stats stats{};stats.struct_size=sizeof(stats);check(boiledegg_research_host_get_stats(h,&stats)==0,"host stats");
    check(stats.underruns==0 && stats.execution.frame_overruns==0,"zero audio/scheduler underruns");return y;
}
template<class Engine> static audio run_reference(Engine& h,const audio& x,bool events) {
    audio y;float a[16384],b[16384];float* out[]={a,b};unsigned event=0;
    auto drain=[&]{while(h.available()){auto n=h.pull(out,16384);check(n>0,"reference pull progress");y[0].insert(y[0].end(),a,a+n);y[1].insert(y[1].end(),b,b+n);}};
    for(unsigned pos=0;pos<x[0].size();++pos){
        if(events && event<changes.size() && changes[event].first==pos)h.set_formant_ratio(changes[event++].second);
        const float* in[]={x[0].data()+pos,x[1].data()+pos};h.push(in,1);drain();
    }
    h.flush();drain();return y;
}
int main(){try{
    unsigned cases=0;
    for(unsigned rate:{44100U,48000U,96000U})for(unsigned profile:{0U,1U,2U,3U,4U})for(float pitch:{.5F,1.F,2.F}) {
        auto c=boiledegg_research_host_default_config(rate,2,257);c.profile=profile;c.pitch_ratio=pitch;
        boiledegg_research_pv_rt_result status{};host_ptr h(boiledegg_research_host_create(&c,&status),boiledegg_research_host_destroy);check(h && status==0,"host create");
        auto latency=boiledegg_research_host_latency_frames(h.get());check(latency>0,"declared delay");
        auto x=source(12017);for(auto& a:x)a.resize(static_cast<std::size_t>(12017)+latency,0.F);
        for(bool events:{false,true}) {
            check(boiledegg_research_host_reset(h.get())==0,"host reset");
            check(boiledegg_research_host_request_formant(h.get(),1.F)==0,"reset target");
            auto y=run_host(h.get(),x,32,events);
            auto f=boiledegg_research_default_features();f.timing_policy=f.rate_policy=1;
            audio reference;
            if(profile==3){auto m=boiledegg_research_multires_rt_default_config(rate,2,257);m.initial_pitch_ratio=pitch;
                boiled_egg::research::multires_rt_engine r(m,f);reference=run_reference(r,x,events);
            }else{auto p=boiledegg_research_pv_rt_default_config(rate,2,257);p.fft_size=profile==0?2048:1024;p.initial_pitch_ratio=pitch;p.formant_mode=1;
                p.mode=profile==2?3:profile==4?4:1;boiled_egg::research::pv_rt_engine r(p,f);reference=run_reference(r,x,events);}
            for(unsigned ch=0;ch<2;++ch){check(std::all_of(y[ch].begin(),y[ch].begin()+latency,[](float v){return v==0.F;}),"latency zero prefix");
                check(std::equal(y[ch].begin()+latency,y[ch].end(),reference[ch].begin()),"sample-exact fixed delayed output");}
            check(boiledegg_research_host_reset(h.get())==0,"reset2");boiledegg_research_host_request_formant(h.get(),1.F);
            check(y==run_host(h.get(),x,257,events,true),"in-place and event partition invariance");
            check(boiledegg_research_host_latency_frames(h.get())==latency,"formants keep latency fixed");++cases;
        }
    }
    auto c=boiledegg_research_host_default_config(48000,2,32);boiledegg_research_pv_rt_result status{};
    host_ptr h(boiledegg_research_host_create(&c,&status),boiledegg_research_host_destroy);check(h!=nullptr,"validation handle");
    float a[32]{},b[32]{};float* out[]={a,b};const float* in[]={a,b};
    boiledegg_research_host_stats before{},after{};before.struct_size=sizeof(before);after.struct_size=sizeof(after);boiledegg_research_host_get_stats(h.get(),&before);
    boiledegg_research_host_event bad{sizeof(bad),32,1.F,0};
    check(boiledegg_research_host_process(h.get(),in,out,32,&bad,1)!=0,"end-of-block event rejected");
    bad.sample_offset=1;bad.formant_ratio=std::numeric_limits<float>::quiet_NaN();
    check(boiledegg_research_host_process(h.get(),in,out,32,&bad,1)!=0,"NaN rejected");
    boiledegg_research_host_get_stats(h.get(),&after);check(before.input_frames==after.input_frames,"invalid block is transactional");
    boiledegg_research_host_event order[2]={{sizeof(bad),3,1.F,0},{sizeof(bad),2,1.F,0}};
    check(boiledegg_research_host_process(h.get(),in,out,32,order,2)!=0,"unsorted rejected");
    order[1].sample_offset=3;order[1].formant_ratio=2.F;
    check(boiledegg_research_host_process(h.get(),in,out,32,order,2)==0,"same offset accepted");
    check(boiledegg_research_host_get_target(h.get())==2.F,"last event wins");
    boiledegg_research_host_state s{};s.struct_size=sizeof(s);check(boiledegg_research_host_state_get(h.get(),&s)==0,"state snapshot");
    check(s.formant_ratio==2.F,"state target");s.formant_ratio=.75F;check(boiledegg_research_host_state_request(h.get(),&s)==0,"state request");
    check(boiledegg_research_host_process(h.get(),nullptr,out,32,nullptr,0)==0,"silence and mailbox");
    check(boiledegg_research_host_get_target(h.get())==.75F,"restored state");s.version=999;check(boiledegg_research_host_state_request(h.get(),&s)!=0,"state version");
    boiled_egg::research::fixed_latency_engine wrapper(c);
    auto moved=std::move(wrapper);check(wrapper.native_handle()==nullptr,"RAII move clears source");
    check(moved.request_formant(1.1F)==0 && moved.process(nullptr,out,32)==0,"RAII realtime bridge");
    check(moved.latency_frames()>0 && moved.reset()==0,"RAII delay/reset");
    std::cout<<cases<<" fixed-delay/event waveform comparisons and host validation passed\n";
}catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}}
