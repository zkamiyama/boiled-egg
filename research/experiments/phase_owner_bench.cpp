// Same-machine cost of the isolated owner refinement, not a hard-RT guarantee.
#include "../cpp_pv_rt/include/boiled_egg_research_host.hpp"
#include <algorithm>
#include <array>
#include <chrono>
#include <cmath>
#include <ctime>
#include <iomanip>
#include <iostream>
#include <numeric>
#include <stdexcept>
#include <vector>
static double cpu(){timespec t{};if(clock_gettime(CLOCK_THREAD_CPUTIME_ID,&t))throw std::runtime_error("clock");return 1e6*double(t.tv_sec)+1e-3*double(t.tv_nsec);}
static double p99(std::vector<double> v){auto k=static_cast<std::size_t>(.99*double(v.size()-1));std::nth_element(v.begin(),v.begin()+k,v.end());return v[k];}
int main(int argc,char** argv){try{
    if(argc!=2)throw std::runtime_error("repeat1..3 required");int repeat=std::stoi(argv[1]);if(repeat<1||repeat>3)throw std::runtime_error("repeat");
    std::cout<<"repeat,rate,channels,block,shift,callbacks,latency_frames,cpu_mean_us,cpu_p99_us,cpu_max_us,wall_p99_us,wall_max_us,cpu_misses,wall_misses,cpu_p99_ratio,frame_overruns,underruns\n";
    for(unsigned rate:{48000U,96000U})for(unsigned block:{32U,64U})for(int st:{-12,-7,-3,3,7,12}){
        auto cfg=boiledegg_research_host_default_config(rate,2,block);cfg.profile=BOILEDEGG_RESEARCH_HOST_FUZZY;
        cfg.pitch_ratio=static_cast<float>(std::pow(2.,st/12.));cfg.formant_ratio=.75F;cfg.scheduled=cfg.simd=1;
        boiled_egg::research::fixed_latency_engine h(cfg);std::array<std::vector<float>,2> in{std::vector<float>(block),std::vector<float>(block)},out=in;
        const float* ip[]={in[0].data(),in[1].data()};float* op[]={out[0].data(),out[1].data()};std::vector<double> times,wall;times.reserve(2000);wall.reserve(2000);unsigned random=903;
        for(unsigned n=0;n<2800;++n){for(unsigned i=0;i<block;++i){random=random*1664525U+1013904223U;float t=float(n*block+i)/float(rate);
            in[0][i]=.23F*std::sin(6.2831853F*120*t)+.09F*std::sin(6.2831853F*3700*t)+.03F*(float(random>>8U)/16777216.F-.5F);
            in[1][i]=-.5F*in[0][i]+.03F*std::cos(6.2831853F*303*t);}
            std::array<boiledegg_research_host_event,4> events{};for(unsigned i=0;i<4;++i)events[i]={sizeof(events[0]),i*block/4,(n+i)%2?.65F:1.7F,0};
            auto start=std::chrono::steady_clock::now();auto begin=cpu();
            auto status=h.process(ip,op,block,events.data(),4);auto end=cpu();auto finish=std::chrono::steady_clock::now();if(status)throw std::runtime_error("host process");
            if(n>=800){times.push_back(end-begin);wall.push_back(std::chrono::duration<double,std::micro>(finish-start).count());}
            for(auto& ch:out)for(float v:ch)if(!std::isfinite(v))throw std::runtime_error("nonfinite output");
        }
        boiledegg_research_host_stats stats{};stats.struct_size=sizeof(stats);
        if(boiledegg_research_host_get_stats(h.native_handle(),&stats)||stats.underruns||stats.execution.frame_overruns)throw std::runtime_error("algorithmic underrun");
        double deadline=1e6*block/rate;auto mean=std::accumulate(times.begin(),times.end(),0.)/times.size();auto cp=p99(times);
        auto misses=[&](const auto& v){return std::count_if(v.begin(),v.end(),[&](double t){return t>deadline;});};
        std::cout<<repeat<<','<<rate<<",2,"<<block<<','<<st<<",2000,"<<h.latency_frames()<<','<<std::fixed<<std::setprecision(6)
            <<mean<<','<<cp<<','<<*std::max_element(times.begin(),times.end())<<','<<p99(wall)<<','<<*std::max_element(wall.begin(),wall.end())<<','
            <<misses(times)<<','<<misses(wall)<<','<<cp/deadline<<','<<stats.execution.frame_overruns<<','<<stats.underruns<<'\n'<<std::flush;
    }
}catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}}
