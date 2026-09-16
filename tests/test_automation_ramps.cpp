#include <boiled_egg/boiled_egg.hpp>
#include "../src/experimental/pv/automation_curve.hpp"
#include <algorithm>
#include <array>
#include <cmath>
#include <cstdint>
#include <cstring>
#include <iostream>
#include <limits>
#include <stdexcept>
#include <vector>
using Audio=std::array<std::vector<float>,2>;
static void require(bool b,const char* text){if(!b)throw std::runtime_error(text);}
static boiledegg_ramp_event event(unsigned at,float target,unsigned duration,unsigned shape=0,unsigned id=BOILEDEGG_PARAMETER_PITCH_RATIO){
    return {sizeof(boiledegg_ramp_event),at,id,duration,shape,target,{0,0}};
}
static boiledegg_backend_config backend(unsigned io,unsigned quality=1,unsigned policy=0){
    auto b=boiledegg_default_backend_config();b.backend_id=BOILEDEGG_BACKEND_PHASE_VOCODER;
    b.flags=BOILEDEGG_BACKEND_ALLOW_EXPERIMENTAL|BOILEDEGG_BACKEND_CONTINUOUS_PITCH;
    b.io_contract=io;b.quality_mode=quality;b.formant_policy=policy;return b;
}
static Audio render(unsigned rate,unsigned quality,unsigned policy,unsigned io,unsigned block){
    auto c=boiledegg_default_config(rate,2);c.max_block_size=257;
    boiled_egg::engine h(c,backend(io,quality,policy));
    unsigned size=11003;if(io==BOILEDEGG_IO_REALTIME)size+=h.runtime_info().realtime_latency_frames;
    Audio x{std::vector<float>(size),std::vector<float>(size)},y;
    for(unsigned i=0;i<11003;++i){x[0][i]=.1f*std::sin(.03f*float(i))+.02f*std::cos(.713f*float(i));x[1][i]=-.5f*x[0][i];}
    const std::array all{event(0,.5f,777),event(779,2.f,6001,1),event(2507,1.5f,1),event(4001,1.5f,999,1),event(5507,.75f,0),event(7501,1.f,480)};
    std::array<float,8192> a{},b{};float* out[]={a.data(),b.data()};
    for(unsigned pos=0;pos<size;){auto n=std::min(block,size-pos);std::array<boiledegg_ramp_event,6> events{};unsigned ne=0;
        for(auto e:all)if(e.sample_offset>=pos&&e.sample_offset<pos+n){e.sample_offset-=pos;events[ne++]=e;}
        const float* in[]={x[0].data()+pos,x[1].data()+pos};
        if(io==BOILEDEGG_IO_REALTIME){h.process_realtime_ramps(in,out,n,std::span(events.data(),ne));
            for(unsigned ch=0;ch<2;++ch)y[ch].insert(y[ch].end(),out[ch],out[ch]+n);
            pos+=n;
        }else{auto used=h.push_ramps(in,n,std::span(events.data(),ne));require(used>0,"stream progress");pos+=used;
            while(h.available()){auto m=h.pull(out,8192);for(unsigned ch=0;ch<2;++ch)y[ch].insert(y[ch].end(),out[ch],out[ch]+m);}}
    }
    const auto before=h.automation_info();
    if(io==BOILEDEGG_IO_STREAMING){h.flush();while(h.available()){auto m=h.pull(out,8192);for(unsigned ch=0;ch<2;++ch)y[ch].insert(y[ch].end(),out[ch],out[ch]+m);}}
    const auto after=h.automation_info();require(before.input_frames==after.input_frames&&before.pitch_remaining_frames==after.pitch_remaining_frames,"flush must not advance input ramp");
    require(y[0].size()==size,"exact duration");
    for(unsigned i=0;i<size;++i){require(std::isfinite(y[0][i])&&std::isfinite(y[1][i]),"finite output");require(std::abs(y[1][i]+.5f*y[0][i])<2e-6f,"stereo relation");}
    return y;
}
int main(){try{
    unsigned samples=0,pairs=0;
    for(unsigned shape:{0U,1U})for(unsigned n:{0U,1U,31U,4800U,0xffffffffU}) {
        auto c=boiledegg_default_config(48000,1);c.max_block_size=1;boiled_egg::engine h(c,backend(BOILEDEGG_IO_STREAMING));
        auto e=event(0,2.f,n,shape);h.push_ramps(nullptr,0,std::span(&e,1));
        long double total=0;float zero=0,buffer[16]{};const float* in[]={&zero};float* out[]={buffer};
        for(unsigned i=1;i<=2000;++i){require(h.push_ramps(in,1)==1,"one input");while(h.available())h.pull(out,16);
            const auto info=h.automation_info();const long double t=n?std::min(1.L,static_cast<long double>(i)/n):1.L;
            const auto expected=shape?std::exp2(t):1.L+t;total+=expected;
            require(std::abs(info.effective_pitch_ratio-double(expected))<2e-10,"independent ratio trajectory");
            require(std::abs(info.intermediate_position-double(total))<2e-7,"independent integrated trajectory");
            require(info.input_frames==i&&info.pitch_remaining_frames==(n>i?n-i:0),"exact ramp clock");++samples;
        }
        auto before=h.automation_info();h.flush();auto after=h.automation_info();
        require(before.pitch_remaining_frames==after.pitch_remaining_frames&&before.effective_pitch_ratio==after.effective_pitch_ratio,"unfinished ramp frozen at EOS");
        h.reset();after=h.automation_info();require(!after.input_frames&&!after.pitch_remaining_frames&&after.effective_pitch_ratio==2.,"reset retains target, cancels ramp");
    }
    for(unsigned sr:{44100U,48000U,88200U,96000U})for(unsigned q:{0U,1U})for(unsigned policy:{0U,1U,2U})for(unsigned io:{1U,2U}) {
        require(render(sr,q,policy,io,32)==render(sr,q,policy,io,257),"bit-exact caller partition invariance");++pairs;
    }
    auto c=boiledegg_default_config(48000,1);c.max_block_size=32;boiled_egg::engine h(c,backend(2));
    std::array<float,32> in{},out{};out.fill(123.f);const float* ip[]={in.data()};float* op[]={out.data()};
    auto before=h.automation_info();auto valid=event(0,2.f,100);auto bad=event(32,.5f,100);
    std::array ev{valid,bad};require(h.process_realtime_ramps_nothrow(ip,op,32,ev)==BOILEDEGG_INVALID_ARGUMENT,"bad event rejected");
    auto after=h.automation_info();require(after.input_frames==before.input_frames&&after.target_pitch_ratio==before.target_pitch_ratio,"batch rejection is transactional");
    for(float v:out)require(v==123.f,"invalid batch leaves output untouched");
    bad=event(0,.5f,100);bad.reserved[1]=1;require(h.process_realtime_ramps_nothrow(ip,op,32,std::span(&bad,1))==BOILEDEGG_INVALID_ARGUMENT,"reserved field");
    bad=event(0,std::numeric_limits<float>::quiet_NaN(),100);require(h.process_realtime_ramps_nothrow(ip,op,32,std::span(&bad,1))==BOILEDEGG_INVALID_ARGUMENT,"nan event");
    ev={event(0,2.f,1),event(0,.5f,1)};h.process_realtime_ramps(ip,op,1,ev);require(h.automation_info().effective_pitch_ratio==.5,"duplicate order");
    // Same target still restarts from the current value with a new duration.
    auto restart=event(0,2.f,1000);h.process_realtime_ramps(ip,op,32,std::span(&restart,1));restart.duration_frames=17;
    h.process_realtime_ramps(ip,op,1,std::span(&restart,1));require(h.automation_info().pitch_remaining_frames==16,"explicit same-target restart");
    // Full FIFO must not consume an offset-zero command on an unaccepted sample.
    boiled_egg::engine s(c,backend(1));unsigned used=0;
    for(unsigned i=0;i<10000;++i){used=s.push_ramps(ip,32);if(used<32)break;}
    before=s.automation_info();auto pending=event(0,.75f,77);
    require(s.push_ramps(ip,32,std::span(&pending,1))==0,"backpressure must expose zero accepted");after=s.automation_info();
    require(before.input_frames==after.input_frames&&before.target_pitch_ratio==after.target_pitch_ratio,"unaccepted event not consumed");
    std::cout<<samples<<" independent trajectory samples; "<<pairs<<" paired renders; validation/backpressure/reset passed\n";
}catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}}
