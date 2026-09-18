#include "pitch_processor.hpp"
#include <boiled_egg/boiled_egg.hpp>
#include <algorithm>
#include <array>
#include <bit>
#include <cmath>
#include <iostream>
#include <limits>
#include <stdexcept>
#include <vector>
namespace p=boiled_egg::plugin;
using Audio=std::array<std::vector<float>,2>;
static void check(bool v,const char* why){if(!v)throw std::runtime_error(why);}
static Audio source(unsigned frames){Audio x{std::vector<float>(frames),std::vector<float>(frames)};for(unsigned i=0;i<frames;++i){x[0][i]=.1f*std::sin(float(i)*.027f);x[1][i]=-.5f*x[0][i];}return x;}
static Audio run(p::Processor& model,Audio x,unsigned block,bool automate){
    const std::array<p::Event,11> schedule{{{777,p::Pitch,-7},{777,p::Fine,37},{1913,p::Formant,3},{2001,p::Wet,.73f},
        {2001,p::Dry,.21f},{4017,p::Pitch,7},{4079,p::FormantFine,-21},{7001,p::Pan,-.27f},
        {7997,p::Volume,-3},{11003,p::Bypass,1},{13001,p::Bypass,0}}};
    const auto latency=model.latency();
    for(unsigned pos=0;pos<x[0].size();pos+=block){const auto n=std::min(block,unsigned(x[0].size())-pos);std::array<p::Event,256> events{};unsigned count=0;
        if(automate)for(auto e:schedule)if(e.offset>=pos&&e.offset<pos+n){e.offset-=pos;events[count++]=e;}
        const float* in[]={x[0].data()+pos,x[1].data()+pos};float* out[]={x[0].data()+pos,x[1].data()+pos};
        check(model.process(in,out,n,{events.data(),count}),"processor event block");check(model.latency()==latency,"automation changed latency");
    }return x;
}
int main(){try{
    auto values=p::defaults();const auto original=values;std::array<std::uint8_t,16> legacy{};
    p::write_word(legacy.data(),p::state_magic);p::write_word(legacy.data()+4,1);p::write_word(legacy.data()+8,std::bit_cast<unsigned>(-7.f));
    check(p::decode(legacy,values)&&values[p::Pitch]==-7&&values[p::Backend]==0&&values[p::Wet]==1&&values[p::Dry]==0,"CLAP v1 meaning");
    check(p::decode({legacy.data(),12},values)&&values[p::Policy]==0,"VST v1 meaning");
    legacy[12]=1;const auto saved=values;check(!p::decode(legacy,values)&&values==saved,"invalid legacy state transactional");
    values=p::defaults();values[p::Fine]=17;values[p::Dry]=.23f;values[p::Pan]=-.42f;auto encoded=p::encode(values);p::Values decoded{};
    check(p::decode(encoded,decoded)&&decoded==values,"state v2 exact");encoded[4]=9;check(!p::decode(encoded,decoded)&&decoded==values,"unknown state version");
    encoded=p::encode(values);p::write_word(encoded.data()+16,std::bit_cast<unsigned>(std::numeric_limits<float>::quiet_NaN()));check(!p::decode(encoded,decoded),"state NaN");
    unsigned cases=0;
    for(unsigned rate:{44100u,48000u,88200u,96000u})for(unsigned backend:{0u,1u}){
        if(backend&&!p::spectral_available())continue;
        for(bool bypass:{false,true}){
            p::Processor model;auto v=p::defaults();v[p::Backend]=float(backend);v[p::Quality]=1;v[p::Wet]=0;v[p::Dry]=1;v[p::Bypass]=bypass?1:0;
            check(model.request(v),"dry setup");const auto before=model.latency();check(model.activate(rate,257),"dry activate");(void)before;
            const auto L=model.latency();auto x=source(14013);for(auto& c:x)c.resize(c.size()+L);auto y=run(model,x,257,false);
            for(unsigned ch=0;ch<2;++ch){check(std::all_of(y[ch].begin(),y[ch].begin()+L,[](float f){return f==0;}),"dry zero prefix");
                check(std::equal(y[ch].begin()+L,y[ch].end(),x[ch].begin()),"dry/bypass latency compensation");}++cases;
        }
        // Default mix must retain the legacy WSOLA output at the same controls.
        if(!backend){p::Processor model;check(model.activate(rate,257),"default activate");auto x=source(17013),expected=x;auto c=boiledegg_default_config(rate,2);c.max_block_size=257;boiled_egg::engine old(c);
            for(unsigned pos=0;pos<x[0].size();pos+=257){auto n=std::min(257u,unsigned(x[0].size())-pos);const float* in[]={x[0].data()+pos,x[1].data()+pos};float* out[]={expected[0].data()+pos,expected[1].data()+pos};check(old.process_realtime_nothrow(in,out,n)==BOILEDEGG_OK,"legacy direct");}
            check(run(model,x,257,false)==expected,"default plugin mix changed WSOLA");++cases;
        }else{p::Processor a,b;auto v=p::defaults();v[p::Backend]=1;v[p::Policy]=1;v[p::Quality]=1;check(a.request(v)&&b.request(v)&&a.activate(rate,257)&&b.activate(rate,257),"PV setup");
            auto x=source(17017);check(run(a,x,32,true)==run(b,x,257,true),"plugin automation block partition");++cases;
        }
    }
    p::Processor model;check(model.activate(48000,32),"validation activate");float l[32],r[32];std::fill_n(l,32,17.f);std::fill_n(r,32,17.f);float* out[]={l,r};
    const auto before=model.targets.snapshot();std::array<p::Event,2> bad{{{0,p::Pitch,3},{31,p::Formant,2}}};
    check(!model.process(nullptr,out,32,bad)&&model.targets.snapshot()==before,"invalid combination changes targets");check(l[0]==17&&r[31]==17,"invalid combination changes output");
    bad[1]={32,p::Pitch,2};check(!model.process(nullptr,out,32,bad),"end offset rejected");
    if(p::spectral_available()){auto v=p::defaults();v[p::Backend]=1;v[p::Quality]=1;v[p::Policy]=1;check(model.request(v)&&model.needs_restart(),"restart pending");
        const auto L=model.latency();check(model.process(nullptr,out,32,{}),"old config runs pending restart");check(model.latency()==L,"pending config changes delay");
        model.deactivate();check(model.activate(48000,32)&&!model.needs_restart(),"restart installs explicit backend");}
    std::cout<<cases<<" plugin mix/partition comparisons; legacy/v2 state, atomic validation and restart passed\n";
}catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}}
