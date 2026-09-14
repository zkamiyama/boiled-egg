// Test-only direct private-API oracle. Not an independent DSP algorithm and
// not installed/exported as part of the SDK. Public routing is tested against it.
#include "boiled_egg_research_execution.h"
#include "wav_io.hpp"
#include <algorithm>
#include <cmath>
#include <iostream>
#include <memory>
#include <stdexcept>
#include <vector>
int main(int argc,char** argv) {try {
    if(argc!=9)throw std::runtime_error("input output quality policy time pitch formant block");
    WavData x;std::string error;if(!read_wav(argv[1],x,error))throw std::runtime_error(error);
    const unsigned block=std::stoul(argv[8]);
    auto c=boiledegg_research_pv_rt_default_config(x.sample_rate,x.channels,block);
    c.fft_size=std::stoul(argv[3])?1024:2048;c.analysis_hop=256;c.mode=BOILEDEGG_RESEARCH_PV_RT_PHASE_LOCKED;
    c.formant_mode=std::stoul(argv[4]);c.initial_time_ratio=std::stof(argv[5]);c.initial_pitch_ratio=std::stof(argv[6]);
    auto features=boiledegg_research_default_features();features.timing_policy=features.rate_policy=1;
    features.initial_formant_ratio=std::stof(argv[7]);auto execution=boiledegg_research_default_execution();
    boiledegg_research_pv_rt_result status{};
    std::unique_ptr<boiledegg_research_pv_rt_handle,decltype(&boiledegg_research_pv_rt_destroy)> h(
        boiledegg_research_pv_rt_create_exec(&c,&features,&execution,&status),boiledegg_research_pv_rt_destroy);
    if(!h || status)throw std::runtime_error("oracle create");
    std::vector<std::vector<float>> input(x.channels,std::vector<float>(block)),output(x.channels,std::vector<float>(8192));
    std::vector<const float*> in(x.channels);std::vector<float*> out(x.channels);
    for(unsigned ch=0;ch<x.channels;++ch){in[ch]=input[ch].data();out[ch]=output[ch].data();}
    WavData y;y.sample_rate=x.sample_rate;y.channels=x.channels;
    auto drain=[&] {
        while(boiledegg_research_pv_rt_available(h.get())) {
            auto n=boiledegg_research_pv_rt_pull(h.get(),out.data(),8192);if(!n)throw std::runtime_error("oracle pull stalled");
            for(unsigned i=0;i<n;++i)for(unsigned ch=0;ch<x.channels;++ch)y.interleaved.push_back(output[ch][i]);
        }
    };
    const auto frames=x.interleaved.size()/x.channels;
    for(size_t pos=0;pos<frames;pos+=block) {
        auto n=static_cast<unsigned>(std::min<size_t>(block,frames-pos));
        for(unsigned ch=0;ch<x.channels;++ch)for(unsigned i=0;i<n;++i)input[ch][i]=x.interleaved[(pos+i)*x.channels+ch];
        if(boiledegg_research_pv_rt_push(h.get(),in.data(),n))throw std::runtime_error("oracle push");drain();
    }
    if(boiledegg_research_pv_rt_flush(h.get()))throw std::runtime_error("oracle flush");drain();
    if(y.interleaved.size()!=static_cast<size_t>(std::llround(double(frames)*c.initial_time_ratio))*x.channels)throw std::runtime_error("oracle length");
    if(!write_wav_float32(argv[2],y,error))throw std::runtime_error(error);
} catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;} }
