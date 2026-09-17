#include "pitch_processor.hpp"
#include <boiled_egg/boiled_egg.hpp>
#include <array>
#include <algorithm>
#include <cmath>
#include <iostream>
#include <stdexcept>
static void check(bool ok,const char* text){if(!ok)throw std::runtime_error(text);}
int main(){try{unsigned cases=0;for(unsigned rate:{44100u,48000u,88200u,96000u})for(unsigned block:{32u,64u,257u})for(float pitch:{-7.f,0.f,12.f})for(bool dynamic:{false,true}){
 namespace p=boiled_egg::plugin;p::Processor model;auto v=p::defaults();v[p::Pitch]=pitch;check(model.request(v)&&model.activate(rate,block),"activate");
 auto c=boiledegg_default_config(rate,2);c.max_block_size=block;boiled_egg::engine old(c);old.set_pitch_semitones(pitch);
 check(model.latency()==old.runtime_info().realtime_latency_frames,"latency changed");
 std::array<float,257> l{},r{},a{},b{},x{},y{};
 for(unsigned pos=0;pos<16013;pos+=block){unsigned n=std::min(block,16013-pos);for(unsigned i=0;i<n;++i){l[i]=.13f*std::sin(float(pos+i)*.0371f)+.07f*std::cos(float(pos+i)*.1231f);r[i]=-.375f*l[i];}
  std::array<p::Event,2> e{};unsigned count=0;if(dynamic)for(unsigned at:{777u,10001u})if(at>=pos&&at<pos+n)e[count++]={at-pos,p::Pitch,at==777u?-3.f:7.f};
  const float* input[]={l.data(),r.data()};float* out[]={a.data(),b.data()};check(model.process(input,out,n,{e.data(),count}),"new process");
  unsigned cursor=0;auto segment=[&](unsigned begin,unsigned end){if(begin==end)return;const float* in[]={l.data()+begin,r.data()+begin};float* dst[]={x.data()+begin,y.data()+begin};check(old.process_realtime_nothrow(in,dst,end-begin)==BOILEDEGG_OK,"old process");};
  for(unsigned i=0;i<count;++i){segment(cursor,e[i].offset);old.set_pitch_semitones(e[i].value);cursor=e[i].offset;}segment(cursor,n);
  check(std::equal(a.begin(),a.begin()+n,x.begin())&&std::equal(b.begin(),b.begin()+n,y.begin()),"old pitch-only waveform changed");
 }
 ++cases;
}std::cout<<cases<<" old C ABI pitch-only histories match current plugin processor exactly\n";}catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}}
