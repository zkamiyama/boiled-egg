// Actual CLAP ABI: restart requests and latency notifications are distinct.
#include "pitch_controls.hpp"
#include <clap/clap.h>
#include <dlfcn.h>
#include <array>
#include <cstring>
#include <iostream>
#include <stdexcept>
namespace bp=boiled_egg::plugin;
static void check(bool b,const char* m){if(!b)throw std::runtime_error(m);}
struct Host {
 bool activating{},offer_latency{true},wrong_context{};unsigned changes{},restarts{},callbacks{},last_latency{};
 const clap_plugin_t* plugin{};
 clap_host_t api{CLAP_VERSION,this,"C2 lifecycle","boiled egg","","1",extension,
  [](const clap_host_t* h){++get(h).restarts;},[](const clap_host_t*){},[](const clap_host_t* h){++get(h).callbacks;}};
 static Host& get(const clap_host_t* h){return *static_cast<Host*>(h->host_data);}
 static const void* extension(const clap_host_t* h,const char* id){
  static const clap_host_latency_t latency{[](const clap_host_t* h){auto& s=get(h);++s.changes;
   if(!s.activating||!s.plugin){s.wrong_context=true;return;}
   auto* p=static_cast<const clap_plugin_latency_t*>(s.plugin->get_extension(s.plugin,CLAP_EXT_LATENCY));
   if(!p){s.wrong_context=true;return;}s.last_latency=p->get(s.plugin);}};
  if(!std::strcmp(id,CLAP_EXT_LATENCY)&&get(h).offer_latency)return &latency;return nullptr;
 }
 bool activate(double rate,unsigned maximum){activating=true;bool ok=plugin->activate(plugin,rate,1,maximum);activating=false;return ok;}
};
struct Input {
 std::array<clap_event_param_value_t,3> values{};unsigned count{};
 clap_input_events_t api{this,[](const clap_input_events_t* s){return static_cast<Input*>(s->ctx)->count;},
  [](const clap_input_events_t* s,uint32_t i)->const clap_event_header_t*{auto& v=*static_cast<Input*>(s->ctx);return i<v.count?&v.values[i].header:nullptr;}};
 void add(unsigned index,float value){auto& e=values[count++];e.header={sizeof(e),0,CLAP_CORE_EVENT_SPACE_ID,CLAP_EVENT_PARAM_VALUE,0};
  e.param_id=bp::clap_param_id(index);e.value=value;e.note_id=-1;e.port_index=e.channel=e.key=-1;}
};
int main(int argc,char** argv){try{
 check(argc==2,"module path");void* lib=dlopen(argv[1],RTLD_NOW|RTLD_LOCAL);check(lib,"dlopen");
 auto* entry=static_cast<const clap_plugin_entry_t*>(dlsym(lib,"clap_entry"));check(entry&&entry->init(argv[1]),"entry");
 auto* factory=static_cast<const clap_plugin_factory_t*>(entry->get_factory(CLAP_PLUGIN_FACTORY_ID));check(factory,"factory");
 const auto* desc=factory->get_plugin_descriptor(factory,0);check(desc,"descriptor");unsigned cases=0;
 for(unsigned rate:{44100u,48000u,88200u,96000u})for(bool spectral:{false,true}){
  if(spectral&&!bp::spectral_available())continue;Host host;host.plugin=factory->create_plugin(factory,&host.api,desc->id);
  const auto* p=host.plugin;check(p&&p->init(p),"init");
  auto* params=static_cast<const clap_plugin_params_t*>(p->get_extension(p,CLAP_EXT_PARAMS));
  auto* latency=static_cast<const clap_plugin_latency_t*>(p->get_extension(p,CLAP_EXT_LATENCY));check(params&&latency,"extensions");
  if(spectral){Input config;config.add(bp::Backend,1);params->flush(p,&config.api,nullptr);}
  check(host.changes==0&&host.activate(rate,64),"initial activate");
  check(host.changes==1&&!host.wrong_context&&host.last_latency==latency->get(p),"initial latency notification");
  const auto first=latency->get(p);check(p->start_processing(p),"start");
  Input quality;quality.add(bp::Quality,1);params->flush(p,&quality.api,nullptr);
  check(host.changes==1&&latency->get(p)==first,"pending request changed active latency");
  check(host.callbacks>0,"main callback request");p->on_main_thread(p);check(host.restarts>0,"restart request");
  p->stop_processing(p);p->deactivate(p);check(host.activate(rate,64),"reactivate");
  check(host.changes==2&&!host.wrong_context&&host.last_latency==latency->get(p)&&host.last_latency!=first,"reactivated latency notification");
  p->deactivate(p);check(host.activate(rate,64)&&host.changes==2,"unchanged latency should not renotify");p->deactivate(p);
  check(!host.activate(rate,0)&&host.changes==2&&!host.wrong_context,"failed activation must not notify");
  p->destroy(p);++cases;
 }
 Host absent;absent.offer_latency=false;absent.plugin=factory->create_plugin(factory,&absent.api,desc->id);
 check(absent.plugin&&absent.plugin->init(absent.plugin)&&absent.activate(48000,64),"optional extension absent");
 check(absent.changes==0,"absent callback");absent.plugin->deactivate(absent.plugin);absent.plugin->destroy(absent.plugin);
 entry->deinit();dlclose(lib);std::cout<<cases<<" actual CLAP activation/restart/latency cases plus absent optional extension\n";
}catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}}
