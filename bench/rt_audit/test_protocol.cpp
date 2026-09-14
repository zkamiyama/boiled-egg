#include "protocol.hpp"
#include <iostream>
#include <stdexcept>
using namespace boiled_egg::bench;
static void require(bool x) { if(!x) throw std::runtime_error("calibration failure"); }
// Deterministic observer injection: an expensive timer read, not expensive DSP.
struct fake_clock {
    ns now{}, wall_cost{};
    ns cpu() const {return now;}
    ns wall() {const auto stamp=now;now+=wall_cost;return stamp;}
};
int main() {try {
    unsigned checks=0;
    for(auto kind:{bracket::legacy,bracket::cpu,bracket::wall}) {
        fake_clock c{0,2000000};
        auto measured=measure(c,[&]{c.now+=50000;},kind);
        if(kind==bracket::legacy) require(measured.cpu==4050000 && measured.wall==2050000);
        if(kind==bracket::cpu) require(measured.cpu==50000 && measured.wall==-1);
        if(kind==bracket::wall) require(measured.wall==2050000 && measured.cpu==-1);
        ++checks;
    }
    for(auto rate:{44100U,48000U,96000U}) for(auto block:{31U,32U,64U,257U}) {
        ns sum=0;
        for(std::uint64_t i=0;i<3000;++i) {
            const auto a=release_at(7,i,block,rate), b=release_at(7,i+1,block,rate);
            sum+=b-a; require(b>a); ++checks;
        }
        require(sum==frame_time(3000ULL*block,rate)); ++checks;
    }
    auto p=classify(1000,2000,1500,2100);require(p.missed && p.wake_late==500 && p.response==1100 && p.slack==-100);++checks;
    require(!classify(1000,2000,1900,2000).missed);++checks;
    // A missed slot stays late. The next deadline is never moved to "now".
    require(classify(2000,3000,3900,4000).missed);++checks;
    require(warmup_calls(200,5248,96000,32)==1664);++checks;
    for(int i=0;i<4;++i) {
        bool threw=false;try {
            if(i==0)(void)release_at(0,0,32,0);
            if(i==1)(void)release_at(-1,0,32,48000);
            if(i==2)(void)release_at(std::numeric_limits<ns>::max(),1,32,48000);
            if(i==3)(void)classify(0,100,-1,5);
        }catch(const std::exception&){threw=true;}require(threw);++checks;
    }
    std::cout<<checks<<" timing/observer/release/warmup calibrations passed\n";
}catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}}
