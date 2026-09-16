// Direct public-SDK lifecycle checks for the integrated static stereo repair.
#include <boiled_egg/boiled_egg.hpp>
#include <algorithm>
#include <array>
#include <cmath>
#include <cstdint>
#include <iostream>
#include <span>
#include <stdexcept>
#include <vector>
using Audio=std::array<std::vector<float>,2>;
static void require(bool v,const char* why){if(!v)throw std::runtime_error(why);}
static Audio input(unsigned rate){
    Audio x{std::vector<float>(16001),std::vector<float>(16001)};unsigned rng=26091641;
    for(unsigned i=0;i<x[0].size();++i){rng=1664525U*rng+1013904223U;double t=double(i)/rate;
        x[0][i]=(i<311 || (i>5900 && i<7001))?0.F:float(.1*std::sin(6.283185307179586*(79*t+910*t*t))+.03*(double(rng>>8U)/16777216.-.5));
        x[1][i]=-.375F*x[0][i];}
    return x;
}
static Audio run(boiled_egg::engine& e,Audio x,unsigned block,bool inplace,bool empty){
    auto before=e.runtime_info();auto latency=before.realtime_latency_frames;
    for(auto& ch:x)ch.resize(ch.size()+latency,0.F);
    Audio y{std::vector<float>(x[0].size()),std::vector<float>(x[0].size())};
    std::array<float,257> l{},r{};
    for(unsigned pos=0;pos<x[0].size();){auto n=std::min(block,unsigned(x[0].size())-pos);
        if(empty)require(e.process_realtime_nothrow(nullptr,nullptr,0)==BOILEDEGG_OK,"empty callback");
        float* out[]={inplace?x[0].data()+pos:l.data(),inplace?x[1].data()+pos:r.data()};
        const float* in[]={x[0].data()+pos,x[1].data()+pos};
        require(e.process_realtime_nothrow(in,out,n)==BOILEDEGG_OK,"process");
        for(unsigned ch=0;ch<2;++ch)std::copy_n(out[ch],n,y[ch].begin()+pos);pos+=n;
    }
    auto after=e.runtime_info();require(before.realtime_latency_frames==after.realtime_latency_frames &&
        before.realtime_tail_frames==after.realtime_tail_frames && before.capabilities==after.capabilities,"runtime contract");
    double p=0,error=0;
    for(unsigned i=0;i<y[0].size();++i){require(std::isfinite(y[0][i])&&std::isfinite(y[1][i]),"nonfinite");
        if(i<latency)require(y[0][i]==0.F && y[1][i]==0.F,"startup delay");
        double d=y[1][i]+.375*y[0][i];error+=d*d;p+=double(y[0][i])*y[0][i];}
    require(p>1e-20,"silent false pass");require(std::sqrt(error/p)<=1e-5,"stereo invariant");return y;
}
int main(){try{
    unsigned cases=0;
    for(unsigned rate:{44100U,48000U,88200U,96000U})for(unsigned quality:{0U,1U})for(unsigned policy:{0U,1U,2U}){
        auto c=boiledegg_default_config(rate,2);c.max_block_size=257;
        auto b=boiledegg_default_backend_config();b.backend_id=BOILEDEGG_BACKEND_PHASE_VOCODER;
        b.flags=BOILEDEGG_BACKEND_ALLOW_EXPERIMENTAL;b.quality_mode=quality;b.formant_policy=policy;
        b.initial_pitch_ratio=1.5F;b.initial_formant_ratio=policy?.8F:1.F;b.io_contract=BOILEDEGG_IO_REALTIME;
        boiled_egg::engine first(c,b);auto state=first.backend_parameter_state();auto x=input(rate);
        auto expected=run(first,x,32,false,false);first.reset();
        require(expected==run(first,x,257,true,true),"reset/inplace/empty replay");
        boiled_egg::engine restored(c,b);if(policy)restored.set_formant_ratio(1.25F);
        restored.set_backend_parameter_state(state);restored.reset();
        require(expected==run(restored,x,31,false,true),"state replay");
        first.reset();restored.reset();auto before=first.runtime_info();
        std::array<float,257> l{},r{};l.fill(123.F);r.fill(123.F);float* out[]={l.data(),r.data()};
        const float* in[]={x[0].data(),x[1].data()};auto invalid=boiled_egg::parameter_event::pitch_ratio(0,3.F);
        require(first.process_realtime_nothrow(in,out,257,std::span(&invalid,1))!=BOILEDEGG_OK,"invalid pitch accepted");
        require(std::all_of(l.begin(),l.end(),[](float v){return v==123.F;}) && std::all_of(r.begin(),r.end(),[](float v){return v==123.F;}),"invalid output mutation");
        require(first.pitch_ratio()==state.pitch_ratio,"invalid pitch mutation");
        require(first.runtime_info().realtime_latency_frames==before.realtime_latency_frames,"invalid delay mutation");
        require(run(first,x,32,false,false)==run(restored,x,32,false,false),"invalid history mutation");++cases;
    }
    std::cout<<cases<<" static lifecycle cases: reset/inplace/empty/state/invalid purity\n";return 0;
}catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}}
