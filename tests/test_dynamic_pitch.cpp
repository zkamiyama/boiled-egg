#include <boiled_egg/boiled_egg.hpp>
#include "../src/experimental/pv/pitch_timeline.hpp"
#include <algorithm>
#include <array>
#include <cmath>
#include <iostream>
#include <limits>
#include <stdexcept>
#include <vector>
using Audio=std::array<std::vector<float>,2>;
struct Event {unsigned at,id;float value;};
static void check(bool b,const char* s){if(!b)throw std::runtime_error(s);}
static Audio source(unsigned n,unsigned rate){Audio x{std::vector<float>(n),std::vector<float>(n)};unsigned random=13;
 for(unsigned i=0;i<n;++i){random=random*1664525u+1013904223u;const double t=double(i)/rate;
  x[0][i]=float(.2*std::sin(6.283185307179586*211*t)+.06*std::sin(6.283185307179586*731*t)+.02*(double(random>>8)/16777216.-.5));x[1][i]=-.5f*x[0][i];}return x;}
static boiledegg_backend_config config(unsigned quality,unsigned policy,unsigned io,float time=1,float pitch=1){
 auto b=boiledegg_default_backend_config();b.backend_id=1;b.flags=BOILEDEGG_BACKEND_ALLOW_EXPERIMENTAL|BOILEDEGG_BACKEND_CONTINUOUS_PITCH;
 b.io_contract=io;b.quality_mode=quality;b.formant_policy=policy;b.initial_time_ratio=time;b.initial_pitch_ratio=pitch;return b;}
static void target(boiled_egg::engine& h,const Event& e){
 if(e.id==BOILEDEGG_PARAMETER_PITCH_RATIO)h.set_pitch_ratio(e.value);else h.set_formant_ratio(e.value);}
static Audio streaming(boiled_egg::engine& h,const Audio& x,unsigned block,const std::vector<Event>& events){
 Audio y;float a[8192],b[8192];float* out[]={a,b};std::size_t event=0;
 auto drain=[&]{while(h.available()){auto n=h.pull(out,8192);check(n>0,"stream drain progress");y[0].insert(y[0].end(),a,a+n);y[1].insert(y[1].end(),b,b+n);}};
 for(unsigned pos=0;pos<x[0].size();){while(event<events.size()&&events[event].at==pos)target(h,events[event++]);
  unsigned n=std::min<unsigned>(block,unsigned(x[0].size())-pos);if(event<events.size())n=std::min(n,events[event].at-pos);
  const float* in[]={x[0].data()+pos,x[1].data()+pos};auto accepted=h.push(in,n);check(accepted>0,"accept progress");pos+=accepted;drain();}
 h.flush();drain();check(h.drained(),"EOS");return y;}
static Audio realtime(boiled_egg::engine& h,Audio x,unsigned block,const std::vector<Event>& events){
 const auto delay=h.runtime_info().realtime_latency_frames;
 for(unsigned pos=0;pos<x[0].size();pos+=block){unsigned n=std::min<unsigned>(block,unsigned(x[0].size())-pos);
  std::array<boiled_egg::parameter_event,256> ev{};unsigned used=0;
  for(auto e:events)if(e.at>=pos&&e.at<pos+n){check(used<ev.size(),"test event size");ev[used++]={sizeof(boiledegg_parameter_event),e.at-pos,e.id,e.value};}
  const float* in[]={x[0].data()+pos,x[1].data()+pos};float* out[]={x[0].data()+pos,x[1].data()+pos};
  auto status=h.process_realtime_nothrow(in,out,n,std::span(ev.data(),used));check(status==BOILEDEGG_OK,"dynamic realtime underrun/error");
  check(h.runtime_info().realtime_latency_frames==delay,"delay changed under automation");}
 return x;}
