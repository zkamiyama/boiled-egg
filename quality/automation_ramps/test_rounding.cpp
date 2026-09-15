#include <boiled_egg/boiled_egg.hpp>
#include <cmath>
#include <cstdio>
#include <stdexcept>
int main(){try {
    unsigned cases=0;
    for(unsigned duration:{100U,1000U,4800U,9600U,44100U})for(float target:{.5f,.75f,1.5f,2.f}) {
        auto c=boiledegg_default_config(48000,1);c.max_block_size=32;
        auto b=boiledegg_default_backend_config();b.backend_id=1;b.quality_mode=1;b.io_contract=1;b.flags=7;
        boiled_egg::engine h(c,b);float x[32]{},y[1024]{};const float* in[]={x};float* out[]={y};
        boiledegg_ramp_event e{sizeof(e),0,BOILEDEGG_PARAMETER_TIME_RATIO,duration,0,target,{0,0}};
        h.push_ramps(nullptr,0,std::span(&e,1));unsigned pos=0,total=0;
        while(pos<duration) {
            auto n=std::min(32u,duration-pos);pos+=h.push_ramps(in,n);
            while(h.available())total+=h.pull(out,1024);
        }
        // Closed right-endpoint linear sum; all endpoints are exact binary values.
        const double expected=double(duration)+(double(target)-1.)*double(duration+1)/2.;
        const double measured=h.automation_info().output_position;
        h.flush();while(h.available())total+=h.pull(out,1024);
        if(total!=static_cast<unsigned>(std::llround(expected))) {
            std::fprintf(stderr,"N=%u target=%g expected_position=%.17g measured=%.17g output=%u expected_frames=%lld\n",duration,target,expected,measured,total,std::llround(expected));return 1;
        }
        if(std::abs(measured-expected)>1e-8)throw std::runtime_error("linear integral drift");++cases;
    }
    std::printf("%u half-sample/linear duration boundaries passed\n",cases);
}catch(const std::exception& e){std::fprintf(stderr,"%s\n",e.what());return 2;}}
