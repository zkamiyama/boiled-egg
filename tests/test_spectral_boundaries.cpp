#include <boiled_egg/backend.h>
#include <algorithm>
#include <array>
#include <cmath>
#include <cstring>
#include <iostream>
#include <limits>
#include <memory>
#include <stdexcept>
#include <vector>

namespace {
void require(bool good,const char* message) { if(!good) throw std::runtime_error(message); }
using Handle=std::unique_ptr<boiledegg_handle,decltype(&boiledegg_destroy)>;
boiledegg_backend_config options(unsigned quality,unsigned policy,unsigned io,float time,float pitch) {
    auto b=boiledegg_default_backend_config();
    b.backend_id=BOILEDEGG_BACKEND_PHASE_VOCODER;b.flags=BOILEDEGG_BACKEND_ALLOW_EXPERIMENTAL;
    b.quality_mode=quality;b.formant_policy=policy;b.io_contract=io;
    b.initial_time_ratio=time;b.initial_pitch_ratio=pitch;
    b.initial_formant_ratio=policy?0.75f:1.f;return b;
}
Handle create(const boiledegg_config& c,const boiledegg_backend_config& b) {
    boiledegg_result r{};Handle h(boiledegg_create_backend(&c,&b,&r),boiledegg_destroy);
    require(h && r==BOILEDEGG_OK,"spectral construction");return h;
}
std::vector<float> streaming(boiledegg_handle* h,unsigned channels,unsigned frames,unsigned block) {
    std::vector<float> input(frames),result;for(unsigned i=0;i<frames;++i)input[i]=.1f*std::sin(.1f*float(i));
    std::array<float,257> left{},right{};float* output[]={left.data(),right.data()};
    auto drain=[&] {
        while(boiledegg_available(h)) {
            uint32_t produced=0;require(boiledegg_pull(h,output,257,&produced)==BOILEDEGG_OK && produced>0,"drain makes progress");
            for(unsigned k=0;k<produced;++k){require(std::isfinite(left[k]),"finite sample");
                if(channels==2)require(left[k]==right[k],"linked identical channels");}
            result.insert(result.end(),left.begin(),left.begin()+produced);
        }
    };
    for(unsigned offset=0;offset<frames;) {
        unsigned count=std::min(block,frames-offset);const float* in[]={input.data()+offset,input.data()+offset};
        uint32_t accepted=0;const auto r=boiledegg_push(h,in,count,&accepted);
        require(r==BOILEDEGG_OK && accepted==count,"short input accepted");offset+=accepted;drain();
    }
    require(boiledegg_flush(h)==BOILEDEGG_OK,"flush");drain();
    require(boiledegg_flush(h)==BOILEDEGG_OK && boiledegg_is_drained(h),"idempotent EOS");
    uint32_t produced=999;require(boiledegg_pull(h,output,257,&produced)==BOILEDEGG_OK && produced==0,"empty post-EOS pull");
    return result;
}
}
int main() { try {
    unsigned cells=0;
    // Exercise zero/one/odd input and both rate-scaling boundaries, not only
    // steady multi-second WAVs. Four-byte size-prefix tests are separate below.
    for(unsigned rate:{44100u,48000u,88200u,96000u})for(unsigned channels:{1u,2u})
    for(unsigned quality:{0u,1u})for(unsigned policy:{0u,1u,2u})
    for(auto control:{std::pair{.5f,.5f},std::pair{1.f,2.f},std::pair{2.f,1.f}}) {
        auto c=boiledegg_default_config(rate,channels);c.max_block_size=257;
        auto b=options(quality,policy,BOILEDEGG_IO_STREAMING,control.first,control.second);
        auto h=create(c,b);
        for(unsigned frames:{0u,1u,31u,513u}) {
            require(boiledegg_reset(h.get())==BOILEDEGG_OK,"reset");
            auto a=streaming(h.get(),channels,frames,31);
            require(a.size()==static_cast<size_t>(std::llround(double(frames)*control.first)),"short exact duration");
            require(boiledegg_reset(h.get())==BOILEDEGG_OK,"repeat reset");
            require(a==streaming(h.get(),channels,frames,257),"short block partition invariance");++cells;
        }
    }
    auto c=boiledegg_default_config(48000,1);c.max_block_size=64;
    auto b=options(1,1,BOILEDEGG_IO_REALTIME,1,1);auto h=create(c,b);
    uint32_t size_only=sizeof(uint32_t);
    require(boiledegg_get_backend_parameter_state(h.get(),reinterpret_cast<boiledegg_backend_parameter_state*>(&size_only))==BOILEDEGG_INVALID_ARGUMENT,"short state output");
    require(boiledegg_set_backend_parameter_state(h.get(),reinterpret_cast<const boiledegg_backend_parameter_state*>(&size_only))==BOILEDEGG_INVALID_ARGUMENT,"short state input");
    struct Extended {boiledegg_backend_parameter_state state;std::array<uint32_t,4> tail;};
    Extended ext{};ext.state.struct_size=sizeof(ext);ext.tail.fill(0x12345678);
    require(boiledegg_get_backend_parameter_state(h.get(),&ext.state)==BOILEDEGG_OK,"extended state output");
    for(auto v:ext.tail)require(v==0x12345678,"future caller tail preserved");
    auto before=ext.state;ext.state.reserved=1;
    require(boiledegg_set_backend_parameter_state(h.get(),&ext.state)==BOILEDEGG_INVALID_ARGUMENT,"reserved state rejected");
    require(boiledegg_get_formant_ratio(h.get())==before.formant_ratio,"rejected state leaves target unchanged");
    float input[64]{},output[64];std::fill_n(output,64,123.f);const float* in[]={input};float* out[]={output};
    std::array<boiledegg_parameter_event,257> ev{};
    for(auto& event:ev)event={sizeof(event),0,BOILEDEGG_PARAMETER_FORMANT_RATIO,1.25f};
    require(boiledegg_process_realtime(h.get(),in,out,64,ev.data(),257)==BOILEDEGG_INVALID_ARGUMENT,"event bound");
    for(float v:output)require(v==123.f,"invalid events leave output untouched");
    require(boiledegg_get_formant_ratio(h.get())==before.formant_ratio,"invalid events leave target untouched");
    require(boiledegg_process_realtime(h.get(),in,out,64,ev.data(),256)==BOILEDEGG_OK,"maximum duplicate-offset events accepted");
    require(boiledegg_get_formant_ratio(h.get())==1.25f,"last target delivered");
    ev[0]={sizeof(ev[0]),0,BOILEDEGG_PARAMETER_FORMANT_SEMITONES,-12.f};
    require(boiledegg_process_realtime(h.get(),nullptr,nullptr,0,ev.data(),1)==BOILEDEGG_OK,"parameter-only update");
    require(boiledegg_get_formant_ratio(h.get())==.5f,"semitone conversion");
    boiledegg_runtime_info rt{};rt.struct_size=sizeof(rt);require(boiledegg_get_runtime_info(h.get(),&rt)==BOILEDEGG_OK,"runtime info");
    require(!(rt.capabilities&BOILEDEGG_CAP_HARD_REALTIME_PROCESSING),"preview cannot advertise hard realtime");
    require(rt.realtime_latency_frames>0,"explicit fixed output delay");
    for(unsigned unsupported_rate:{44099u,50000u,96001u}) {
        c.sample_rate=unsupported_rate;require(boiledegg_validate_backend_config(&c,&b)==BOILEDEGG_UNSUPPORTED_MODE,"discrete sample rate contract");
    }
    std::cout<<cells<<" short/zero/odd exact-duration and partition cells; sized state, event bounds and truthful capabilities passed\n";
} catch(const std::exception& ex) {std::cerr<<ex.what()<<'\n';return 1;} }
