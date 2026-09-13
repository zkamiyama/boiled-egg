#include "boiled_egg_research_features.h"
#include "boiled_egg_pv_rt.hpp"
#include "boiled_egg_multires_rt.hpp"
#include <algorithm>
#include <array>
#include <cmath>
#include <cstdint>
#include <iostream>
#include <limits>
#include <memory>
#include <stdexcept>
#include <vector>

using namespace boiled_egg::research;
using audio = std::vector<std::vector<float>>;
void require(bool ok, const char* message) { if (!ok) throw std::runtime_error(message); }

audio source(std::size_t frames, unsigned channels) {
    audio x(channels, std::vector<float>(frames));
    for (std::size_t i=0; i<frames; ++i) {
        float value = .17F*std::sin(.031F*static_cast<float>(i)) + .09F*std::sin(.141F*static_cast<float>(i));
        for (unsigned ch=0; ch<channels; ++ch) x[ch][i] = ch%2 ? -.5F*value : value;
    }
    return x;
}

template<class Engine>
audio process(Engine& h, const audio& x, unsigned block, float time, bool change_formant=false) {
    audio y(x.size()), work(x.size(), std::vector<float>(block*32));
    std::array<const float*,8> in{}; std::array<float*,8> out{};
    for (unsigned ch=0; ch<x.size(); ++ch) out[ch]=work[ch].data();
    auto drain=[&]{
        while (h.available()) {
            unsigned n=h.pull(out.data(),block*32); require(n>0,"pull made no progress");
            for(unsigned ch=0; ch<x.size(); ++ch) y[ch].insert(y[ch].end(),work[ch].begin(),work[ch].begin()+n);
        }
    };
    for (std::size_t i=0;i<x[0].size();i+=block) {
        unsigned n=static_cast<unsigned>(std::min<std::size_t>(block,x[0].size()-i));
        for(unsigned ch=0;ch<x.size();++ch) in[ch]=x[ch].data()+i;
        if(change_formant) h.set_formant_ratio(i<x[0].size()/2 ? .75F : 1.5F);
        h.push(in.data(),n); drain();
    }
    h.flush();drain();
    for(const auto& ch:y) {
        require(ch.size()==static_cast<std::size_t>(std::llround(x[0].size()*static_cast<double>(time))),"exact duration");
        for(float v:ch) require(std::isfinite(v),"finite output");
    }
    return y;
}

audio pv(const audio& x, unsigned rate, unsigned block, unsigned mode, unsigned formant,
         float pitch, float time, boiledegg_research_features f, bool old=false, bool manual=false) {
    auto c=boiledegg_research_pv_rt_default_config(rate,static_cast<unsigned>(x.size()),block);
    c.fft_size=1024;c.analysis_hop=256;c.mode=mode;c.formant_mode=formant;
    c.initial_pitch_ratio=pitch;c.initial_time_ratio=time;
    if(manual){c.fft_size*=2;c.analysis_hop*=2;c.formant_cepstral_order*=2;}
    auto h=old ? std::make_unique<pv_rt_engine>(c) : std::make_unique<pv_rt_engine>(c,f);
    require(h->formant_ratio()==(old?1.0F:f.initial_formant_ratio),"formant getter");
    auto first=process(*h,x,block,time);
    h->reset();require(first==process(*h,x,block,time),"reset exact replay");
    return first;
}

int main() {
    try {
        auto legacy=boiledegg_research_default_features(), centered=legacy;
        centered.timing_policy=BOILEDEGG_RESEARCH_TIMING_CENTERED;
        auto scaled=centered;scaled.rate_policy=BOILEDEGG_RESEARCH_RATE_SCALED;
        const auto x=source(12013,2);
        for(unsigned mode:{1U,3U,4U}) for(unsigned formant:{0U,1U,2U}) {
            for(float p:{.5F,1.0F,2.0F}) {
                require(pv(x,48000,64,mode,formant,p,1,legacy,true)==pv(x,48000,64,mode,formant,p,1,legacy),"legacy create/ex parity");
                require(pv(x,96000,32,mode,formant,p,1,scaled)==pv(x,96000,257,mode,formant,p,1,scaled),"block partition invariance");
                require(pv(x,96000,64,mode,formant,p,1,scaled)==pv(x,96000,64,mode,formant,p,1,centered,false,true),"explicit rate scaling equivalence");
                if(formant) {
                    auto matched=centered;matched.initial_formant_ratio=p;
                    require(pv(x,48000,64,mode,formant,p,1,matched)==pv(x,48000,64,mode,0,p,1,centered),"matching formant/pitch cancels envelope EQ");
                }
            }
        }
        for(float time:{.25F,.5F,1.0F,2.0F,4.0F}) for(float p:{.25F,.5F,1.0F,2.0F,4.0F})
            (void)pv(source(2049,1),48000,31,3,1,p,time,centered);
        for(unsigned n:{0U,1U,31U,513U}) (void)pv(source(n,1),96000,31,3,1,.5F,1,scaled);
        for(unsigned rate:{48000U,96000U}) {
            auto c=boiledegg_research_multires_rt_default_config(rate,2,32);
            c.initial_pitch_ratio=1.5F;c.formant_mode=1;
            multires_rt_engine a(c), b(c,legacy);
            require(process(a,x,32,1)==process(b,x,32,1),"legacy multires create/ex parity");
            auto f=scaled;f.initial_formant_ratio=.8F;
            multires_rt_engine h(c,f);auto out=process(h,x,32,1,true);
            require(h.formant_ratio()==1.5F,"automated target retained");
            h.reset();require(out==process(h,x,32,1,true),"multires reset smoothing");
            double error=0,power=0;
            for(std::size_t i=0;i<out[0].size();++i){double d=out[1][i]+.5*out[0][i];error+=d*d;power+=out[0][i]*out[0][i];}
            require(std::sqrt(error/power)<1e-4,"multires channel relation");
        }
        auto c=boiledegg_research_pv_rt_default_config(96000,1,64);c.formant_mode=1;
        boiledegg_research_pv_rt_result r{};
        for(unsigned invalid=0;invalid<6;++invalid){
            auto bad=scaled;
            if(invalid==0)bad.struct_size=4;
            if(invalid==1)bad.version=999;
            if(invalid==2)bad.rate_policy=999;
            if(invalid==3)bad.timing_policy=999;
            if(invalid==4)bad.initial_formant_ratio=std::numeric_limits<float>::quiet_NaN();
            if(invalid==5)bad.initial_formant_ratio=3;
            auto* h=boiledegg_research_pv_rt_create_ex(&c,&bad,&r);
            require(!h && r==BOILEDEGG_RESEARCH_PV_RT_INVALID_CONFIG,"invalid features rejected");
        }
        c.fft_size=16384;c.analysis_hop=4096;
        require(!boiledegg_research_pv_rt_create_ex(&c,&scaled,&r),"scaled FFT overflow rejected");
        std::cout<<"feature compatibility, rate scaling, formant independence, exact duration and reset passed\n";
    } catch(const std::exception& error){std::cerr<<error.what()<<'\n';return 1;}
}
