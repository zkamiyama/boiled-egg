#include <boiled_egg/boiled_egg.hpp>
#include <algorithm>
#include <chrono>
#include <cmath>
#include <cstdint>
#include <iomanip>
#include <iostream>
#include <random>
#include <vector>

using steady_clock_t=std::chrono::steady_clock;

static void run(uint32_t sr,uint32_t block,float pitch){
    auto cfg=boiledegg_default_config(sr,2); cfg.max_block_size=block;
    boiled_egg::engine e(cfg); e.set_pitch_semitones(pitch); e.set_time_ratio(1.0f);
    std::vector<std::vector<float>> in(2,std::vector<float>(block)),out(2,std::vector<float>(block*4));
    std::vector<const float*> ip{in[0].data(),in[1].data()}; std::vector<float*> op{out[0].data(),out[1].data()};
    std::minstd_rand rng(123); std::uniform_real_distribution<float>d(-0.5f,0.5f);
    std::vector<double> us; us.reserve(4000);
    const int blocks=std::max(2000, int(sr*8/block));
    for(int b=0;b<blocks;++b){for(auto& c:in)for(auto& x:c)x=d(rng); auto t0=steady_clock_t::now(); uint32_t off=0;while(off<block){auto a=e.push(ip.data(),block-off);off+=a;while(e.available()){e.pull(op.data(),block*4);}if(!a)break;}auto t1=steady_clock_t::now();us.push_back(std::chrono::duration<double,std::micro>(t1-t0).count());}
    std::sort(us.begin(),us.end()); auto pct=[&](double p){return us[std::min(us.size()-1,(size_t)(p*(us.size()-1)))];};
    const double deadline=1e6*block/sr; double mean=0;for(double x:us)mean+=x;mean/=us.size();
    std::cout<<sr<<","<<block<<","<<pitch<<","<<std::fixed<<std::setprecision(2)<<mean<<","<<pct(.50)<<","<<pct(.95)<<","<<pct(.99)<<","<<us.back()<<","<<deadline<<","<<(pct(.99)/deadline)<<"\n";
}
int main(){
    std::cout<<"sample_rate,block,pitch_st,mean_us,p50_us,p95_us,p99_us,max_us,deadline_us,p99_deadline_fraction\n";
    for(auto sr:{44100u,48000u,96000u})for(auto b:{32u,64u,128u,256u,512u})for(auto p:{-12.0f,0.0f,12.0f})run(sr,b,p);
}
