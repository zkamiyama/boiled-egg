#include "transport.hpp"
#include <algorithm>
#include <array>
#include <atomic>
#include <cmath>
#include <cstdlib>
#include <cstring>
#include <iostream>
#include <new>
#include <stdexcept>
#include <vector>
static std::atomic<bool> tracking{false};static std::atomic<unsigned> allocations{0};
void* operator new(std::size_t n){if(tracking)++allocations;if(void* p=std::malloc(n?n:1))return p;throw std::bad_alloc();}
void* operator new[](std::size_t n){return ::operator new(n);}
void operator delete(void* p) noexcept{std::free(p);}void operator delete[](void* p) noexcept{std::free(p);}
void operator delete(void* p,std::size_t) noexcept{std::free(p);}void operator delete[](void* p,std::size_t) noexcept{std::free(p);}
static void check(bool v,const char* why){if(!v)throw std::runtime_error(why);}
struct Handle{
    be_transport* h{};
    Handle(be_transport_config c,const std::vector<float>& x){int r;h=be_transport_create(&c,x.data(),x.size()/c.channels,&r);check(h&&r==0,"create");}
    ~Handle(){be_transport_destroy(h);}
    Handle(const Handle&)=delete;
};
static be_transport_info info(be_transport* h){be_transport_info s{};s.struct_size=sizeof(s);check(!be_transport_get_info(h,&s),"info");return s;}
static std::vector<float> tone(unsigned rate,unsigned frames){std::vector<float>x(frames*2);for(unsigned i=0;i<frames;++i){x[2*i]=float(.2*std::cos(2*3.141592653589793*223*i/rate));x[2*i+1]=-.375F*x[2*i];}return x;}
static std::vector<float> replay(be_transport* h,unsigned total,unsigned block){
    std::vector<float> y(total*2);std::array<be_transport_event,5> plan{{{3073,BE_T_SPEED,19,0,.1},{12345,BE_T_SPEED,0,0,0},{16301,BE_T_PITCH_SEMITONES,791,0,7},{28001,BE_T_SPEED,481,0,1.2},{31001,BE_T_SPEED,0,0,4}}};
    unsigned consumed=0;
    for(unsigned pos=0;pos<total;){unsigned n=std::min(block,total-pos),count=0;std::array<be_transport_event,5> e{};
        while(consumed<plan.size() && plan[consumed].offset<pos+n){e[count]=plan[consumed++];e[count++].offset-=pos;}
        tracking=true;int r=be_transport_render(h,y.data()+2*pos,n,e.data(),count);tracking=false;check(!r,"render");pos+=n;
    }return y;
}
int main(){try{
  unsigned checks=0;
  for(unsigned mode=0;mode<6;++mode)for(unsigned rate:{48000U,96000U}){
    auto c=be_transport_default_config(rate,2);c.mode=mode;c.max_block_frames=257;auto x=tone(rate,rate);
    Handle a(c,x),b(c,x);auto y=replay(a.h,40001,32);auto z=replay(b.h,40001,257);
    check(y==z,"block history mismatch");check(info(a.h).source_position==info(b.h).source_position,"source clock mismatch");
    double energy=0,error=0;for(unsigned i=0;i<40001;++i){check(std::isfinite(y[2*i])&&std::isfinite(y[2*i+1]),"finite");energy+=double(y[2*i])*y[2*i];double d=y[2*i+1]+.375*y[2*i];error+=d*d;}
    check(energy>1e-6 && std::sqrt(error/energy)<1e-5,"linked stereo");
    check(!be_transport_seek(a.h,12000),"seek");be_transport_event freeze{0,BE_T_SPEED,0,0,0};
    check(!be_transport_render(a.h,nullptr,0,&freeze,1),"zero-frame control");std::array<float,514> buffer{};auto original=info(a.h);
    tracking=true;for(unsigned i=0;i<200;++i)be_transport_render(a.h,buffer.data(),257,nullptr,0);tracking=false;
    auto s=info(a.h);check(s.source_position==12000 && s.output_frames==51400,"freeze source/output clocks");check(s.owned_bytes==original.owned_bytes,"hold memory grew");
    if(mode<3)check(s.analysis_frames==2,"stationary spectrum reanalyzed");
    be_transport_event change{0,BE_T_PITCH_SEMITONES,1200,0,-5};check(!be_transport_render(a.h,buffer.data(),257,&change,1),"held pitch change");
    for(unsigned i=0;i<4;++i)check(!be_transport_render(a.h,buffer.data(),257,nullptr,0),"ramp");
    check(info(a.h).pitch_semitones==-5 && info(a.h).source_position==12000,"output-time ramp stopped on freeze");
    auto prior=info(a.h);buffer.fill(77);be_transport_event invalid{0,BE_T_SPEED,0,0,-1};
    check(be_transport_render(a.h,buffer.data(),257,&invalid,1)==BE_T_INVALID,"invalid speed accepted");check(info(a.h).output_frames==prior.output_frames && std::all_of(buffer.begin(),buffer.end(),[](float v){return v==77;}),"invalid batch mutation");
    be_transport_event eof{257,BE_T_SPEED,0,0,1};check(!be_transport_render(a.h,buffer.data(),257,&eof,1),"endpoint event");check(info(a.h).source_position==12000 && info(a.h).speed==1,"endpoint semantics");
    checks+=8;
  }
  // The source is copied and resampling is included in source clock arithmetic.
  auto c=be_transport_default_config(44100,2);c.output_rate=48000;auto x=tone(44100,44100);Handle a(c,x);std::fill(x.begin(),x.end(),0);
  std::vector<float> out(4096*2);check(!be_transport_render(a.h,out.data(),4096,nullptr,0),"resampling render");
  check(std::abs(info(a.h).source_position-4096.*44100/48000)<1e-6,"unequal-rate clock");
  check(*std::max_element(out.begin(),out.end())>.01,"source not copied");
  c.mode=BE_T_WSOLA;c.formant_policy=1;int r;check(!be_transport_create(&c,x.data(),44100,&r)&&r==BE_T_UNSUPPORTED,"formant fallback");
  c=be_transport_default_config(48000,2);Handle empty(c,{});check(!be_transport_render(empty.h,out.data(),4096,nullptr,0),"empty render");check(std::all_of(out.begin(),out.end(),[](float v){return v==0;}),"empty nonzero");
  {auto cfg=be_transport_default_config(48000,2);auto pcm=tone(48000,8192);
    boiled_egg::file_transport first(cfg,pcm);auto moved=std::move(first);std::array<float,128> y{};
    moved.render(y);check(first.render_nothrow(y)==BE_T_INVALID,"moved-from wrapper");check(moved.info().output_frames==64,"RAII history");}
  check(allocations==0,"processing allocation");std::cout<<checks<<" native trajectory/freeze assertions; empty, ownership, rate conversion; processing allocations="<<allocations<<'\n';
  return 0;
}catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}}
