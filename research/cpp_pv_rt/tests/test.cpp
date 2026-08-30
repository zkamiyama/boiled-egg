#include "boiled_egg_pv_rt.h"
#include <algorithm>
#include <cmath>
#include <cstdint>
#include <iostream>
#include <vector>
namespace {
std::vector<float> run(float ratio,std::uint32_t block,std::uint32_t mode){constexpr std::uint32_t sr=48000,frames=24000;auto c=boiledegg_research_pv_rt_default_config(sr,1,block);c.initial_time_ratio=ratio;c.mode=mode;boiledegg_research_pv_rt_result r{};auto*h=boiledegg_research_pv_rt_create(&c,&r);if(!h)throw 1;std::vector<float> input(frames),ib(block),ob(block*8U),output;for(std::uint32_t i=0;i<frames;++i){const float t=static_cast<float>(i)/sr;input[i]=0.35F*std::sin(2.0F*3.14159265358979323846F*440.0F*t)+0.12F*std::sin(2.0F*3.14159265358979323846F*880.0F*t);if(i%6000U<3U)input[i]+=0.7F;}const float*ip[1]={ib.data()};float*op[1]={ob.data()};auto drain=[&](){while(boiledegg_research_pv_rt_available(h)){auto n=boiledegg_research_pv_rt_pull(h,op,static_cast<std::uint32_t>(ob.size()));output.insert(output.end(),ob.begin(),ob.begin()+n);}};for(std::uint32_t p=0;p<frames;p+=block){auto n=std::min(block,frames-p);std::copy_n(input.data()+p,n,ib.data());if(boiledegg_research_pv_rt_push(h,ip,n)!=BOILEDEGG_RESEARCH_PV_RT_OK)throw 2;drain();}if(boiledegg_research_pv_rt_flush(h)!=BOILEDEGG_RESEARCH_PV_RT_OK)throw 3;drain();boiledegg_research_pv_rt_destroy(h);if(output.size()!=static_cast<std::size_t>(std::llround(frames*ratio)))throw 4;for(float x:output)if(!std::isfinite(x))throw 5;return output;}
}
int main(){try{for(float r:{0.5F,0.75F,1.0F,1.25F,2.0F})for(std::uint32_t m:{0U,1U,2U})(void)run(r,127,m);auto a=run(1.37F,64,2U);auto b=run(1.37F,257,2U);if(a.size()!=b.size())return 10;double e=0.0,p=0.0;for(std::size_t i=0;i<a.size();++i){const double d=static_cast<double>(a[i])-b[i];e+=d*d;p+=static_cast<double>(a[i])*a[i];}if(std::sqrt(e/(p+1e-20))>1e-5)return 11;std::cout<<"pv rt tests passed\n";return 0;}catch(int code){std::cerr<<"failure "<<code<<'\n';return code;}}
