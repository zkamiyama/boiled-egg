#include "boiled_egg_pv_rt.h"
#include <algorithm>
#include <array>
#include <chrono>
#include <cmath>
#include <cstdint>
#include <ctime>
#include <iomanip>
#include <iostream>
#include <numeric>
#include <string>
#include <vector>

namespace {
double cpu_us() {
    timespec t{};
    if(clock_gettime(CLOCK_THREAD_CPUTIME_ID,&t)) return -1;
    return 1e6*static_cast<double>(t.tv_sec)+1e-3*static_cast<double>(t.tv_nsec);
}
double quantile(std::vector<double> v,double q) {
    auto k=static_cast<std::size_t>(q*static_cast<double>(v.size()-1));
    std::nth_element(v.begin(),v.begin()+static_cast<std::ptrdiff_t>(k),v.end());return v[k];
}
}
int main(int argc,char** argv){
    const bool scaled=argc==2 && std::string(argv[1])=="--scale-window";
    if(argc>2 || (argc==2 && !scaled))return 1;
    if(cpu_us()<0)return 1;
    std::cout<<"rate,channels,block,fft,hop,semitones,mode,wall_mean_us,wall_p99_us,cpu_mean_us,cpu_p99_us,cpu_max_us,deadline_us,cpu_p99_ratio,wall_p99_ratio\n";
    for(std::uint32_t rate:{48000U,96000U})for(std::uint32_t channels:{1U,2U})
    for(std::uint32_t block:{32U,64U})for(int st:{-12,-7,-3,3,7,12})
    for(auto mode:{BOILEDEGG_RESEARCH_PV_RT_PHASE_LOCKED,BOILEDEGG_RESEARCH_PV_RT_FUZZY_NOISE,BOILEDEGG_RESEARCH_PV_RT_FUZZY}){
        auto c=boiledegg_research_pv_rt_default_config(rate,channels,block);
        c.fft_size=scaled && rate==96000 ? 2048U : 1024U;c.analysis_hop=c.fft_size/4U;c.mode=mode;c.formant_mode=BOILEDEGG_RESEARCH_PV_RT_FORMANT_HARMONIC;
        c.initial_pitch_ratio=static_cast<float>(std::pow(2.0,st/12.0));
        boiledegg_research_pv_rt_result result{};auto* h=boiledegg_research_pv_rt_create(&c,&result);if(!h)return 2;
        std::array<std::vector<float>,2> input{std::vector<float>(block),std::vector<float>(block)};
        std::array<std::vector<float>,2> output{std::vector<float>(block*32U),std::vector<float>(block*32U)};
        const float* in[]={input[0].data(),input[1].data()};float* out[]={output[0].data(),output[1].data()};
        std::vector<double> wall,cpu;wall.reserve(1400);cpu.reserve(1400);
        std::uint64_t position=0,produced=0;std::uint32_t rng=1234567;
        for(std::uint32_t iteration=0;iteration<1600;++iteration){
            for(std::uint32_t i=0;i<block;++i){
                rng=1664525U*rng+1013904223U;
                float noise=(static_cast<float>(rng>>8U)/16777216.0F-.5F)*.06F;
                float t=static_cast<float>(position+i)/static_cast<float>(rate);
                input[0][i]=.25F*std::sin(6.283185307F*120*t)+.18F*std::sin(6.283185307F*720*t)
                    +.10F*std::sin(6.283185307F*6200*t)+noise+((position+i)%12000<2?.3F:0.F);
                input[1][i]=-.5F*input[0][i]+.03F*std::sin(6.283185307F*300*t);
            }
            auto wb=std::chrono::steady_clock::now();double cb=cpu_us();
            result=boiledegg_research_pv_rt_push(h,in,block);
            while(boiledegg_research_pv_rt_available(h))produced+=boiledegg_research_pv_rt_pull(h,out,block*32U);
            double ce=cpu_us();auto we=std::chrono::steady_clock::now();
            if(result)return 3;
            if(iteration>=200){wall.push_back(std::chrono::duration<double,std::micro>(we-wb).count());cpu.push_back(ce-cb);}
            position+=block;
        }
        if(boiledegg_research_pv_rt_flush(h))return 4;
        while(boiledegg_research_pv_rt_available(h))produced+=boiledegg_research_pv_rt_pull(h,out,block*32U);
        if(produced!=position)return 5;
        boiledegg_research_pv_rt_destroy(h);
        auto mean=[](const std::vector<double>& x){return std::accumulate(x.begin(),x.end(),0.)/static_cast<double>(x.size());};
        double deadline=1e6*block/rate,cp99=quantile(cpu,.99),wp99=quantile(wall,.99);
        std::cout<<rate<<','<<channels<<','<<block<<','<<c.fft_size<<','<<c.analysis_hop<<','<<st<<','<<static_cast<int>(mode)<<','<<std::fixed<<std::setprecision(6)
            <<mean(wall)<<','<<wp99<<','<<mean(cpu)<<','<<cp99<<','<<*std::max_element(cpu.begin(),cpu.end())<<','
            <<deadline<<','<<cp99/deadline<<','<<wp99/deadline<<'\n';
    }
}
