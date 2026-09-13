#include "formant_common.hpp"
#include <clap/clap.h>
#include <algorithm>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <new>
namespace {
using namespace boiled_egg::lab;
constexpr char id[]="org.zkamiyama.boiled-egg.research.formant-lab";
const char* const features[]={CLAP_PLUGIN_FEATURE_AUDIO_EFFECT,CLAP_PLUGIN_FEATURE_PITCH_SHIFTER,CLAP_PLUGIN_FEATURE_STEREO,nullptr};
const clap_plugin_descriptor_t descriptor={CLAP_VERSION,id,"boiled egg Formant Lab (research)","zkamiyama","","","","0.1.0","Experimental fixed-pitch formant automation; not the product backend",features};
struct Plugin {
    clap_plugin_t api{};const clap_host_t* host{};boiledegg_research_host_handle* core{};
    target control;unsigned rate{},max_block{};bool processing{};
    explicit Plugin(const clap_host_t* h):host(h){}
    ~Plugin(){boiledegg_research_host_destroy(core);}
};
Plugin* self(const clap_plugin_t* p) noexcept {return static_cast<Plugin*>(p->plugin_data);}
// Validate the complete parameter list before touching DSP or audio. Malformed
// relevant events are errors, not silently truncated automation.
bool read_events(const clap_input_events_t* list,unsigned frames,bool flushing,
                 std::array<boiledegg_research_host_event,max_events>& out,unsigned& count,float& last) noexcept {
    count=0;if(!list)return true;if(!list->size||!list->get)return false;
    auto n=list->size(list);if(n>4096)return false;
    for(unsigned i=0;i<n;++i) {
        auto* h=list->get(list,i);if(!h||h->size<sizeof(*h))return false;
        if(h->space_id!=CLAP_CORE_EVENT_SPACE_ID||h->type!=CLAP_EVENT_PARAM_VALUE)continue;
        if(h->size<sizeof(clap_event_param_value_t))return false;
        auto* e=reinterpret_cast<const clap_event_param_value_t*>(h);
        if(e->param_id!=parameter_id)continue;
        if(e->note_id>=0||e->port_index>=0||e->channel>=0||e->key>=0)continue;
        if(!valid_semitones(e->value)||count==max_events||(!flushing&&(h->time>=frames||(count&&h->time<out[count-1].sample_offset))))return false;
        last=static_cast<float>(e->value);out[count++]={sizeof(out[0]),h->time,to_ratio(last),0};
    }
    return true;
}
bool CLAP_ABI init(const clap_plugin_t* p){return self(p)->host&&clap_version_is_compatible(self(p)->host->clap_version);}
void CLAP_ABI destroy(const clap_plugin_t* p){delete self(p);}
bool CLAP_ABI activate(const clap_plugin_t* p,double sr,uint32_t minimum,uint32_t maximum){
    auto& s=*self(p);if(s.core||!valid_rate(sr)||minimum<1||maximum<minimum||maximum>16384)return false;
    auto c=boiledegg_research_host_default_config(static_cast<unsigned>(sr),2,maximum);
    c.formant_ratio=to_ratio(s.control.get());boiledegg_research_pv_rt_result status{};
    s.core=boiledegg_research_host_create(&c,&status);if(!s.core)return false;
    s.rate=c.sample_rate;s.max_block=maximum;s.control.pending.store(0,std::memory_order_relaxed);
    return true;
}
void CLAP_ABI deactivate(const clap_plugin_t* p){auto& s=*self(p);s.processing=false;boiledegg_research_host_destroy(s.core);s.core=nullptr;}
bool CLAP_ABI start(const clap_plugin_t* p){auto& s=*self(p);s.processing=s.core!=nullptr;return s.processing;}
void CLAP_ABI stop(const clap_plugin_t* p){self(p)->processing=false;}
void CLAP_ABI reset(const clap_plugin_t* p){auto& s=*self(p);if(s.core)(void)boiledegg_research_host_reset(s.core);}
clap_process_status CLAP_ABI process(const clap_plugin_t* p,const clap_process_t* d){
    auto& s=*self(p);if(!s.core||!s.processing||!d||d->frames_count>s.max_block)return CLAP_PROCESS_ERROR;
    std::array<boiledegg_research_host_event,max_events> ev{};unsigned n=0;float last=0;
    if(!read_events(d->in_events,d->frames_count,false,ev,n,last))return CLAP_PROCESS_ERROR;
    if(d->audio_inputs_count!=1||d->audio_outputs_count!=1||!d->audio_inputs||!d->audio_outputs)return CLAP_PROCESS_ERROR;
    const auto& in=d->audio_inputs[0];auto& out=d->audio_outputs[0];
    if(in.channel_count!=2||out.channel_count!=2||!in.data32||!out.data32||!in.data32[0]||!in.data32[1]||!out.data32[0]||!out.data32[1])return CLAP_PROCESS_ERROR;
    if(!s.control.consume(s.core))return CLAP_PROCESS_ERROR;
    const float* inputs[]={in.data32[0],in.data32[1]};
    auto status=boiledegg_research_host_process(s.core,inputs,out.data32,d->frames_count,ev.data(),n);
    if(status!=BOILEDEGG_RESEARCH_PV_RT_OK)return CLAP_PROCESS_ERROR;
    if(n)s.control.observed(last);out.constant_mask=0;return CLAP_PROCESS_CONTINUE;
}
uint32_t CLAP_ABI ports_count(const clap_plugin_t*,bool){return 1;}
bool CLAP_ABI port_info(const clap_plugin_t*,uint32_t index,bool input,clap_audio_port_info_t* info){
    if(index||!info)return false;*info={};info->id=0;std::snprintf(info->name,sizeof(info->name),"Stereo %s",input?"In":"Out");
    info->flags=CLAP_AUDIO_PORT_IS_MAIN;info->channel_count=2;info->port_type=CLAP_PORT_STEREO;info->in_place_pair=0;return true;
}
const clap_plugin_audio_ports_t ports={ports_count,port_info};
uint32_t CLAP_ABI param_count(const clap_plugin_t*){return 1;}
bool CLAP_ABI param_info(const clap_plugin_t*,uint32_t i,clap_param_info_t* info){
    if(i||!info)return false;*info={};info->id=parameter_id;info->flags=CLAP_PARAM_IS_AUTOMATABLE|CLAP_PARAM_REQUIRES_PROCESS;
    std::snprintf(info->name,sizeof(info->name),"Formant");info->min_value=-12;info->max_value=12;info->default_value=0;return true;
}
bool CLAP_ABI param_value(const clap_plugin_t* p,clap_id i,double* v){if(i!=parameter_id||!v)return false;*v=self(p)->control.get();return true;}
bool CLAP_ABI value_text(const clap_plugin_t*,clap_id i,double v,char* text,uint32_t size){
    if(i!=parameter_id||!valid_semitones(v)||!text||size<2)return false;std::snprintf(text,size,"%+.2f st",v);return true;
}
bool CLAP_ABI text_value(const clap_plugin_t*,clap_id i,const char* text,double* v){
    if(i!=parameter_id||!text||!v)return false;char* end=nullptr;double x=std::strtod(text,&end);
    if(end==text||!valid_semitones(x))return false;while(*end==' ')++end;if(*end&&std::strcmp(end,"st"))return false;*v=x;return true;
}
void CLAP_ABI flush(const clap_plugin_t* p,const clap_input_events_t* in,const clap_output_events_t*){
    std::array<boiledegg_research_host_event,max_events> ev{};unsigned n=0;float last=0;
    if(read_events(in,0,true,ev,n,last)&&n)(void)self(p)->control.request(last);
}
const clap_plugin_params_t params={param_count,param_info,param_value,value_text,text_value,flush};
uint32_t CLAP_ABI get_latency(const clap_plugin_t* p){auto& s=*self(p);return s.core?boiledegg_research_host_latency_frames(s.core):0;}
const clap_plugin_latency_t latency_ext={get_latency};
uint32_t CLAP_ABI get_tail(const clap_plugin_t* p){return self(p)->rate?tail(self(p)->rate):0;}
const clap_plugin_tail_t tail_ext={get_tail};
bool CLAP_ABI state_save(const clap_plugin_t* p,const clap_ostream_t* stream){
    if(!stream||!stream->write)return false;auto bytes=save(self(p)->control.get());std::size_t pos=0;
    while(pos<bytes.size()){auto n=stream->write(stream,bytes.data()+pos,bytes.size()-pos);if(n<=0||static_cast<uint64_t>(n)>bytes.size()-pos)return false;pos+=static_cast<std::size_t>(n);}return true;
}
bool CLAP_ABI state_load(const clap_plugin_t* p,const clap_istream_t* stream){
    if(!stream||!stream->read)return false;std::array<std::uint8_t,16> bytes{};std::size_t pos=0;
    while(pos<bytes.size()){auto n=stream->read(stream,bytes.data()+pos,bytes.size()-pos);if(n<=0||static_cast<uint64_t>(n)>bytes.size()-pos)return false;pos+=static_cast<std::size_t>(n);}
    float st=0;if(!load(bytes,st)||!self(p)->control.request(st))return false;
    auto* host=self(p)->host;
    if(host&&host->get_extension){auto* ext=static_cast<const clap_host_params_t*>(host->get_extension(host,CLAP_EXT_PARAMS));if(ext&&ext->rescan)ext->rescan(host,CLAP_PARAM_RESCAN_VALUES);}
    return true;
}
const clap_plugin_state_t state_ext={state_save,state_load};
const void* CLAP_ABI extension(const clap_plugin_t*,const char* name){
    if(!name)return nullptr;if(!std::strcmp(name,CLAP_EXT_AUDIO_PORTS))return &ports;if(!std::strcmp(name,CLAP_EXT_PARAMS))return &params;
    if(!std::strcmp(name,CLAP_EXT_LATENCY))return &latency_ext;if(!std::strcmp(name,CLAP_EXT_STATE))return &state_ext;
    if(!std::strcmp(name,CLAP_EXT_TAIL))return &tail_ext;return nullptr;
}
void CLAP_ABI main_thread(const clap_plugin_t*){}
uint32_t CLAP_ABI plugin_count(const clap_plugin_factory_t*){return 1;}
const clap_plugin_descriptor_t* CLAP_ABI plugin_descriptor(const clap_plugin_factory_t*,uint32_t n){return n?nullptr:&descriptor;}
const clap_plugin_t* CLAP_ABI create(const clap_plugin_factory_t*,const clap_host_t* host,const char* name){
    if(!name||std::strcmp(name,id)||!host)return nullptr;auto* s=new(std::nothrow)Plugin(host);if(!s)return nullptr;
    s->api={&descriptor,s,init,destroy,activate,deactivate,start,stop,reset,process,extension,main_thread};return &s->api;
}
const clap_plugin_factory_t factory={plugin_count,plugin_descriptor,create};
bool CLAP_ABI entry_init(const char*){return true;}void CLAP_ABI entry_deinit(){}
const void* CLAP_ABI get_factory(const char* name){return name&&!std::strcmp(name,CLAP_PLUGIN_FACTORY_ID)?&factory:nullptr;}
}
extern "C" CLAP_EXPORT const clap_plugin_entry_t clap_entry={CLAP_VERSION,entry_init,entry_deinit,get_factory};
