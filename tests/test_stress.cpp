#include <boiled_egg/boiled_egg.hpp>
#include <cmath>
#include <cstdint>
#include <random>
#include <vector>

int main(){
    auto cfg=boiledegg_default_config(48000,2); cfg.max_block_size=257;
    boiled_egg::engine e(cfg);
    std::minstd_rand rng(42);
    std::uniform_real_distribution<float> sig(-0.8f,0.8f), tr(0.5f,2.0f), ps(-12.0f,12.0f);
    std::vector<float> l(257),r(257),ol(4096),orr(4096); const float* ip[2]{l.data(),r.data()}; float* op[2]{ol.data(),orr.data()};
    for(int b=0;b<1500;++b){
        for(int i=0;i<257;++i){l[i]=sig(rng);r[i]=0.7f*l[i]+0.3f*sig(rng);}
        e.set_time_ratio(tr(rng)); e.set_pitch_semitones(ps(rng));
        uint32_t off=0; while(off<257){ const float* p[2]{l.data()+off,r.data()+off}; auto a=e.push(p,257-off); if(!a) return 1; off+=a; while(e.available()){auto n=e.pull(op,4096);for(uint32_t i=0;i<n;++i)if(!std::isfinite(ol[i])||!std::isfinite(orr[i]))return 2;} }
    }
    e.flush();
    for(int g=0;g<100000 && !e.drained();++g){auto n=e.pull(op,4096);for(uint32_t i=0;i<n;++i)if(!std::isfinite(ol[i])||!std::isfinite(orr[i]))return 3;if(n==0 && !e.drained()) return 4;}
    return e.drained()?0:5;
}
