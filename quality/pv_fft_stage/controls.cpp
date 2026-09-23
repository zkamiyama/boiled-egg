// Compare actual immutable old and new implementations, including every pause.
#include "fft.hpp"
#undef BOILED_EGG_RESEARCH_PV_RT_FFT_HPP
#define boiled_egg fft_reference
#include "reference/fft.hpp"
#undef boiled_egg
#include <algorithm>
#include <atomic>
#include <bit>
#include <cmath>
#include <cstdint>
#include <cstdlib>
#include <cstring>
#include <future>
#include <iostream>
#include <new>
#include <stdexcept>
#include <string>
#include <vector>

static std::atomic<std::size_t> allocations{0};
void* operator new(std::size_t n) {
    allocations.fetch_add(1,std::memory_order_relaxed);
    if(void* p=std::malloc(n?n:1))return p;
    throw std::bad_alloc();
}
void operator delete(void* p) noexcept {std::free(p);}
void operator delete(void* p,std::size_t) noexcept {std::free(p);}
void* operator new[](std::size_t n){return ::operator new(n);}
void operator delete[](void* p) noexcept {std::free(p);}
void operator delete[](void* p,std::size_t) noexcept {std::free(p);}
using Plan=boiled_egg::research::detail::fft_plan;
using Old=fft_reference::research::detail::fft_plan;
using C=std::complex<float>;
void need(bool ok,const char* message){if(!ok)throw std::runtime_error(message);}
bool same(const std::vector<C>& a,const std::vector<C>& b){return a.size()==b.size()&&!std::memcmp(a.data(),b.data(),a.size()*sizeof(C));}
void cursors(const Plan::cursor& a,const Old::cursor& b){
    need(a.position==b.position&&a.length==b.length&&a.base==b.base&&a.column==b.column&&
         a.stage==b.stage&&a.inverse==b.inverse&&a.simd==b.simd,"cursor differs");
}
std::vector<C> fixture(std::size_t n,unsigned family){
    std::vector<C> x(n);std::uint32_t state=0x6743ab29u;
    for(std::size_t j=0;j<n;++j){
        auto value=[&](){state=state*1664525u+1013904223u;return static_cast<float>(static_cast<int>(state>>8)-8388608)/8388608.f;};
        if(family==0){float a=value(),b=value();x[j]={a,b};}
        else if(family==1)x[j]={j==n/3?0.5f:0.f,0.f};
        else if(family==2)x[j]={std::bit_cast<float>((j&1)?0x80000000u:0u),std::bit_cast<float>((j&2)?0x80000000u:0u)};
        else x[j]={0.f,0.f};
    }
    return x;
}
std::size_t cases=0,pauses=0;
void run_case(std::size_t n,unsigned family,bool inverse,bool simd,const std::vector<std::size_t>& budgets){
    Plan plan(n);Old old(n);auto x=fixture(n,family),y=x;
    Plan::cursor a;Old::cursor b;plan.start(a,x.data(),inverse,simd);old.start(b,y.data(),inverse,simd);
    std::size_t steps=0;
    do{
        auto budget=budgets[steps%budgets.size()];
        need(plan.advance(a,budget)==old.advance(b,budget),"completion differs");
        cursors(a,b);need(same(x,y),"paused FFT output differs");++steps;++pauses;
        need(steps<2000000,"no progress");
    }while(a.stage!=3);
    need(!plan.advance(a,999)&&!old.advance(b,999),"finished cursor restarted");
    cursors(a,b);need(same(x,y),"finished output differs");++cases;
}
int main(int argc,char** argv){try{
    need(argc==2,"test name required");const std::string name=argv[1];
    need(Plan::simd_available()==Old::simd_available(),"SIMD build mismatch");
    if(name=="first_stage"){
        for(std::size_t n=2;n<=16384;n*=2)for(bool inv:{false,true})for(bool simd:{false,true})
        for(auto budget:{std::size_t(0),1ul,2ul,3ul,127ul,128ul,129ul,4096ul,n/2,n/2+1}){
            Plan plan(n);Old old(n);auto x=fixture(n,0),y=x;Plan::cursor a;Old::cursor b;
            plan.start(a,x.data(),inv,simd);old.start(b,y.data(),inv,simd);
            plan.advance(a,n);old.advance(b,n);need(a.stage==1&&a.length==2,"bad initial phase");
            need(plan.advance(a,budget)==old.advance(b,budget),"first stage completion differs");
            cursors(a,b);need(same(x,y),"first stage differs");++cases;
        }
    }else if(name=="small_prefix"||name=="large_prefix"){
        const bool small=name=="small_prefix";
        std::vector<std::vector<std::size_t>> budgets=small?
            std::vector<std::vector<std::size_t>>{{1},{2},{3},{127},{128},{129},{4096},{0,1,3,2,128,0,129}}:
            std::vector<std::vector<std::size_t>>{{127},{128},{129},{4096},{0,1,3,128,4096}};
        for(std::size_t n=small?2:512;n<=(small?256:16384);n*=2)
        for(unsigned f=0;f<2;++f)for(bool inv:{false,true})for(bool simd:{false,true})for(const auto& b:budgets)
            run_case(n,f,inv,simd,b);
    }else if(name=="signed_zero"){
        for(std::size_t n=2;n<=4096;n*=2)for(unsigned f:{2u,3u})for(bool inv:{false,true})for(bool simd:{false,true})
            run_case(n,f,inv,simd,{0,1,2,127,128,129});
    }else if(name=="immediate"){
        for(std::size_t n=2;n<=16384;n*=2)for(unsigned f=0;f<4;++f){
            Plan plan(n);Old old(n);auto x=fixture(n,f),y=x;
            plan.forward(x.data());old.forward(y.data());need(same(x,y),"immediate forward differs");
            plan.inverse(x.data());old.inverse(y.data());need(same(x,y),"immediate inverse differs");++cases;
        }
    }else if(name=="zero_budget"){
        for(bool inv:{false,true})for(bool simd:{false,true})run_case(1024,0,inv,simd,{0,128,0,0,3});
        auto a=fixture(16,2),b=a;b[0]={1,0};need(!same(a,b),"bit comparator accepts corruption");
    }else if(name=="noalloc"){
        Plan plan(4096);auto x=fixture(4096,0);Plan::cursor c;
        for(bool inv:{false,true})for(bool simd:{false,true}){
            auto before=allocations.load();plan.start(c,x.data(),inv,simd);while(plan.advance(c,128)){}
            need(allocations.load()==before,"FFT allocated during advance");++cases;
        }
    }else if(name=="threads"){
        Plan shared(2048);Old old(2048);auto input=fixture(2048,0),expected=input;Old::cursor c;
        old.start(c,expected.data(),true,true);while(old.advance(c,127)){}
        auto call=[&](){auto x=input;Plan::cursor s;shared.start(s,x.data(),true,true);while(shared.advance(s,127)){}return x;};
        auto future=std::async(std::launch::async,call);auto x=call(),y=future.get();
        need(same(x,y)&&same(x,expected),"parallel shared-plan mismatch");++cases;
    }else throw std::runtime_error("unknown test");
    std::cout<<name<<" cases="<<cases<<" pauses="<<pauses<<" SIMD="<<Plan::simd_available()<<" passed\n";return 0;
}catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}}
