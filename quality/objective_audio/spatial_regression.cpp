#include <boiled_egg/boiled_egg.hpp>
#include <algorithm>
#include <array>
#include <bit>
#include <cmath>
#include <cstdint>
#include <iostream>
#include <span>
#include <stdexcept>
#include <vector>
using Audio=std::array<std::vector<float>,2>;
static void require(bool ok,const char* why){if(!ok)throw std::runtime_error(why);}
static Audio input(unsigned count,float gain) {
    Audio x{std::vector<float>(count),std::vector<float>(count)};unsigned rng=260916;
    for(unsigned i=0;i<count;++i){rng=1664525U*rng+1013904223U;
        x[0][i]=.1f*std::sin(.0217f*float(i))+.03f*(float(rng>>8U)/16777216.f-.5f);
        x[1][i]=gain*x[0][i];}
    return x;
}
static Audio render(Audio x,unsigned rate,unsigned quality,unsigned policy,float pitch,unsigned block,bool realtime,bool dynamic){
    auto c=boiledegg_default_config(rate,2);c.max_block_size=257;
    auto b=boiledegg_default_backend_config();b.backend_id=BOILEDEGG_BACKEND_PHASE_VOCODER;
    b.flags=BOILEDEGG_BACKEND_ALLOW_EXPERIMENTAL|(dynamic?BOILEDEGG_BACKEND_CONTINUOUS_PITCH:0u);
    b.quality_mode=quality;b.formant_policy=policy;b.initial_pitch_ratio=pitch;
    b.io_contract=realtime?BOILEDEGG_IO_REALTIME:BOILEDEGG_IO_STREAMING;
    boiled_egg::engine engine(c,b);Audio result;
    float left[4096]{},right[4096]{};float* out[]={left,right};
    auto drain=[&]{while(engine.available()){auto n=engine.pull(out,4096);require(n!=0,"pull stalled");
        result[0].insert(result[0].end(),left,left+n);result[1].insert(result[1].end(),right,right+n);}};
    if(realtime){const auto latency=engine.runtime_info().realtime_latency_frames;
        for(auto& v:x)v.resize(v.size()+latency,0.f);}
    for(unsigned pos=0;pos<x[0].size();){auto n=std::min(block,static_cast<unsigned>(x[0].size())-pos);
        const float* in[]={x[0].data()+pos,x[1].data()+pos};
        if(realtime){std::array<boiled_egg::parameter_event,2> events{};unsigned ec=0;
            if(dynamic)for(unsigned at:{777U,4101U})if(at>=pos&&at<pos+n)
                events[ec++]=boiled_egg::parameter_event::pitch_ratio(at-pos,at==777U?.75f:1.5f);
            require(engine.process_realtime_nothrow(in,out,n,std::span(events.data(),ec))==BOILEDEGG_OK,"realtime error");
            result[0].insert(result[0].end(),left,left+n);result[1].insert(result[1].end(),right,right+n);pos+=n;
        }else{auto nread=engine.push(in,n);require(nread>0,"push stalled");pos+=nread;drain();}}
    if(!realtime){engine.flush();drain();require(engine.drained(),"not drained");}
    for(auto& channel:result)for(float v:channel)require(std::isfinite(v),"nonfinite output");
    return result;
}
static double error(const Audio& x,double gain){double p=0,e=0;for(unsigned i=0;i<x[0].size();++i){
    double d=x[1][i]-gain*x[0][i];e+=d*d;p+=double(x[0][i])*x[0][i];}require(p>1e-20,"silent false pass");return std::sqrt(e/p);}
int main(){try{
    unsigned total=0,failed=0;double maximum=0;std::uint64_t dynamic_hash=1469598103934665603ULL;
    for(unsigned rate:{48000U,96000U})for(unsigned quality:{0U,1U})for(unsigned policy:{0U,1U,2U})
    for(bool realtime:{false,true})for(float pitch:{.5f,1.f,2.f})for(float gain:{-.375f,.25f,-2.f,0.f}){
        auto x=input(25001,gain);auto a=render(x,rate,quality,policy,pitch,32,realtime,false);
        auto b=render(x,rate,quality,policy,pitch,257,realtime,false);
        require(a==b,"block partition changed samples");double e=error(a,gain);maximum=std::max(maximum,e);
        failed+=e>1e-5;++total;
    }
    unsigned dynamic_cases=0;
    for(unsigned rate:{48000U,96000U})for(unsigned quality:{0U,1U})for(unsigned policy:{0U,1U,2U}){
        auto x=input(14001,-.375f);auto a=render(x,rate,quality,policy,1.f,32,true,true);
        auto b=render(x,rate,quality,policy,1.f,257,true,true);require(a==b,"dynamic partition");
        require(error(a,-.375)<1e-5,"dynamic relation");
        for(auto& ch:a)for(float v:ch){dynamic_hash^=std::bit_cast<std::uint32_t>(v);dynamic_hash*=1099511628211ULL;}
        ++dynamic_cases;
    }
    std::cout<<"static_cases="<<total<<" static_failures="<<failed<<" max_relative="<<maximum
             <<" dynamic_cases="<<dynamic_cases<<" dynamic_hash="<<dynamic_hash<<'\n';return failed?2:0;
}catch(const std::exception&e){std::cerr<<e.what()<<'\n';return 1;}}
