#include "boiled_egg_pv_rt.hpp"
#include "boiled_egg_multires_rt.hpp"
#include <algorithm>
#include <array>
#include <chrono>
#include <cmath>
#include <cstdint>
#include <ctime>
#include <iomanip>
#include <iostream>
#include <numeric>
#include <stdexcept>
#include <string>
#include <vector>

namespace {
double cpu_us() {
    timespec t{};
    if(clock_gettime(CLOCK_THREAD_CPUTIME_ID,&t)) throw std::runtime_error("thread CPU clock unavailable");
    return 1e6*static_cast<double>(t.tv_sec)+1e-3*static_cast<double>(t.tv_nsec);
}
double quantile(std::vector<double> v,double q) {
    auto k=static_cast<std::size_t>(q*static_cast<double>(v.size()-1));
    std::nth_element(v.begin(),v.begin()+static_cast<std::ptrdiff_t>(k),v.end());return v[k];
}
template<class Engine>
void measure(Engine& h,std::uint32_t rate,std::uint32_t channels,std::uint32_t block,
             int st,const char* profile,bool candidate,int repeat) {
    constexpr unsigned warmup=200, iterations=1400;
    std::array<std::vector<float>,2> input{std::vector<float>(block),std::vector<float>(block)};
    std::array<std::vector<float>,2> output{std::vector<float>(block*32U),std::vector<float>(block*32U)};
    const float* in[]={input[0].data(),input[1].data()};float* out[]={output[0].data(),output[1].data()};
    std::vector<double> wall,cpu;wall.reserve(iterations-warmup);cpu.reserve(iterations-warmup);
    std::uint64_t position=0,produced=0,first_output=0;std::uint32_t rng=1234567;
    for(unsigned iteration=0;iteration<iterations;++iteration){
        for(std::uint32_t i=0;i<block;++i){
            rng=1664525U*rng+1013904223U;
            float noise=(static_cast<float>(rng>>8U)/16777216.0F-.5F)*.06F;
            float t=static_cast<float>(position+i)/static_cast<float>(rate);
            input[0][i]=.25F*std::sin(6.283185307F*120*t)+.18F*std::sin(6.283185307F*720*t)
                +.10F*std::sin(6.283185307F*6200*t)+noise+((position+i)%12000<2?.3F:0.F);
            input[1][i]=-.5F*input[0][i]+.03F*std::sin(6.283185307F*300*t);
        }
        auto wb=std::chrono::steady_clock::now();double cb=cpu_us();
        h.push(in,block);
        while(h.available()) {
            auto n=h.pull(out,block*32U);if(!n)throw std::runtime_error("pull stalled");
            produced+=n;
        }
        double ce=cpu_us();auto we=std::chrono::steady_clock::now();
        if(iteration>=warmup){wall.push_back(std::chrono::duration<double,std::micro>(we-wb).count());cpu.push_back(ce-cb);}
        position+=block;if(produced && !first_output)first_output=position;
    }
    h.flush();while(h.available())produced+=h.pull(out,block*32U);
    if(produced!=position)throw std::runtime_error("duration mismatch");
    auto mean=[](const auto& x){return std::accumulate(x.begin(),x.end(),0.)/static_cast<double>(x.size());};
    double deadline=1e6*block/rate,cp99=quantile(cpu,.99),wp99=quantile(wall,.99);
    std::cout<<repeat<<','<<rate<<','<<channels<<','<<block<<','<<st<<','<<profile<<','
        <<(candidate?"candidate":"legacy")<<','<<iterations-warmup<<','<<std::fixed<<std::setprecision(6)
        <<mean(wall)<<','<<wp99<<','<<mean(cpu)<<','<<cp99<<','<<*std::max_element(cpu.begin(),cpu.end())<<','
        <<deadline<<','<<cp99/deadline<<','<<wp99/deadline<<','<<first_output<<','<<h.latency_frames()<<'\n'<<std::flush;
}
}
int main(int argc,char** argv) {
    try {
        if(argc!=2)throw std::runtime_error("usage: features_bench REPEAT_INDEX(1..3)");
        const int repeat=std::stoi(argv[1]);if(repeat<1||repeat>3)throw std::runtime_error("repeat outside1..3");
        std::cout<<"repeat,rate,channels,block,shift,profile,variant,callbacks,wall_mean_us,wall_p99_us,cpu_mean_us,cpu_p99_us,cpu_max_us,deadline_us,cpu_p99_ratio,wall_p99_ratio,first_output_input_frames,latency_hint_frames\n";
        for(unsigned rate:{48000U,96000U})for(unsigned channels:{1U,2U})for(unsigned block:{32U,64U})
        for(int st:{-12,-7,-3,3,7,12})for(const char* name:{"general","transient","fuzzy","multires"})for(unsigned order:{0U,1U}) {
            const bool candidate=(order+static_cast<unsigned>(repeat))%2U!=0;
            auto f=boiledegg_research_default_features();
            if(candidate){f.timing_policy=BOILEDEGG_RESEARCH_TIMING_CENTERED;f.rate_policy=BOILEDEGG_RESEARCH_RATE_SCALED;}
            const auto pitch=static_cast<float>(std::pow(2.,st/12.));
            if(std::string(name)=="multires") {
                auto c=boiledegg_research_multires_rt_default_config(rate,channels,block);c.initial_pitch_ratio=pitch;
                boiled_egg::research::multires_rt_engine h(c,f);measure(h,rate,channels,block,st,name,candidate,repeat);
            } else {
                auto c=boiledegg_research_pv_rt_default_config(rate,channels,block);
                c.fft_size=std::string(name)=="general"?2048U:1024U;c.analysis_hop=256;
                if(!candidate && rate==96000){c.fft_size*=2;c.analysis_hop*=2;}
                c.formant_mode=BOILEDEGG_RESEARCH_PV_RT_FORMANT_HARMONIC;c.initial_pitch_ratio=pitch;
                c.mode=std::string(name)=="fuzzy"?BOILEDEGG_RESEARCH_PV_RT_FUZZY:BOILEDEGG_RESEARCH_PV_RT_PHASE_LOCKED;
                boiled_egg::research::pv_rt_engine h(c,f);measure(h,rate,channels,block,st,name,candidate,repeat);
            }
        }
    } catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}
}
