#include "formant_common.hpp"
#include "test_alloc.hpp"
#include <clap/clap.h>
#include <dlfcn.h>
#include <algorithm>
#include <cstring>
#include <iostream>
#include <limits>
#include <memory>
#include <stdexcept>
#include <vector>
using namespace boiled_egg::lab;
static void require(bool v,const char* why){if(!v)throw std::runtime_error(why);}
struct Events {
    std::array<clap_event_param_value_t,257> data{};unsigned count=0;
    clap_input_events_t api{this,[](const clap_input_events_t* p){return static_cast<Events*>(p->ctx)->count;},
        [](const clap_input_events_t* p,uint32_t i)->const clap_event_header_t*{auto* s=static_cast<Events*>(p->ctx);return i<s->count?&s->data[i].header:nullptr;}};
    void add(unsigned offset,double st){auto& e=data[count++];e={};e.header={sizeof(e),offset,CLAP_CORE_EVENT_SPACE_ID,CLAP_EVENT_PARAM_VALUE,0};e.param_id=parameter_id;e.note_id=-1;e.port_index=-1;e.channel=-1;e.key=-1;e.value=st;}
};
struct Memory {
    std::array<unsigned char,16> bytes{};unsigned pos=0,limit=16,step=3;
    clap_ostream_t out{this,[](const clap_ostream_t* p,const void* b,uint64_t n)->int64_t{auto& s=*static_cast<Memory*>(p->ctx);auto size=std::min<uint64_t>({n,s.limit-s.pos,s.step});std::memcpy(s.bytes.data()+s.pos,b,size);s.pos+=static_cast<unsigned>(size);return static_cast<int64_t>(size);}};
    clap_istream_t in{this,[](const clap_istream_t* p,void* b,uint64_t n)->int64_t{auto& s=*static_cast<Memory*>(p->ctx);auto size=std::min<uint64_t>({n,s.limit-s.pos,s.step});std::memcpy(b,s.bytes.data()+s.pos,size);s.pos+=static_cast<unsigned>(size);return static_cast<int64_t>(size);}};
};
int main(int argc,char** argv){try{
    require(argc==2,"plugin path required");void* library=dlopen(argv[1],RTLD_NOW|RTLD_LOCAL);require(library,"dlopen");
    auto* entry=static_cast<const clap_plugin_entry_t*>(dlsym(library,"clap_entry"));require(entry&&entry->init(argv[1]),"entry");
    auto* factory=static_cast<const clap_plugin_factory_t*>(entry->get_factory(CLAP_PLUGIN_FACTORY_ID));require(factory&&factory->get_plugin_count(factory)==1,"factory");
    clap_host_t host{CLAP_VERSION,nullptr,"Formant Lab Test","boiled egg","","0.1",[](const clap_host_t*,const char*)->const void*{return nullptr;},[](const clap_host_t*){},[](const clap_host_t*){},[](const clap_host_t*){}};
    auto* descriptor=factory->get_plugin_descriptor(factory,0);unsigned comparisons=0;
    for(unsigned sr:{44100U,48000U,96000U})for(unsigned block:{32U,64U,257U})for(bool inplace:{false,true}){
        auto* p=factory->create_plugin(factory,&host,descriptor->id);require(p&&p->init(p),"plugin init");
        auto* params=static_cast<const clap_plugin_params_t*>(p->get_extension(p,CLAP_EXT_PARAMS));
        auto* lat=static_cast<const clap_plugin_latency_t*>(p->get_extension(p,CLAP_EXT_LATENCY));auto* state=static_cast<const clap_plugin_state_t*>(p->get_extension(p,CLAP_EXT_STATE));
        auto* tails=static_cast<const clap_plugin_tail_t*>(p->get_extension(p,CLAP_EXT_TAIL));require(params&&lat&&state&&tails,"extensions");
        Events init;init.add(0,-3);params->flush(p,&init.api,nullptr);
        Memory saved;require(state->save(p,&saved.out)&&saved.pos==16,"partial state writes");
        Events changed;changed.add(0,6);params->flush(p,&changed.api,nullptr);saved.pos=0;require(state->load(p,&saved.in),"partial state reads");
        double v=0;require(params->get_value(p,parameter_id,&v)&&v==-3,"state restores target");
        Memory bad;bad.bytes=saved.bytes;bad.bytes[4]=9;require(!state->load(p,&bad.in),"bad state version rejected");
        require(params->get_value(p,parameter_id,&v)&&v==-3,"invalid state is transactional");
        require(!p->activate(p,48000.5,1,block),"fractional sample rate rejected");require(p->activate(p,sr,1,block)&&p->start_processing(p),"activate");
        unsigned L=lat->get(p);require(L==latency(sr),"reported delay");
        auto cfg=boiledegg_research_host_default_config(sr,2,block);cfg.formant_ratio=to_ratio(-3);boiledegg_research_pv_rt_result r{};
        auto* reference=boiledegg_research_host_create(&cfg,&r);require(reference&&!r,"reference create");
        std::array<std::vector<float>,2> input{std::vector<float>(block),std::vector<float>(block)},output=input,oracle=input;
        const unsigned marks[]={0U,777U,1559U,4097U,6200U};unsigned mark=0;
        for(unsigned pos=0;pos<sr/3+L;pos+=block){unsigned n=std::min(block,sr/3+L-pos);Events ev;std::array<boiledegg_research_host_event,8> re{};unsigned rc=0;
            while(mark<5&&marks[mark]<pos+n){if(marks[mark]>=pos){float st=mark%2?-12.F:12.F;ev.add(marks[mark]-pos,st);re[rc++]={sizeof(re[0]),marks[mark]-pos,to_ratio(st),0};}++mark;}
            for(unsigned i=0;i<n;++i){input[0][i]=.17F*std::sin(.041F*float(pos+i))+.07F*std::cos(.12F*float(pos+i));input[1][i]=-.5F*input[0][i];}
            const float* ri[]={input[0].data(),input[1].data()};float* ro[]={oracle[0].data(),oracle[1].data()};
            require(boiledegg_research_host_process(reference,ri,ro,n,re.data(),rc)==0,"reference process");
            float* ins[]={input[0].data(),input[1].data()};float* outs[]={inplace?ins[0]:output[0].data(),inplace?ins[1]:output[1].data()};
            clap_audio_buffer_t a{ins,nullptr,2,0,0},b{outs,nullptr,2,0,0};clap_process_t d{};d.frames_count=n;d.audio_inputs=&a;d.audio_outputs=&b;d.audio_inputs_count=d.audio_outputs_count=1;d.in_events=&ev.api;
            count_allocations=true;auto status=p->process(p,&d);count_allocations=false;require(status!=CLAP_PROCESS_ERROR,"CLAP process");
            for(unsigned ch=0;ch<2;++ch)require(std::equal(outs[ch],outs[ch]+n,oracle[ch].begin()),"CLAP equals bridge");
            require(lat->get(p)==L,"automation changed latency");
        }
        Events invalid;invalid.add(0,3);invalid.add(block,6);float* ins[]={input[0].data(),input[1].data()};float* outs[]={output[0].data(),output[1].data()};
        clap_audio_buffer_t a{ins,nullptr,2,0,0},b{outs,nullptr,2,0,0};clap_process_t d{};d.frames_count=block;d.audio_inputs=&a;d.audio_outputs=&b;d.audio_inputs_count=d.audio_outputs_count=1;d.in_events=&invalid.api;
        for(auto& ch:output)std::fill(ch.begin(),ch.end(),123.F);require(p->process(p,&d)==CLAP_PROCESS_ERROR,"out-of-range automation rejected");
        for(auto& ch:output)for(float s:ch)require(s==123.F,"invalid automation mutated output");
        // Clear controls and verify the advertised finite tail using an impulse.
        Events flat;flat.add(0,0);params->flush(p,&flat.api,nullptr);p->reset(p);d.in_events=nullptr;unsigned T=tails->get(p);
        for(unsigned pos=0;pos<T+2048;pos+=block){d.frames_count=std::min(block,T+2048-pos);for(auto& ch:input)std::fill(ch.begin(),ch.end(),0.F);if(!pos)input[0][0]=input[1][0]=.5F;
            require(p->process(p,&d)!=CLAP_PROCESS_ERROR,"tail processing");if(pos>=T)for(unsigned ch=0;ch<2;++ch)for(unsigned i=0;i<d.frames_count;++i)require(std::abs(outs[ch][i])<1e-12F,"reported tail too short");}
        boiledegg_research_host_destroy(reference);p->stop_processing(p);p->deactivate(p);p->destroy(p);++comparisons;
    }
    require(!allocations.load(),"CLAP process allocated");entry->deinit();dlclose(library);
    std::cout<<comparisons<<" loaded CLAP bridge-equality cases; events/state/tail/in-place; zero process allocations\n";
}catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}}
