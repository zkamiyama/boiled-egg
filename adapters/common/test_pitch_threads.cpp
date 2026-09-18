#include "pitch_processor.hpp"
#include <atomic>
#include <array>
#include <cmath>
#include <cstdlib>
#include <iostream>
#include <thread>
namespace bp=boiled_egg::plugin;
static void check(bool x){if(!x)std::abort();}
int main(){
 std::array<bp::Processor,2> processors;const bool pv=bp::spectral_available();
 auto a=bp::defaults();a[bp::Backend]=pv?1.f:0.f;a[bp::Quality]=1;a[bp::Policy]=pv?1.f:0.f;
 a[bp::Pitch]=12;a[bp::Fine]=-100;auto b=a;b[bp::Pitch]=11;b[bp::Fine]=100;
 // Both snapshots are valid; their individual fields can form an invalid
 // intermediate PV13st snapshot. The audio thread retains a valid prior state
 // without spinning, blocking, clamping or processing a malformed combination.
 for(auto& p:processors)check(p.request(a)&&p.activate(96000,64));
 std::atomic<unsigned> ready{0};std::atomic<bool> start{false};
 auto audio=[&](unsigned instance){float l[64]{},r[64]{},ol[64]{},orr[64]{};const float* in[]={l,r};float* out[]={ol,orr};
  ++ready;while(!start.load())std::this_thread::yield();
  for(unsigned n=0;n<2500;++n){for(unsigned i=0;i<64;++i){l[i]=.1f*std::sin(float(n*64+i)*.0349f);r[i]=-.5f*l[i];}
   std::array<bp::Event,2> e{{{3,bp::Wet,n%2?.9f:.7f},{37,bp::Volume,n%2?-3.f:0.f}}};
   check(processors[instance].process(in,out,64,e));for(unsigned i=0;i<64;++i)check(std::isfinite(ol[i])&&std::isfinite(orr[i]));}
 };
 auto ui=[&]{++ready;while(!start.load())std::this_thread::yield();for(unsigned n=0;n<100000;++n)for(auto& p:processors){check(p.request(n%2?a:b));(void)p.targets.snapshot();(void)p.error();}};
 std::thread first(audio,0),second(audio,1),control(ui);while(ready.load()!=3)std::this_thread::yield();start.store(true);first.join();second.join();control.join();
 std::cout<<"Two plugin audio owners and concurrent coupled state publications: finite output, no spin or fault\n";
}
