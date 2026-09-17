// A CLAP host may send live changes even when a parameter is not automatable.
// Compare actual module processing with a separately controlled active processor.
#include "pitch_processor.hpp"
#include "test_allocations.hpp"
#include <clap/clap.h>
#include <dlfcn.h>
#include <algorithm>
#include <array>
#include <bit>
#include <cmath>
#include <cstring>
#include <iostream>
#include <stdexcept>
namespace bp=boiled_egg::plugin;
static void check(bool ok,const char* reason){if(!ok)throw std::runtime_error(reason);}
struct Host {
 unsigned callbacks{},restarts{},changes{};bool activating{},bad_context{};
 clap_host_t api{CLAP_VERSION,this,"C2 live controls","boiled egg","","1",extension,
  [](const clap_host_t* h){++get(h).restarts;},[](const clap_host_t*){},
  [](const clap_host_t* h){++get(h).callbacks;}};
 static Host& get(const clap_host_t* h){return *static_cast<Host*>(h->host_data);}
 static const void* extension(const clap_host_t*,const char* id){
  static const clap_host_latency_t latency{[](const clap_host_t* h){auto& s=get(h);++s.changes;if(!s.activating)s.bad_context=true;}};
  return !std::strcmp(id,CLAP_EXT_LATENCY)?&latency:nullptr;
 }
 bool activate(const clap_plugin_t* p,unsigned rate,unsigned block){activating=true;const bool ok=p->activate(p,rate,1,block);activating=false;return ok;}
};
struct Events {
 std::array<clap_event_param_value_t,16> data{};unsigned count{};
 clap_input_events_t api{this,[](const clap_input_events_t* p){return static_cast<Events*>(p->ctx)->count;},
  [](const clap_input_events_t* p,uint32_t i)->const clap_event_header_t*{
   auto& s=*static_cast<Events*>(p->ctx);return i<s.count?&s.data[i].header:nullptr;}};
 void add(unsigned at,unsigned index,float value){check(count<data.size(),"test event capacity");auto& e=data[count++];
  e.header={sizeof(e),at,CLAP_CORE_EVENT_SPACE_ID,CLAP_EVENT_PARAM_VALUE,CLAP_EVENT_IS_LIVE};
  e.param_id=bp::clap_param_id(index);e.value=value;e.note_id=-1;e.port_index=e.channel=e.key=-1;}
};
struct State {
 std::array<std::uint8_t,bp::state_size> bytes{};unsigned pos{};
 clap_ostream_t output{this,[](const clap_ostream_t* o,const void* p,uint64_t n)->int64_t{
  auto& s=*static_cast<State*>(o->ctx);n=std::min<uint64_t>(n,s.bytes.size()-s.pos);if(!n)return -1;
  std::memcpy(s.bytes.data()+s.pos,p,n);s.pos+=unsigned(n);return int64_t(n);}};
};
struct Audio {
 std::array<float,257> l{},r{},a{},b{};unsigned position{};
 void fill(unsigned n){for(unsigned i=0;i<n;++i){l[i]=.1f*std::sin(float(position+i)*.071f);r[i]=-.375f*l[i];}position+=n;}
 void run(const clap_plugin_t* p,bp::Processor& reference,unsigned n,Events& ev,
          std::span<const bp::Event> expected={},bool invalid=false){
  fill(n);const float* input[]={l.data(),r.data()};float* expected_out[]={a.data(),b.data()};
  if(!invalid)check(reference.process(input,expected_out,n,expected),"reference processing");
  float* in[]={l.data(),r.data()};float* out[]={l.data(),r.data()};const auto before_l=l,before_r=r;
  clap_audio_buffer_t ib{in,nullptr,2,0,0},ob{out,nullptr,2,0,0};
  clap_process_t d{};d.frames_count=n;d.audio_inputs=&ib;d.audio_outputs=&ob;
  d.audio_inputs_count=d.audio_outputs_count=1;d.in_events=&ev.api;
  counting_allocations=true;const auto status=p->process(p,&d);counting_allocations=false;
  if(invalid){check(status==CLAP_PROCESS_ERROR,"invalid joint request accepted");check(l==before_l&&r==before_r,"invalid batch changed audio");}
  else {check(status!=CLAP_PROCESS_ERROR,"valid live configuration rejected by process");
   check(std::equal(l.begin(),l.begin()+n,a.begin())&&std::equal(r.begin(),r.begin()+n,b.begin()),"active processing changed before restart");}
 }
};
int main(int argc,char** argv){try{
 check(argc>=2,"module path required");const bool metadata=argc>2;
 void* lib=dlopen(argv[1],RTLD_NOW|RTLD_LOCAL);check(lib,"dlopen");
 auto* entry=static_cast<const clap_plugin_entry_t*>(dlsym(lib,"clap_entry"));check(entry&&entry->init(argv[1]),"entry");
 auto* factory=static_cast<const clap_plugin_factory_t*>(entry->get_factory(CLAP_PLUGIN_FACTORY_ID));check(factory,"factory");
 const auto* desc=factory->get_plugin_descriptor(factory,0);check(desc,"descriptor");unsigned cases=0;
 for(unsigned rate:{44100u,48000u,88200u,96000u})for(unsigned block:{32u,257u})for(bool pv:{false,true}){
  if(pv&&!bp::spectral_available())continue;Host host;auto* p=factory->create_plugin(factory,&host.api,desc->id);check(p&&p->init(p),"init");
  auto* params=static_cast<const clap_plugin_params_t*>(p->get_extension(p,CLAP_EXT_PARAMS));
  auto* latency=static_cast<const clap_plugin_latency_t*>(p->get_extension(p,CLAP_EXT_LATENCY));
  auto* state=static_cast<const clap_plugin_state_t*>(p->get_extension(p,CLAP_EXT_STATE));check(params&&latency&&state,"extensions");
  if(metadata){unsigned bypass_count=0;for(unsigned i=0;i<params->count(p);++i){clap_param_info_t info{};check(params->get_info(p,i,&info),"param info");
    if(info.flags&CLAP_PARAM_IS_BYPASS){++bypass_count;check(info.id==bp::clap_param_id(bp::Bypass)&&info.min_value==0&&info.max_value==1&&(info.flags&CLAP_PARAM_IS_STEPPED),"bypass metadata");}
    if(i>=bp::Backend)check((info.flags&CLAP_PARAM_IS_ENUM)&&!(info.flags&CLAP_PARAM_IS_AUTOMATABLE),"configuration flags");}
   check(bypass_count==1,"standard bypass flag missing");p->destroy(p);++cases;continue;}
  auto values=bp::defaults();if(pv){values[bp::Backend]=1;Events init;init.add(0,bp::Backend,1);params->flush(p,&init.api,nullptr);}
  bp::Processor reference;check(reference.request(values)&&reference.activate(rate,block),"reference activate");
  check(host.activate(p,rate,block)&&p->start_processing(p),"activate");const auto old_latency=latency->get(p);
  Audio audio;Events empty;for(unsigned i=0;i<old_latency/block+2;++i)audio.run(p,reference,block,empty);
  Events quality;quality.add(1,bp::Quality,1);audio.run(p,reference,block,quality);
  double current{};check(params->get_value(p,bp::clap_param_id(bp::Quality),&current)&&current==1,"pending quality invisible");
  check(latency->get(p)==old_latency&&host.callbacks>0&&host.changes==1&&!host.bad_context,"premature latency notification");
  p->on_main_thread(p);check(host.restarts>0,"restart was not requested");
  State before;check(state->save(p,&before.output),"pending state save");const auto cb=host.callbacks;
  Events bad;bad.add(0,bp::Quality,0);bad.add(block-1,bp::Pitch,25);audio.run(p,reference,block,bad,{},true);
  State after;check(state->save(p,&after.output)&&before.bytes==after.bytes&&cb==host.callbacks,"invalid batch mutated targets/restart");
  audio.run(p,reference,block,empty); // Invalid call did not advance DSP history.
  Events pitch;pitch.add(0,bp::Pitch,7);audio.run(p,reference,block,pitch);
  check(params->get_value(p,bp::clap_param_id(bp::Pitch),&current)&&current==7,"pending pitch lost");
  Events cancel;cancel.add(0,bp::Quality,0);cancel.add(block-1,bp::Fine,20);
  const std::array<bp::Event,2> resume{{{0,bp::Pitch,7},{block-1,bp::Fine,20}}};
  audio.run(p,reference,block,cancel,resume);const auto restarts=host.restarts;p->on_main_thread(p);
  check(host.restarts==restarts,"cancelled configuration still requests restart");
  Events joint;joint.add(0,bp::Quality,1);values[bp::Quality]=1;values[bp::Pitch]=7;values[bp::Fine]=20;
  if(bp::spectral_available()){joint.add(0,bp::Formant,3);joint.add(0,bp::Policy,1);joint.add(0,bp::Backend,1);
   values[bp::Formant]=3;values[bp::Policy]=1;values[bp::Backend]=1;}
  audio.run(p,reference,block,joint);State pending;check(state->save(p,&pending.output)&&pending.bytes==bp::encode(values),"joint pending state differs");
  check(latency->get(p)==old_latency,"pending configuration changed latency");p->on_main_thread(p);
  p->stop_processing(p);p->deactivate(p);check(host.activate(p,rate,block)&&p->start_processing(p),"reactivation");
  check(latency->get(p)!=old_latency&&host.changes==2&&!host.bad_context,"reactivation delay notification");
  bp::Processor activated;check(activated.request(values)&&activated.activate(rate,block),"fresh expected activate");
  for(unsigned i=0;i<latency->get(p)/block+3;++i)audio.run(p,activated,block,empty);
  p->stop_processing(p);p->deactivate(p);p->destroy(p);++cases;
 }
 check(allocation_count.load()==0,"live configuration allocated in process");entry->deinit();dlclose(lib);
 std::cout<<cases<<(metadata?" CLAP bypass/enum metadata cases":" CLAP live-edit cases: staged controls, cancellation, atomic rejection, restart and exact active output; zero process allocations")<<'\n';
}catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}}
