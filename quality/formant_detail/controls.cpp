#include "driver.hpp"
#include "boiled_egg_research_execution.h"
#include <atomic>
#include <cstdlib>
#include <future>
#include <iostream>
#include <limits>
#include <new>
#include <cstring>
static thread_local bool watch=false;
static thread_local unsigned allocations=0;
void* operator new(std::size_t n){if(watch)++allocations;if(void* p=std::malloc(n?n:1))return p;throw std::bad_alloc();}
void* operator new[](std::size_t n){return ::operator new(n);}
void operator delete(void* p)noexcept{std::free(p);}void operator delete[](void* p)noexcept{std::free(p);}
void operator delete(void* p,std::size_t)noexcept{std::free(p);}void operator delete[](void* p,std::size_t)noexcept{std::free(p);}
using namespace detail_test;
static Audio reference(const Audio& x,unsigned rate,unsigned channels,unsigned block,float pitch,bool detail,bool events){
    auto c=boiledegg_research_pv_rt_default_config(rate,channels,block);c.fft_size=2048;c.analysis_hop=256;c.mode=1;c.formant_mode=2;c.initial_pitch_ratio=pitch;c.formant_cepstral_order=detail?80u:40u;
    auto f=boiledegg_research_default_features();f.timing_policy=f.rate_policy=1;
    auto e=boiledegg_research_default_execution();boiledegg_research_pv_rt_result status{};
    auto* h=boiledegg_research_pv_rt_create_exec(&c,&f,&e,&status);require(h&&!status,"direct creation");
    std::unique_ptr<boiledegg_research_pv_rt_handle,decltype(&boiledegg_research_pv_rt_destroy)> owner(h,boiledegg_research_pv_rt_destroy);
    Audio y{std::vector<float>(x[0].size()),std::vector<float>(x[0].size())};unsigned offset=0;
    auto drain=[&]{while(boiledegg_research_pv_rt_available(h)){require(offset<y[0].size(),"reference overrun");float* out[]={y[0].data()+offset,y[1].data()+offset};auto n=boiledegg_research_pv_rt_pull(h,out,unsigned(y[0].size())-offset);require(n>0,"reference progress");offset+=n;}};
    for(unsigned i=0;i<x[0].size();++i){if(events&&(i==1024||i==3072))require(boiledegg_research_pv_rt_set_formant_ratio(h,i==1024?1.15f:.9f)==0,"direct event");const float* in[]={x[0].data()+i,x[1].data()+i};require(!boiledegg_research_pv_rt_push(h,in,1),"direct push");drain();}
    require(!boiledegg_research_pv_rt_flush(h),"direct flush");drain();require(offset==x[0].size(),"reference length");return y;
}
static void validation(){
    auto c=boiledegg_default_config(48000,1);c.max_block_size=64;auto b=options(true,1,BOILEDEGG_IO_STREAMING);
    require(boiledegg_validate_backend_config(&c,&b)==BOILEDEGG_OK,"known detail option");
    auto reject=[&](boiledegg_config cc,boiledegg_backend_config bb){require(boiledegg_validate_backend_config(&cc,&bb)!=BOILEDEGG_OK,"bad combination accepted");boiledegg_result status{};auto h=boiledegg_create_backend(&cc,&bb,&status);require(!h&&status!=0,"fallback created");};
    for(auto rate:{44100u,88200u}){auto v=c;v.sample_rate=rate;reject(v,b);}
    for(auto q:{1u,2u,3u}){auto v=b;v.quality_mode=q;reject(c,v);}
    for(auto p:{0u,1u}){auto v=b;v.formant_policy=p;reject(c,v);}
    for(auto f:{2u,4u,6u,0x80000000u}){auto v=b;v.flags|=f;reject(c,v);}
    for(float t:{.5f,2.f}){auto v=b;v.initial_time_ratio=t;reject(c,v);}
    auto v=b;v.flags=8;reject(c,v);v=b;v.backend_id=0;reject(c,v);v=b;v.io_contract=0;reject(c,v);
    for(auto rate:{48000u,96000u})for(auto io:{1u,2u})for(auto ch:{1u,2u}){
        c=boiledegg_default_config(rate,ch);c.max_block_size=64;b=options(true,.5f,io);boiled_egg::engine h(c,b);
        boiledegg_backend_config read{};read.struct_size=sizeof(read);require(!boiledegg_get_backend_configuration(h.native_handle(),&read),"getter");require(!std::memcmp(&b,&read,sizeof(b)),"construction readback");
        auto state=h.backend_parameter_state();state.time_ratio=.5f;require(boiledegg_set_backend_parameter_state(h.native_handle(),&state)==BOILEDEGG_UNSUPPORTED_MODE,"state changes immutable time");require(h.time_ratio()==1,"state mutated");
        auto legacy=h.parameter_state();h.set_parameter_state(legacy);h.reset();read={};read.struct_size=sizeof(read);require(!boiledegg_get_backend_configuration(h.native_handle(),&read)&&read.flags==b.flags,"reset loses option");
    }
}
static void exact(bool rt,bool events){unsigned comparisons=0;
    for(unsigned rate:{48000u,96000u})for(unsigned channels:{1u,2u})for(float pitch:{.5f,1.f,2.f}){
        auto x=signal(6011,rate);auto c=boiledegg_default_config(rate,channels);c.max_block_size=257;
        boiled_egg::engine engine(c,options(true,pitch,rt?2u:1u));auto result=run(engine,x,rate,channels,32,rt,events);
        Audio padded=x;for(auto& v:padded)v.resize(result.pcm[0].size(),0);
        auto expected=reference(padded,rate,channels,257,pitch,true,events);unsigned lag=rt?result.info.realtime_latency_frames:0;
        for(unsigned ch=0;ch<channels;++ch){require(std::all_of(result.pcm[ch].begin(),result.pcm[ch].begin()+lag,[](float v){return v==0;}),"startup prefix");require(std::equal(result.pcm[ch].begin()+lag,result.pcm[ch].end(),expected[ch].begin()),"public/direct PCM differs");}
        engine.set_formant_ratio(1);engine.reset();auto again=run(engine,x,rate,channels,257,rt,events);require(again.pcm==result.pcm,"partition/reset PCM differs");
        auto plain=boiled_egg::engine(c,options(false,pitch,rt?2u:1u)).runtime_info();require(!std::memcmp(&plain,&result.info,sizeof(plain)),"latency/tail changed");++comparisons;
    }std::cout<<comparisons<<" direct/public/reset comparisons\n";
}
static void noalloc(){for(auto rate:{48000u,96000u})for(unsigned io:{1u,2u}){
    auto c=boiledegg_default_config(rate,2);c.max_block_size=64;boiled_egg::engine h(c,options(true,2,io));
    std::array<float,64> a{},b{};for(unsigned i=0;i<64;++i){a[i]=float(i)/256;b[i]=a[i]*.5f;}
    const float* in[]={a.data(),b.data()};float* out[]={a.data(),b.data()};allocations=0;watch=true;
    for(unsigned i=0;i<400;++i){if(io==2){require(h.process_realtime_nothrow(in,out,64)==0,"RT");}else{require(h.push(in,64)==64,"push");while(h.available())require(h.pull(out,64)>0,"pull");}}
    if(io==1){h.flush();while(h.available())require(h.pull(out,64)>0,"flush drain");}h.reset();watch=false;require(allocations==0,"audio new/new[] allocation");}}
int main(int argc,char** argv){try{require(argc==2,"test name required");std::string test=argv[1];
    if(test=="validation")validation();else if(test=="stream")exact(false,false);else if(test=="realtime")exact(true,false);else if(test=="events")exact(true,true);else if(test=="noalloc")noalloc();
    else if(test=="parallel"){auto x=signal(5000,48000);auto f=std::async(std::launch::async,[&]{return render(x,48000,2,64,.5f,true,false).pcm;});auto y=render(x,48000,2,64,.5f,true,false).pcm;require(y==f.get(),"independent instances");}
    else if(test=="nonfinite"){auto c=boiledegg_default_config(48000,1);c.max_block_size=64;boiled_egg::engine h(c,options(true,1,1));float x=std::numeric_limits<float>::quiet_NaN();const float* in[]={&x};uint32_t accepted=9;require(boiledegg_push(h.native_handle(),in,1,&accepted)==BOILEDEGG_INVALID_ARGUMENT&&accepted==0,"bad input accepted");}
    else throw std::runtime_error("unknown test");std::cout<<test<<" passed\n";return 0;
}catch(const std::exception& e){watch=false;std::cerr<<e.what()<<'\n';return 1;}}
