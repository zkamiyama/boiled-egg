#include "boiled_egg_research_host.h"
#include "../src/host_latency_bound.hpp"
#include <algorithm>
#include <array>
#include <cmath>
#include <iostream>
#include <stdexcept>
#include <vector>
static void require(bool x,const char* m){if(!x)throw std::runtime_error(m);}
int main(){try{
    unsigned models=0,real=0;
    // Worst allowed completion time at every frame; also alternate early/late
    // completion to stress burst cleanup. No audio-dependent fitted constant.
    for(unsigned n:{512U,1024U,2048U,4096U})for(unsigned h:{n/4,n*3/8})
    for(unsigned j=0;j<=120;++j)for(bool burst:{false,true}){
        float p=.5F+1.5F*static_cast<float>(j)/120;
        unsigned D=boiled_egg::research::detail::child_latency_bound(n,h,p),cleaned=0,emitted=0,k=0,safe=0;
        for(unsigned t=1;t<12*n;++t){
            while(t>=n/2+k*h+((!burst||k%2)?h:0)) {safe=static_cast<unsigned>(std::llround(k*h*double(p)));++k;}
            cleaned=std::min(safe,cleaned+8);
            unsigned available=cleaned>n/2?cleaned-n/2:0;
            for(unsigned step=0;step<2&&emitted<t;++step){
                if(static_cast<unsigned>(std::floor(emitted*double(p)))+21>=available)break;++emitted;
            }
            require(emitted>=((t>D)?t-D:0),"analytical service bound failed");
        }
        ++models;
    }
    // Broad actual-runtime corner coverage beyond the independent 90-case
    // waveform oracle test: odd blocks, eight channels, noninteger ratios,
    // both formant policies, higher rates, silence/nonzero alternating input.
    for(unsigned rate:{48000U,96000U,192000U})for(unsigned profile:{0U,1U,2U,3U,4U})
    for(unsigned channels:{1U,8U})for(float p:{.5F,.501F,.667F,1.F,1.337F,1.999F,2.F}){
        auto c=boiledegg_research_host_default_config(rate,channels,31);c.profile=profile;c.pitch_ratio=p;c.formant_mode=1+((real/3)%2);
        boiledegg_research_pv_rt_result status{};auto* h=boiledegg_research_host_create_compact(&c,&status);require(h&&status==0,"create compact");
        std::array<std::array<float,31>,8> x{},y{};const float* in[8]{};float* out[8]{};
        for(unsigned ch=0;ch<channels;++ch){in[ch]=x[ch].data();out[ch]=y[ch].data();}
        auto D=boiledegg_research_host_latency_frames(h);require(D==boiledegg_research_host_compact_latency(&c),"bound query");
        unsigned rng=129;
        for(unsigned pos=0;pos<D+5003;pos+=31){
            for(unsigned ch=0;ch<channels;++ch)for(unsigned i=0;i<31;++i){rng=1664525U*rng+1013904223U;x[ch][i]=((pos/127)%3)?float(int(rng>>16)-32768)/100000.F:0.F;}
            boiledegg_research_host_event ev{sizeof(ev),13,(pos/31)%2?.5F:2.F,0};
            auto result=boiledegg_research_host_process(h,in,out,31,&ev,1);
            if(result){boiledegg_research_host_stats st{};st.struct_size=sizeof(st);boiledegg_research_host_get_stats(h,&st);
                std::cerr<<"failure rate="<<rate<<" profile="<<profile<<" channels="<<channels<<" pitch="<<p<<" formant="<<c.formant_mode<<" position="<<pos<<" delay="<<D<<" status="<<result<<" underrun="<<st.underruns<<" frame_overrun="<<st.execution.frame_overruns<<" frame_steps="<<st.execution.max_frame_steps<<" budget="<<st.execution.steps_per_input<<'\n';}
            require(result==0,"readiness underrun");
            for(unsigned ch=0;ch<channels;++ch)for(float v:y[ch])require(std::isfinite(v),"finite output");
        }
        boiledegg_research_host_stats stats{};stats.struct_size=sizeof(stats);boiledegg_research_host_get_stats(h,&stats);
        require(!stats.underruns&&!stats.execution.frame_overruns,"zero underruns");boiledegg_research_host_destroy(h);++real;
    }
    std::cout<<models<<" service-bound models; "<<real<<" runtime compact-latency corners passed\n";
}catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}}
