#pragma once
#include <boiled_egg/boiled_egg.hpp>
#include <algorithm>
#include <array>
#include <chrono>
#include <cmath>
#include <cstdint>
#include <stdexcept>
#include <vector>
namespace detail_test {
inline void require(bool b,const char* message){if(!b)throw std::runtime_error(message);}
using Audio=std::array<std::vector<float>,2>;
inline Audio signal(unsigned n,unsigned rate){
    Audio x{std::vector<float>(n),std::vector<float>(n)};
    for(unsigned i=0;i<n;++i){double t=double(i)/rate; x[0][i]=float(.08*std::sin(2*3.141592653589793*173*t+.2)+.035*std::sin(2*3.141592653589793*519*t));x[1][i]=-.5f*x[0][i];}
    return x;
}
inline boiledegg_backend_config options(bool detail,float pitch,unsigned io){
    auto b=boiledegg_default_backend_config();b.backend_id=BOILEDEGG_BACKEND_PHASE_VOCODER;
    b.formant_policy=BOILEDEGG_FORMANT_POLICY_MONOPHONIC;b.io_contract=io;
    b.flags=BOILEDEGG_BACKEND_ALLOW_EXPERIMENTAL|(detail?BOILEDEGG_BACKEND_FORMANT_LOW_DETAIL:0u);
    b.initial_pitch_ratio=pitch;return b;
}
using Clock=std::chrono::steady_clock;
inline double seconds(Clock::time_point a){return std::chrono::duration<double>(Clock::now()-a).count();}
struct Result {
    Audio pcm;
    boiledegg_runtime_info info{};
    double service_seconds=0,flush_seconds=0,max_service_seconds=0,setup_seconds=0;
    unsigned input_blocks=0,service_period_exceedances=0;
    std::vector<double> services;
};
/* All output/timing storage is allocated before audio calls. service groups one
   push and its required drain; fixed-I/O uses the actual public callback.
   Stream service time is not a callback deadline claim. */
inline Result run(boiled_egg::engine& engine,const Audio& original,unsigned rate,unsigned channels,unsigned block,bool rt,bool events=false){
    Result result;result.info=engine.runtime_info();Audio input=original;
    const unsigned length=unsigned(input[0].size());
    const unsigned n=length+(rt?result.info.realtime_latency_frames:0u);
    for(auto& v:input)v.resize(n,0.f);
    for(auto& v:result.pcm)v.resize(n,0.f);
    result.services.reserve(n/block+2);unsigned at=0,out_at=0;
    auto drain=[&]{unsigned guard=0;
        while(engine.available()){
            require(++guard<100000 && out_at<n,"unexpected output length/progress");
            float* out[]={result.pcm[0].data()+out_at,result.pcm[1].data()+out_at};
            auto made=engine.pull(out,std::min(block,n-out_at)); require(made>0,"zero drain progress");out_at+=made;
        }
    };
    while(at<n){unsigned count=std::min(block,n-at);const float* in[]={input[0].data()+at,input[1].data()+at};
        std::array<boiled_egg::parameter_event,2> ev{};unsigned ec=0;
        if(events)for(unsigned i:{1024u,3072u})if(i>=at&&i<at+count)ev[ec++]=boiled_egg::parameter_event::formant_ratio(i-at,i==1024?1.15f:.9f);
        auto start=Clock::now();
        if(rt){float* out[]={result.pcm[0].data()+at,result.pcm[1].data()+at};require(engine.process_realtime_nothrow(in,out,count,std::span(ev.data(),ec))==BOILEDEGG_OK,"public realtime failed");at+=count;out_at=at;}
        else {require(!events,"stream events not used in this driver");auto used=engine.push(in,count);require(used>0,"push stalled");at+=used;drain();}
        double elapsed=seconds(start); result.services.push_back(elapsed);result.service_seconds+=elapsed;
        result.max_service_seconds=std::max(result.max_service_seconds,elapsed);result.service_period_exceedances+=elapsed>double(count)/rate;++result.input_blocks;
    }
    if(!rt){auto start=Clock::now();engine.flush();drain();result.flush_seconds=seconds(start);require(engine.drained(),"not drained");}
    require(out_at==n,"wrong final length");double energy=0;
    for(unsigned ch=0;ch<channels;++ch)for(float v:result.pcm[ch]){require(std::isfinite(v),"nonfinite audio");energy+=double(v)*v;}
    require(energy>1e-12,"nonzero input rendered silence");return result;
}
inline Result render(const Audio& input,unsigned rate,unsigned channels,unsigned block,float pitch,bool detail,bool rt){
    auto c=boiledegg_default_config(rate,channels);c.max_block_size=block;
    auto start=Clock::now();boiled_egg::engine engine(c,options(detail,pitch,rt?BOILEDEGG_IO_REALTIME:BOILEDEGG_IO_STREAMING));double setup=seconds(start);
    auto r=run(engine,input,rate,channels,block,rt);r.setup_seconds=setup;return r;
}
}
