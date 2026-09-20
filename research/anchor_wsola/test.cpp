#include "anchor.h"
#include <algorithm>
#include <cmath>
#include <future>
#include <iostream>
#include <limits>
#include <stdexcept>
#include <string>
#include <vector>
namespace {
void check(bool b) {if(!b)throw std::runtime_error("control failed");}
struct Result { std::vector<float> pcm;std::vector<be_anchor_grain> trace;be_anchor_info info{}; };
std::vector<float> input(unsigned rate) {
 std::vector<float> x(rate/2);
 for(size_t i=0;i<x.size();++i)x[i]=static_cast<float>(.2*std::sin(2*3.141592653589793*61*static_cast<double>(i)/rate));
 return x;
}
Result run(std::vector<float> x,unsigned rate,double p,unsigned mode,std::vector<int64_t> marks={}) {
 be_anchor_config c{sizeof(c),rate,1,mode,p,16777216};Result r;r.pcm.resize(x.size());r.trace.resize(2048);
 check(be_anchor_render(x.data(),x.size(),marks.data(),static_cast<uint32_t>(marks.size()),&c,r.pcm.data(),r.trace.data(),r.trace.size(),&r.info)==0);
 r.trace.resize(r.info.grains);return r;
}
}
int main(int argc,char**argv) {
 try {
 check(argc==2);const std::string which=argv[1];
 if(which=="identity") {for(unsigned rate:{48000u,96000u})for(unsigned mode:{0u,1u,2u}) {auto x=input(rate);auto r=run(x,rate,1,mode);check(x==r.pcm && r.info.frames==x.size() && r.info.grains==0);}}
 else if(which=="deterministic") {auto x=input(48000);for(double p:{.5,2.}) {auto a=run(x,48000,p,2,{12000});auto b=run(x,48000,p,2,{12000});check(a.pcm==b.pcm && a.trace.size()==b.trace.size());}}
 else if(which=="empty_marks") {auto x=input(48000);auto a=run(x,48000,2,0);for(unsigned mode:{1u,2u})check(a.pcm==run(x,48000,2,mode).pcm);}
 else if(which=="ownership") {
  for(unsigned rate:{48000u,96000u})for(double p:{.5,2.}) {
   const int64_t mark=rate/4;auto r=run(input(rate),rate,p,2,{mark});bool found=false;uint64_t masked=0;
   for(const auto& g:r.trace) {masked+=g.masked_samples;if(g.anchor_index==0){found=true;check(g.source_center-g.output_center==mark-static_cast<int64_t>(std::llround(mark*p)));}}
   check(found && masked==r.info.masked_samples && r.info.min_weight>0 && r.info.workspace_bytes<16777216);
  }
 }
 else if(which=="invalid") {
  auto x=input(48000);std::vector<float> out(x.size(),-9);std::vector<be_anchor_grain> trace(2048);be_anchor_info info{};
  be_anchor_config c{sizeof(c),48000,1,2,2,16777216};std::vector<int64_t> m;
  auto bad=[&](){check(be_anchor_render(x.data(),x.size(),m.data(),static_cast<uint32_t>(m.size()),&c,out.data(),trace.data(),trace.size(),&info)!=0);check(std::all_of(out.begin(),out.end(),[](float v){return v==-9;}));};
  for(auto marks:std::vector<std::vector<int64_t>>{{0},{24000},{12000,12000},{12000,10000},{12000,12001}}){m=marks;bad();}
  m.clear();c.pitch_ratio=std::numeric_limits<double>::quiet_NaN();bad();c.pitch_ratio=3;bad();c.pitch_ratio=.5;
  c.channels=2;bad();c.channels=1;c.sample_rate=44100;bad();c.sample_rate=48000;c.memory_limit_bytes=1;bad();c.memory_limit_bytes=16777216;
  x[0]=std::numeric_limits<float>::infinity();bad();x[0]=.2f;c.mode=0;m={12000};bad();m.clear();std::fill(x.begin(),x.end(),0);bad();
 }
 else if(which=="threads") {auto x=input(48000);auto a=std::async(std::launch::async,[&]{return run(x,48000,2,2,{12000});});auto b=run(x,48000,2,2,{12000});check(a.get().pcm==b.pcm);}
 else throw std::runtime_error("unknown test");
 std::cout<<which<<" passed\n";return 0;
 }catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}
}
