// One standalone host probe; no boiled-egg header, library or shared Processor.
#include <clap/clap.h>
#include <dlfcn.h>
#include <algorithm>
#include <array>
#include <bit>
#include <cmath>
#include <cstdint>
#include <cstring>
#include <iostream>
#include <stdexcept>
#include <vector>
static constexpr clap_id pitch_id=0x42450001;
static void require(bool v,const char* why){if(!v)throw std::runtime_error(why);}
struct Events {
 std::array<clap_event_param_value_t,3> events{};unsigned count{};
 clap_input_events_t api{this,[](const clap_input_events_t* p){return static_cast<Events*>(p->ctx)->count;},
  [](const clap_input_events_t* p,uint32_t i)->const clap_event_header_t*{auto& s=*static_cast<Events*>(p->ctx);return i<s.count?&s.events[i].header:nullptr;}};
 void add(unsigned offset,double value){auto& e=events[count++];e.header={sizeof(e),offset,CLAP_CORE_EVENT_SPACE_ID,CLAP_EVENT_PARAM_VALUE,0};
  e.param_id=pitch_id;e.value=value;e.note_id=-1;e.port_index=e.channel=e.key=-1;}
};
struct LegacyState {
 std::array<std::uint32_t,4> words;std::size_t offset{};
 explicit LegacyState(float pitch):words{0x42454747,1,std::bit_cast<std::uint32_t>(pitch),0}{}
 clap_istream_t api{this,[](const clap_istream_t* p,void* dst,uint64_t cap)->int64_t{
  auto& s=*static_cast<LegacyState*>(p->ctx);auto n=std::min<std::size_t>({std::size_t(cap),3,sizeof(s.words)-s.offset});
  std::memcpy(dst,reinterpret_cast<const char*>(s.words.data())+s.offset,n);s.offset+=n;return n;}};
};
int main(int argc,char** argv){try{
 require(argc==2,"module path required");auto* module=dlopen(argv[1],RTLD_NOW|RTLD_LOCAL);require(module,"dlopen");
 auto* entry=static_cast<const clap_plugin_entry_t*>(dlsym(module,"clap_entry"));require(entry&&entry->init(argv[1]),"entry");
 auto* factory=static_cast<const clap_plugin_factory_t*>(entry->get_factory(CLAP_PLUGIN_FACTORY_ID));require(factory&&factory->get_plugin_count(factory)==1,"factory");
 const auto* desc=factory->get_plugin_descriptor(factory,0);require(desc&&!std::strcmp(desc->id,"io.github.zkamiyama.boiled-egg"),"legacy plugin ID");
 clap_host_t host{CLAP_VERSION,nullptr,"Legacy C2 probe","boiled egg","","1",
  [](const clap_host_t*,const char*)->const void*{return nullptr;},[](const clap_host_t*){},[](const clap_host_t*){},[](const clap_host_t*){}};
 std::cout<<"rate,block,pitch,scenario,frames,latency,tail,last_pitch,audio_hash\n";
 for(unsigned rate:{44100U,48000U,88200U,96000U})for(unsigned block:{32U,257U})for(float pitch:{-12.F,0.F,12.F})for(unsigned scenario:{0U,1U}){
  const auto* p=factory->create_plugin(factory,&host,desc->id);require(p&&p->init(p),"plugin init");
  auto* params=static_cast<const clap_plugin_params_t*>(p->get_extension(p,CLAP_EXT_PARAMS));
  auto* state=static_cast<const clap_plugin_state_t*>(p->get_extension(p,CLAP_EXT_STATE));
  auto* latency=static_cast<const clap_plugin_latency_t*>(p->get_extension(p,CLAP_EXT_LATENCY));
  auto* tail=static_cast<const clap_plugin_tail_t*>(p->get_extension(p,CLAP_EXT_TAIL));require(params&&state&&latency&&tail,"extensions");
  clap_param_info_t info{};require(params->get_info(p,0,&info)&&info.id==pitch_id&&info.min_value==-24&&info.max_value==24,"legacy pitch contract");
  LegacyState saved(pitch);require(state->load(p,&saved.api),"old state load");
  require(p->activate(p,rate,1,257)&&p->start_processing(p),"activation");auto L=latency->get(p);auto T=tail->get(p);require(L>0,"latency");
  const unsigned frames=24001+L;std::array<std::vector<float>,2>x{std::vector<float>(frames),std::vector<float>(frames)};
  unsigned rng=260917;
  for(unsigned i=0;i<24001;++i){rng=1664525U*rng+1013904223U;const double time=double(i)/rate;
   x[0][i]=float(.1*std::sin(6.283185307179586*173*time)+.02*(double(rng>>8)/16777216.-.5));x[1][i]=-.375F*x[0][i];}
  std::array<float,257>a{},b{};float* output[]{a.data(),b.data()};uint64_t hash=1469598103934665603ULL;
  for(unsigned pos=0;pos<frames;){unsigned n=std::min(block,frames-pos);float* input[]{x[0].data()+pos,x[1].data()+pos};Events ev;
   if(scenario)for(auto [at,value]:std::array<std::pair<unsigned,double>,3>{{{777,7},{4101,-5},{12289,0}}})if(at>=pos&&at<pos+n)ev.add(at-pos,value);
   clap_audio_buffer_t in{input,nullptr,2,0,0},out{output,nullptr,2,0,0};clap_process_t process{};
   process.steady_time=pos;process.frames_count=n;process.audio_inputs=&in;process.audio_outputs=&out;
   process.audio_inputs_count=process.audio_outputs_count=1;process.in_events=&ev.api;
   require(p->process(p,&process)!=CLAP_PROCESS_ERROR,"processing");
   for(unsigned i=0;i<n;++i)for(unsigned ch=0;ch<2;++ch){float v=output[ch][i];require(std::isfinite(v),"nonfinite");if(pos+i<L)require(v==0,"declared startup");
    hash^=std::bit_cast<std::uint32_t>(v);hash*=1099511628211ULL;}pos+=n;
  }
  double last{};require(params->get_value(p,pitch_id,&last),"last pitch");require(last==(scenario?0:double(pitch)),"event state");
  require(latency->get(p)==L&&tail->get(p)==T,"fixed contract");
  std::cout<<rate<<','<<block<<','<<pitch<<','<<scenario<<','<<frames<<','<<L<<','<<T<<','<<last<<','<<hash<<'\n';
  p->stop_processing(p);p->deactivate(p);p->destroy(p);
 }
 entry->deinit();dlclose(module);
}catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}}