int main(){try{
 // Independent cumulative reference for an arbitrary stream of targets. No DSP.
 using Timeline=boiled_egg::research::detail::pitch_timeline;Timeline tl;tl.prepare(32768,48000,1,1,1);
 long double current=1,target_pitch=1,step=0,sum=0;unsigned remaining=0;double previous=-1;
 for(unsigned i=0;i<25000;++i){if(i==107||i==899||i==2201||i==9100){target_pitch=i%2?.5:2;remaining=480;step=(target_pitch-current)/480;tl.target(float(target_pitch));}
  if(remaining){current=remaining==1?target_pitch:current+step;--remaining;}tl.append(i%2?.75f:1.25f);
  check(tl.at(i).position>previous,"monotonic input map");previous=tl.at(i).position;
  check(std::abs(tl.at(i).position-double(sum))<1e-8,"integral differs from independent long-double reference");
  check(std::abs(double(tl.at(i).pitch)-double(current))<1e-7,"effective ratio history");sum+=current;
  check(std::abs(tl.position(double(i)+.5)-(tl.at(i).position+tl.at(i+1).position)/2)<1e-10,"fractional coordinate interpolation");}
 unsigned comparisons=0;
 for(unsigned rate:{44100u,48000u,88200u,96000u})for(unsigned quality:{0u,1u})for(unsigned policy:{0u,1u,2u}){
  auto b=config(quality,policy,BOILEDEGG_IO_REALTIME);auto c=boiledegg_default_config(rate,2);c.max_block_size=257;
  boiled_egg::engine h(c,b);const auto L=h.runtime_info().realtime_latency_frames;
  std::vector<Event> events={{777,BOILEDEGG_PARAMETER_PITCH_RATIO,.5f},{2131,BOILEDEGG_PARAMETER_PITCH_RATIO,2.f},
   {4537,BOILEDEGG_PARAMETER_PITCH_RATIO,.7491535f},{7103,BOILEDEGG_PARAMETER_PITCH_RATIO,1.f},{10017,BOILEDEGG_PARAMETER_PITCH_RATIO,1.4983071f}};
  if(policy){events.push_back({1913,BOILEDEGG_PARAMETER_FORMANT_RATIO,.75f});events.push_back({4679,BOILEDEGG_PARAMETER_FORMANT_RATIO,1.5f});
   events.push_back({12011,BOILEDEGG_PARAMETER_FORMANT_RATIO,1.f});}
  std::stable_sort(events.begin(),events.end(),[](auto a,auto d){return a.at<d.at;});
  auto x=source(35003,rate);for(auto& ch:x)ch.resize(ch.size()+L,0.f);
  auto y=realtime(h,x,32,events);h.set_pitch_ratio(1);h.set_formant_ratio(1);h.reset();
  check(y==realtime(h,x,257,events),"input block partition/reset changed audio");
  b.io_contract=BOILEDEGG_IO_STREAMING;boiled_egg::engine r(c,b);auto oracle=streaming(r,x,31,events);
  for(unsigned ch=0;ch<2;++ch){check(std::all_of(y[ch].begin(),y[ch].begin()+L,[](float v){return v==0;}),"prefix zeros");
   check(std::equal(y[ch].begin()+L,y[ch].end(),oracle[ch].begin()),"fixed-delay output differs from immediate timeline");}
  double err=0,power=0;for(std::size_t i=0;i<y[0].size();++i){check(std::isfinite(y[0][i])&&std::isfinite(y[1][i]),"finite");
   const double d=y[1][i]+.5*y[0][i];err+=d*d;power+=double(y[0][i])*y[0][i];}check(err<1e-10*(power+1e-30),"linked stereo relation");
  ++comparisons;
 }
 // Time is fixed, but output-clock mapping also works with constant nonunit T.
 for(float time:{.5f,.75f,1.25f,2.f})for(unsigned n:{0u,1u,31u,11003u}){
  auto c=boiledegg_default_config(48000,2);c.max_block_size=257;auto b=config(1,1,1,time,.5f);
  std::vector<Event> events;if(n>800)events={{799,BOILEDEGG_PARAMETER_PITCH_RATIO,std::min(1.5f,2.f/time)}};
  auto x=source(n,48000);boiled_egg::engine a(c,b),d(c,b);auto y=streaming(a,x,31,events);
  check(y==streaming(d,x,257,events),"streaming automation partition");check(y[0].size()==std::llround(n*double(time)),"exact stretched duration");++comparisons;
 }
 // Invalid event batch must not advance DSP or mutate any target/output.
 auto c=boiledegg_default_config(48000,2);c.max_block_size=64;auto b=config(1,1,2);boiled_egg::engine h(c,b);
 float a[64]{},d[64]{};const float* in[]={a,d};float* out[]={a,d};
 std::array<boiled_egg::parameter_event,2> ev{boiled_egg::parameter_event::pitch_ratio(0,.5f),boiled_egg::parameter_event::pitch_ratio(33,2.1f)};
 check(h.process_realtime_nothrow(in,out,64,ev)==BOILEDEGG_UNSUPPORTED_MODE,"reject unsupported pitch atomically");check(h.pitch_ratio()==1.f,"bad batch mutated target");
 auto state=h.backend_parameter_state();state.pitch_ratio=.5;state.formant_ratio=.75;h.set_backend_parameter_state(state);check(h.pitch_ratio()==.5f,"state restores dynamic pitch");
 check(boiledegg_set_time_ratio(h.native_handle(),1.5f)==BOILEDEGG_UNSUPPORTED_MODE,"dynamic time not advertised");
 std::cout<<comparisons<<" dynamic delay/partition/duration cases and 25000 integral checks passed\n";
}catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}}
