// Compile with previous headers; loading a new library must not require rebuild.
#include <boiled_egg/boiled_egg.hpp>
#include <array>
#include <bit>
#include <cmath>
#include <cstdint>
#include <iostream>
#include <stdexcept>
static void require(bool v,const char* why){if(!v)throw std::runtime_error(why);}
int main(){try{
    std::cout<<"rate,quality,frames,audio_hash,latency,capabilities\n";
    for(unsigned rate:{44100u,48000u,88200u,96000u})for(unsigned q:{0u,1u,2u}) {
        auto c=boiledegg_default_config(rate,2);c.max_block_size=128;
        boiled_egg::engine first(c,boiled_egg::profile(static_cast<boiledegg_quality_mode>(q)));
        auto* saved=first.native_handle();boiled_egg::engine moved(std::move(first));
        require(!first.native_handle() && moved.native_handle()==saved,"move constructor");
        boiled_egg::engine e(c);e=std::move(moved);require(!moved.native_handle(),"move assignment");
        e.set_pitch_semitones(-7);auto state=e.parameter_state();e.set_pitch_ratio(1);e.set_parameter_state(state);e.reset();
        auto info=e.runtime_info();std::array<float,128> left{},right{},ol{},orr{};
        const float* in[]={left.data(),right.data()};float* out[]={ol.data(),orr.data()};
        std::uint64_t hash=1469598103934665603ULL;
        for(unsigned k=0;k<128;++k){
            for(unsigned i=0;i<128;++i){left[i]=.1f*std::sin(.071f*float(128*k+i));right[i]=-.375f*left[i];}
            auto event=boiled_egg::parameter_event::pitch_semitones(31,7.f);
            e.process_realtime(in,out,128,k==31?std::span(&event,1):std::span<boiled_egg::parameter_event>());
            for(unsigned i=0;i<128;++i)for(float v:{ol[i],orr[i]}) {
                require(std::isfinite(v),"nonfinite");hash=(hash^std::bit_cast<std::uint32_t>(v))*1099511628211ULL;
            }
        }
        bool caught=false;try{e.set_pitch_ratio(-1);}catch(const boiled_egg::error& x){caught=x.result()==BOILEDEGG_INVALID_ARGUMENT;}
        require(caught,"legacy RAII exception");
        std::cout<<rate<<','<<q<<",16384,"<<hash<<','<<info.realtime_latency_frames<<','<<info.capabilities<<'\n';
    }return 0;
}catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}}
