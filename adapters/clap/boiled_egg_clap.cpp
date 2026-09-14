#include "pitch_processor.hpp"
#include "pitch_editor.hpp"
#include <clap/clap.h>
#include <algorithm>
#include <array>
#include <atomic>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <memory>
#include <new>
namespace {
using namespace boiled_egg::plugin;
struct UiEvent {unsigned index,kind;float value;};
struct UiQueue {
 std::array<UiEvent,1024> values{};std::atomic<unsigned> read{},write{};
 unsigned free()const noexcept{return unsigned(values.size())-(write.load(std::memory_order_relaxed)-read.load(std::memory_order_acquire));}
 bool put(UiEvent e,unsigned reserve)noexcept{if(free()<reserve)return false;const auto w=write.load(std::memory_order_relaxed);values[w%values.size()]=e;write.store(w+1,std::memory_order_release);return true;}
};
struct Plugin {
 clap_plugin_t clap{};const clap_host_t* host{};const clap_host_params_t* host_params{};Processor processor;UiQueue ui;
 bool processing{};
#ifdef BOILED_EGG_PLUGIN_X11
 const clap_host_timer_support_t* timers{};std::unique_ptr<PitchEditor> editor;clap_id timer_id=CLAP_INVALID_ID;
 unsigned width=PitchEditor::default_width,height=PitchEditor::default_height;
#endif
 explicit Plugin(const clap_host_t* h):host(h){}
};
Plugin* self(const clap_plugin_t* p)noexcept{return static_cast<Plugin*>(p->plugin_data);}
bool parse(const clap_input_events_t* list,unsigned n,bool flushing,std::array<Event,256>& events,unsigned& count)noexcept{
 count=0;if(!list)return true;if(!list->size||!list->get)return false;const auto size=list->size(list);if(size>4096)return false;
 for(unsigned i=0;i<size;++i){const auto* header=list->get(list,i);if(!header||header->size<sizeof(*header))return false;
  if(header->space_id!=CLAP_CORE_EVENT_SPACE_ID||header->type!=CLAP_EVENT_PARAM_VALUE)continue;
  if(header->size<sizeof(clap_event_param_value_t))return false;const auto* e=reinterpret_cast<const clap_event_param_value_t*>(header);unsigned index;
  if(!clap_index(e->param_id,index)||e->note_id>=0||e->port_index>=0||e->channel>=0||e->key>=0)continue;
  if(count>=events.size()||!valid_value(index,float(e->value))||!std::isfinite(e->value))return false;
  if(!flushing&&((n?header->time>=n:header->time!=0)||(count&&header->time<events[count-1].offset)))return false;
  events[count++]={flushing?0:header->time,index,float(e->value)};
 }return true;
}
void output_ui(Plugin& p,const clap_output_events_t* out)noexcept{
 if(!out||!out->try_push)return;
 unsigned r=p.ui.read.load(std::memory_order_relaxed);const auto end=p.ui.write.load(std::memory_order_acquire);
 for(unsigned n=0;r!=end&&n<1024;++n){const auto& e=p.ui.values[r%p.ui.values.size()];bool accepted=false;
  if(e.kind==1){clap_event_param_value_t v{};v.header={sizeof(v),0,CLAP_CORE_EVENT_SPACE_ID,CLAP_EVENT_PARAM_VALUE,CLAP_EVENT_IS_LIVE};v.param_id=clap_param_id(e.index);v.value=e.value;v.note_id=-1;v.port_index=v.channel=v.key=-1;accepted=out->try_push(out,&v.header);}
  else {clap_event_param_gesture_t g{};g.header={sizeof(g),0,CLAP_CORE_EVENT_SPACE_ID,std::uint16_t(e.kind==0?CLAP_EVENT_PARAM_GESTURE_BEGIN:CLAP_EVENT_PARAM_GESTURE_END),CLAP_EVENT_IS_LIVE};g.param_id=clap_param_id(e.index);accepted=out->try_push(out,&g.header);}
  if(!accepted)break;++r;p.ui.read.store(r,std::memory_order_release);
 }
}
void request_restart(Plugin& p)noexcept{if(p.processor.needs_restart()&&p.host->request_callback)p.host->request_callback(p.host);}
bool apply_controls(Plugin& p,const clap_input_events_t* in)noexcept{
 std::array<Event,256> events{};unsigned n=0;if(!parse(in,0,true,events,n))return false;auto v=p.processor.targets.snapshot();for(unsigned i=0;i<n;++i)v[events[i].index]=events[i].value;
 if(!p.processor.request(v))return false;request_restart(p);return true;
}
bool CLAP_ABI init(const clap_plugin_t* p){auto& s=*self(p);if(!s.host||!clap_version_is_compatible(s.host->clap_version))return false;
 if(s.host->get_extension){s.host_params=static_cast<const clap_host_params_t*>(s.host->get_extension(s.host,CLAP_EXT_PARAMS));
#ifdef BOILED_EGG_PLUGIN_X11
 s.timers=static_cast<const clap_host_timer_support_t*>(s.host->get_extension(s.host,CLAP_EXT_TIMER_SUPPORT));
#endif
 }return true;}
#ifdef BOILED_EGG_PLUGIN_X11
void CLAP_ABI gui_destroy(const clap_plugin_t* p){auto& s=*self(p);if(s.timer_id!=CLAP_INVALID_ID&&s.timers&&s.timers->unregister_timer)s.timers->unregister_timer(s.host,s.timer_id);s.timer_id=CLAP_INVALID_ID;s.editor.reset();}
#endif
void CLAP_ABI destroy(const clap_plugin_t* p){
#ifdef BOILED_EGG_PLUGIN_X11
 gui_destroy(p);
#endif
 delete self(p);}
bool CLAP_ABI activate(const clap_plugin_t* p,double rate,uint32_t min,uint32_t max){if(!std::isfinite(rate)||rate<8000||rate>384000||rate!=std::floor(rate)||min<1||max<min)return false;
 try{return self(p)->processor.activate(unsigned(rate),max);}catch(...){return false;}}
void CLAP_ABI deactivate(const clap_plugin_t* p){self(p)->processing=false;self(p)->processor.deactivate();}
bool CLAP_ABI start(const clap_plugin_t* p){auto& s=*self(p);s.processing=s.processor.is_active();return s.processing;}
void CLAP_ABI stop(const clap_plugin_t* p){self(p)->processing=false;}
void CLAP_ABI reset(const clap_plugin_t* p){(void)self(p)->processor.reset();}
clap_process_status CLAP_ABI process(const clap_plugin_t* p,const clap_process_t* d){
 auto& s=*self(p);if(!d||!s.processing)return CLAP_PROCESS_ERROR;std::array<Event,256> events{};unsigned count=0;
 if(!parse(d->in_events,d->frames_count,false,events,count))return CLAP_PROCESS_ERROR;
 if(!d->frames_count){if(!apply_controls(s,d->in_events))return CLAP_PROCESS_ERROR;output_ui(s,d->out_events);return CLAP_PROCESS_CONTINUE;}
 if(d->audio_inputs_count!=1||d->audio_outputs_count!=1||!d->audio_inputs||!d->audio_outputs)return CLAP_PROCESS_ERROR;
 const auto& in=d->audio_inputs[0];auto& out=d->audio_outputs[0];if(in.channel_count!=2||out.channel_count!=2||!in.data32||!out.data32)return CLAP_PROCESS_ERROR;
 const float* inputs[]={in.data32[0],in.data32[1]};if(!s.processor.process(inputs,out.data32,d->frames_count,std::span(events.data(),count)))return CLAP_PROCESS_ERROR;
 out.constant_mask=0;output_ui(s,d->out_events);request_restart(s);return CLAP_PROCESS_CONTINUE;
}
uint32_t CLAP_ABI ports_count(const clap_plugin_t*,bool){return 1;}
bool CLAP_ABI ports_get(const clap_plugin_t*,uint32_t i,bool input,clap_audio_port_info_t* info){if(i||!info)return false;*info={};info->id=0;std::snprintf(info->name,sizeof(info->name),"Stereo %s",input?"Input":"Output");info->flags=CLAP_AUDIO_PORT_IS_MAIN;info->channel_count=2;info->port_type=CLAP_PORT_STEREO;info->in_place_pair=0;return true;}
uint32_t CLAP_ABI param_count(const clap_plugin_t*){return Count;}
bool CLAP_ABI param_info(const clap_plugin_t*,uint32_t i,clap_param_info_t* info){if(i>=Count||!info)return false;const auto& d=parameters[i];*info={};info->id=clap_param_id(i);
 info->flags=(d.automatable?CLAP_PARAM_IS_AUTOMATABLE|CLAP_PARAM_REQUIRES_PROCESS:0)|(d.stepped?CLAP_PARAM_IS_STEPPED:0);
 std::snprintf(info->name,sizeof(info->name),"%s",d.name);std::snprintf(info->module,sizeof(info->module),"%s",i>=Backend?"Processing (restart)":"Shifter 1");
 info->min_value=d.min;info->max_value=d.max;info->default_value=d.initial;return true;}
bool CLAP_ABI param_get(const clap_plugin_t* p,clap_id id,double* value){unsigned i;if(!value||!clap_index(id,i))return false;*value=self(p)->processor.targets.get(i);return true;}
bool CLAP_ABI value_text(const clap_plugin_t*,clap_id id,double value,char* text,uint32_t cap){unsigned i;if(!text||!cap||!clap_index(id,i)||!std::isfinite(value)||!valid_value(i,float(value)))return false;
 const int n=parameters[i].stepped?std::snprintf(text,cap,"%s",choice(i,int(value))):std::snprintf(text,cap,"%.2f %s",value,parameters[i].unit);return n>=0&&unsigned(n)<cap;}
bool CLAP_ABI text_value(const clap_plugin_t*,clap_id id,const char* text,double* value){unsigned i;if(!text||!value||!clap_index(id,i))return false;
 if(parameters[i].stepped){for(int v=int(parameters[i].min);v<=int(parameters[i].max);++v)if(!std::strcmp(text,choice(i,v))){*value=v;return true;}}
 char* end=nullptr;double v=std::strtod(text,&end);if(end==text||!std::isfinite(v)||!valid_value(i,float(v)))return false;while(*end==' ')++end;if(*end&&std::strcmp(end,parameters[i].unit))return false;*value=v;return true;}
void CLAP_ABI param_flush(const clap_plugin_t* p,const clap_input_events_t* in,const clap_output_events_t* out){auto& s=*self(p);(void)apply_controls(s,in);output_ui(s,out);}
uint32_t CLAP_ABI get_latency(const clap_plugin_t* p){return self(p)->processor.latency();}
uint32_t CLAP_ABI get_tail(const clap_plugin_t* p){return self(p)->processor.tail();}
bool read_all(const clap_istream_t* stream,void* data,std::size_t n)noexcept{if(!stream||!stream->read)return false;std::size_t pos=0;while(pos<n){const auto used=stream->read(stream,static_cast<char*>(data)+pos,n-pos);if(used<=0||std::uint64_t(used)>n-pos)return false;pos+=std::size_t(used);}return true;}
bool CLAP_ABI state_save(const clap_plugin_t* p,const clap_ostream_t* stream){if(!stream||!stream->write)return false;const auto values=self(p)->processor.targets.snapshot();if(!valid_values(values))return false;const auto b=encode(values);std::size_t pos=0;
 while(pos<b.size()){const auto n=stream->write(stream,b.data()+pos,b.size()-pos);if(n<=0||std::uint64_t(n)>b.size()-pos)return false;pos+=std::size_t(n);}return true;}
bool CLAP_ABI state_load(const clap_plugin_t* p,const clap_istream_t* stream){std::array<std::uint8_t,state_size> b{};if(!read_all(stream,b.data(),8))return false;
 if(read_word(b.data())!=state_magic)return false;const auto v=read_word(b.data()+4);const std::size_t n=v==1?16:v==2?state_size:0;if(!n||!read_all(stream,b.data()+8,n-8))return false;
 Values values;if(!decode(std::span(b.data(),n),values))return false;auto& s=*self(p);if(!s.processor.request(values))return false;
 if(s.host_params&&s.host_params->rescan)s.host_params->rescan(s.host,CLAP_PARAM_RESCAN_VALUES);request_restart(s);return true;}
#ifdef BOILED_EGG_PLUGIN_X11
bool gui_edit(void* user,unsigned i,float value,Gesture stage)noexcept {auto& p=*static_cast<Plugin*>(user);const unsigned kind=stage==Gesture::Begin?0:stage==Gesture::Value?1:2;
 const unsigned reserve=kind==0?3:kind==1?2:1;if(p.ui.free()<reserve)return false;
 if(stage==Gesture::Value&&!p.processor.request(i,value))return false;
 if(!p.ui.put({i,kind,value},reserve))return false;
 if(p.host_params&&p.host_params->request_flush)p.host_params->request_flush(p.host);request_restart(p);return true;}
bool CLAP_ABI gui_supported(const clap_plugin_t* p,const char* api,bool floating){return api&&!std::strcmp(api,CLAP_WINDOW_API_X11)&&!floating&&self(p)->timers;}
bool CLAP_ABI gui_preferred(const clap_plugin_t* p,const char** api,bool* floating){if(!api||!floating||!self(p)->timers)return false;*api=CLAP_WINDOW_API_X11;*floating=false;return true;}
bool CLAP_ABI gui_create(const clap_plugin_t* p,const char* api,bool floating){auto& s=*self(p);if(s.editor||!gui_supported(p,api,floating)||!s.timers->register_timer)return false;
 EditorCallbacks cb{&s,[](void* p)noexcept{return static_cast<Plugin*>(p)->processor.targets.snapshot();},gui_edit,
  [](void* p)noexcept{return static_cast<Plugin*>(p)->processor.latency();},[](void* p)noexcept{return static_cast<Plugin*>(p)->processor.needs_restart();},[](void* p)noexcept{return static_cast<Plugin*>(p)->processor.error();}};
 try{s.editor=std::make_unique<PitchEditor>(cb);}catch(...){return false;}
 if(!s.timers->register_timer(s.host,33,&s.timer_id)){s.editor.reset();return false;}return true;}
bool CLAP_ABI gui_size(const clap_plugin_t* p,uint32_t* w,uint32_t* h){if(!w||!h||!self(p)->editor)return false;*w=self(p)->width;*h=self(p)->height;return true;}
bool CLAP_ABI gui_adjust(const clap_plugin_t*,uint32_t* w,uint32_t* h){if(!w||!h)return false;*w=std::clamp(*w,760u,1800u);*h=std::clamp(*h,560u,1280u);return true;}
bool CLAP_ABI gui_set_size(const clap_plugin_t* p,uint32_t w,uint32_t h){auto& s=*self(p);if(!s.editor||!s.editor->resize(w,h))return false;s.width=w;s.height=h;return true;}
bool CLAP_ABI gui_scale(const clap_plugin_t* p,double scale){if(!std::isfinite(scale)||scale<.9||scale>2.)return false;return gui_set_size(p,uint32_t(900*scale),uint32_t(640*scale));}
bool CLAP_ABI gui_can_resize(const clap_plugin_t*){return true;}
bool CLAP_ABI gui_hints(const clap_plugin_t*,clap_gui_resize_hints_t* h){if(!h)return false;*h={true,true,false,0,0};return true;}
bool CLAP_ABI gui_parent(const clap_plugin_t* p,const clap_window_t* window){auto& s=*self(p);return window&&window->api&&!std::strcmp(window->api,CLAP_WINDOW_API_X11)&&s.editor&&s.editor->attach(window->x11);}
bool CLAP_ABI gui_transient(const clap_plugin_t*,const clap_window_t*){return false;}
void CLAP_ABI gui_title(const clap_plugin_t*,const char*){}
bool CLAP_ABI gui_show(const clap_plugin_t* p){auto& s=*self(p);if(!s.editor||!s.editor->window())return false;s.editor->show(true);return true;}
bool CLAP_ABI gui_hide(const clap_plugin_t* p){auto& s=*self(p);if(!s.editor)return false;s.editor->show(false);return true;}
void CLAP_ABI timer(const clap_plugin_t* p,clap_id id){auto& s=*self(p);if(s.editor&&id==s.timer_id)s.editor->pump();}
const clap_plugin_timer_support_t timer_ext{timer};
const clap_plugin_gui_t gui_ext{gui_supported,gui_preferred,gui_create,gui_destroy,gui_scale,gui_size,gui_can_resize,gui_hints,gui_adjust,gui_set_size,gui_parent,gui_transient,gui_title,gui_show,gui_hide};
#endif
const clap_plugin_audio_ports_t ports{ports_count,ports_get};const clap_plugin_params_t params{param_count,param_info,param_get,value_text,text_value,param_flush};
const clap_plugin_latency_t latency{get_latency};const clap_plugin_tail_t tail{get_tail};const clap_plugin_state_t state{state_save,state_load};
const void* CLAP_ABI extension(const clap_plugin_t*,const char* name){if(!name)return nullptr;
 if(!std::strcmp(name,CLAP_EXT_AUDIO_PORTS))return &ports;if(!std::strcmp(name,CLAP_EXT_PARAMS))return &params;if(!std::strcmp(name,CLAP_EXT_LATENCY))return &latency;if(!std::strcmp(name,CLAP_EXT_TAIL))return &tail;if(!std::strcmp(name,CLAP_EXT_STATE))return &state;
#ifdef BOILED_EGG_PLUGIN_X11
 if(!std::strcmp(name,CLAP_EXT_GUI))return &gui_ext;if(!std::strcmp(name,CLAP_EXT_TIMER_SUPPORT))return &timer_ext;
#endif
 return nullptr;}
void CLAP_ABI main_thread(const clap_plugin_t* p){auto& s=*self(p);if(s.processor.needs_restart()&&s.host->request_restart)s.host->request_restart(s.host);}
const char* const features[]={CLAP_PLUGIN_FEATURE_AUDIO_EFFECT,CLAP_PLUGIN_FEATURE_PITCH_SHIFTER,CLAP_PLUGIN_FEATURE_STEREO,nullptr};
const clap_plugin_descriptor_t descriptor{CLAP_VERSION_INIT,"io.github.zkamiyama.boiled-egg","boiled egg","zkamiyama","https://github.com/zkamiyama/boiled-egg","","","0.1.3-preview","Manual pitch/formant processor with compensated dry path",features};
uint32_t CLAP_ABI factory_count(const clap_plugin_factory_t*){return 1;}
const clap_plugin_descriptor_t* CLAP_ABI factory_descriptor(const clap_plugin_factory_t*,uint32_t i){return i?nullptr:&descriptor;}
const clap_plugin_t* CLAP_ABI factory_create(const clap_plugin_factory_t*,const clap_host_t* host,const char* id){if(!host||!id||std::strcmp(id,descriptor.id))return nullptr;
 auto* s=new(std::nothrow)Plugin(host);if(!s)return nullptr;s->clap={&descriptor,s,init,destroy,activate,deactivate,start,stop,reset,process,extension,main_thread};return &s->clap;}
const clap_plugin_factory_t factory{factory_count,factory_descriptor,factory_create};
bool CLAP_ABI entry_init(const char*){return true;}void CLAP_ABI entry_deinit(){}const void* CLAP_ABI get_factory(const char* id){return id&&!std::strcmp(id,CLAP_PLUGIN_FACTORY_ID)?&factory:nullptr;}
}
extern "C" CLAP_EXPORT const clap_plugin_entry_t clap_entry{CLAP_VERSION_INIT,entry_init,entry_deinit,get_factory};
