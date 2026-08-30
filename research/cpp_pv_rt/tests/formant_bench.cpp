#include "boiled_egg_pv_rt.h"
#include <algorithm>
#include <chrono>
#include <cmath>
#include <cstdint>
#include <iomanip>
#include <iostream>
#include <numeric>
#include <vector>

static double quantile(std::vector<double> v,double q){const auto i=static_cast<std::size_t>(std::floor(q*(v.size()-1)));std::nth_element(v.begin(),v.begin()+static_cast<std::ptrdiff_t>(i),v.end());return v[i];}
static const char* fmode(std::uint32_t m){return m==0?"off":m==1?"harmonic":"monophonic";}
int main(){
 std::cout<<"sample_rate,block,pitch_ratio,formant,mean_us,p95_us,p99_us,max_us,deadline_us,p99_deadline_ratio\n";
 for(auto sr:{48000U,96000U})for(auto block:{32U,64U,128U,256U})for(float pitch:{0.6674199F,1.4983071F})for(auto fm:{0U,1U,2U}){
  auto c=boiledegg_research_pv_rt_default_config(sr,1,block);c.mode=BOILEDEGG_RESEARCH_PV_RT_PHASE_LOCKED;c.initial_pitch_ratio=pitch;c.formant_mode=fm;
  boiledegg_research_pv_rt_result r{};auto*h=boiledegg_research_pv_rt_create(&c,&r);if(!h)return 2;
  std::vector<float> inbuf(block),outbuf(block*8U);const float*in[1]={inbuf.data()};float*out[1]={outbuf.data()};std::vector<double> t;t.reserve(1200);std::uint64_t pos=0;
  for(std::uint32_t it=0;it<1400;++it){for(std::uint32_t i=0;i<block;++i){float x=static_cast<float>(pos+i)/sr;inbuf[i]=0.25F*std::sin(2*3.14159265358979323846F*120*x)+0.18F*std::sin(2*3.14159265358979323846F*720*x)+0.1F*std::sin(2*3.14159265358979323846F*1320*x);}auto a=std::chrono::steady_clock::now();r=boiledegg_research_pv_rt_push(h,in,block);while(boiledegg_research_pv_rt_available(h))boiledegg_research_pv_rt_pull(h,out,static_cast<std::uint32_t>(outbuf.size()));auto b=std::chrono::steady_clock::now();if(r!=BOILEDEGG_RESEARCH_PV_RT_OK)return 3;if(it>=200)t.push_back(std::chrono::duration<double,std::micro>(b-a).count());pos+=block;}
  double mean=std::accumulate(t.begin(),t.end(),0.0)/t.size(),p95=quantile(t,.95),p99=quantile(t,.99),mx=*std::max_element(t.begin(),t.end()),deadline=1e6*block/static_cast<double>(sr);
  std::cout<<sr<<','<<block<<','<<pitch<<','<<fmode(fm)<<','<<std::fixed<<std::setprecision(3)<<mean<<','<<p95<<','<<p99<<','<<mx<<','<<deadline<<','<<p99/deadline<<'\n';boiledegg_research_pv_rt_destroy(h);
 }
}
