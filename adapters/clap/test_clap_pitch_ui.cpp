#include "pitch_processor.hpp"
#include "pitch_editor.hpp"
#include "test_allocations.hpp"
#include <clap/clap.h>
#include <dlfcn.h>
#include <algorithm>
#include <array>
#include <cmath>
#include <cstring>
#include <fstream>
#include <iostream>
#include <stdexcept>
#include <vector>
#ifdef BOILED_EGG_PLUGIN_X11
#include <X11/Xutil.h>
#include <X11/keysym.h>
#endif
namespace bp=boiled_egg::plugin;
static void require(bool v,const char* s){if(!v)throw std::runtime_error(s);}
struct Host {
 unsigned flushes{},callbacks{},restarts{},rescans{},registered{};
 clap_host_t api{CLAP_VERSION,this,"boiled egg integration test","zkamiyama","","1",extensions,
     [](const clap_host_t* h){++self(h).restarts;},[](const clap_host_t*){},[](const clap_host_t* h){++self(h).callbacks;}};
 static Host& self(const clap_host_t* h){return *static_cast<Host*>(h->host_data);}
 static const void* CLAP_ABI extensions(const clap_host_t*,const char* id){
     static const clap_host_params_t params{[](const clap_host_t* h,clap_param_rescan_flags){++self(h).rescans;},
         [](const clap_host_t*,clap_id,clap_param_clear_flags){},[](const clap_host_t* h){++self(h).flushes;}};
     static const clap_host_timer_support_t timer{[](const clap_host_t* h,uint32_t ms,clap_id* id){if(ms<1||!id)return false;*id=7;++self(h).registered;return true;},
         [](const clap_host_t* h,clap_id id){if(id!=7||!self(h).registered)return false;--self(h).registered;return true;}};
     if(!std::strcmp(id,CLAP_EXT_PARAMS))return &params;if(!std::strcmp(id,CLAP_EXT_TIMER_SUPPORT))return &timer;return nullptr;
 }
};
struct Events {
 std::array<clap_event_param_value_t,257> values{};unsigned count{};
 clap_input_events_t api{this,[](const clap_input_events_t* s){return static_cast<Events*>(s->ctx)->count;},
     [](const clap_input_events_t* s,uint32_t n)->const clap_event_header_t*{const auto* self=static_cast<Events*>(s->ctx);return n<self->count?&self->values[n].header:nullptr;}};
 void add(unsigned offset,unsigned index,float value){require(count<values.size(),"fixture event overflow");auto& v=values[count++];v={};
     v.header={sizeof(v),offset,CLAP_CORE_EVENT_SPACE_ID,CLAP_EVENT_PARAM_VALUE,0};v.param_id=bp::clap_param_id(index);v.value=value;v.note_id=-1;v.port_index=v.channel=v.key=-1;}
};
struct OutputEvents {
 std::array<std::uint16_t,1024> types{};unsigned count{};
 clap_output_events_t api{this,[](const clap_output_events_t* out,const clap_event_header_t* e){auto& self=*static_cast<OutputEvents*>(out->ctx);if(!e||self.count==self.types.size())return false;self.types[self.count++]=e->type;return true;}};
};
struct State {
 std::array<std::uint8_t,bp::state_size> bytes{};unsigned size=bp::state_size,position{};
 clap_istream_t in{this,[](const clap_istream_t* s,void* d,uint64_t n)->int64_t{auto& x=*static_cast<State*>(s->ctx);n=std::min<std::uint64_t>({n,x.size-x.position,3});std::memcpy(d,x.bytes.data()+x.position,n);x.position+=unsigned(n);return int64_t(n);}};
 clap_ostream_t out{this,[](const clap_ostream_t* s,const void* d,uint64_t n)->int64_t{auto& x=*static_cast<State*>(s->ctx);n=std::min<std::uint64_t>({n,x.size-x.position,3});std::memcpy(x.bytes.data()+x.position,d,n);x.position+=unsigned(n);return int64_t(n);}};
};
#ifdef BOILED_EGG_PLUGIN_X11
static void click(Display* d,Window w,int x,int y,unsigned button=1){
 for(int type:{ButtonPress,ButtonRelease}){XEvent e{};e.xbutton.type=type;e.xbutton.display=d;e.xbutton.window=w;e.xbutton.root=DefaultRootWindow(d);e.xbutton.x=x;e.xbutton.y=y;e.xbutton.button=button;e.xbutton.same_screen=True;
     XSendEvent(d,w,False,type==ButtonPress?ButtonPressMask:ButtonReleaseMask,&e);}XSync(d,False);
}
static void key(Display* d,Window w,KeySym sym,unsigned mods=0){XEvent e{};e.xkey.type=KeyPress;e.xkey.display=d;e.xkey.window=w;e.xkey.root=DefaultRootWindow(d);e.xkey.keycode=XKeysymToKeycode(d,sym);e.xkey.state=mods;e.xkey.same_screen=True;XSendEvent(d,w,False,KeyPressMask,&e);XSync(d,False);}
static void capture(Display* d,Window w,const char* path){if(!path)return;XSync(d,False);XWindowAttributes a{};require(XGetWindowAttributes(d,w,&a),"capture geometry");auto* image=XGetImage(d,w,0,0,unsigned(a.width),unsigned(a.height),AllPlanes,ZPixmap);require(image,"capture pixels");
 std::ofstream out(path,std::ios::binary);out<<"P6\n"<<a.width<<' '<<a.height<<"\n255\n";
 auto channel=[](unsigned long pixel,unsigned long mask){unsigned shift=0;while(mask&&!(mask&1)){mask>>=1;++shift;}return mask?static_cast<unsigned char>((pixel>>shift&mask)*255/mask):0;};
 for(int y=0;y<a.height;++y)for(int x=0;x<a.width;++x){auto p=XGetPixel(image,x,y);char b[]={char(channel(p,image->red_mask)),char(channel(p,image->green_mask)),char(channel(p,image->blue_mask))};out.write(b,3);}XDestroyImage(image);require(bool(out),"screenshot write");
}
#endif
int main(int argc,char** argv){try{
 require(argc>=2,"plugin path required");const bool ui=argc>=3;
 void* library=dlopen(argv[1],RTLD_NOW|RTLD_LOCAL);require(library,"dlopen");auto* entry=static_cast<const clap_plugin_entry_t*>(dlsym(library,"clap_entry"));require(entry&&entry->init(argv[1]),"entry");
 auto* factory=static_cast<const clap_plugin_factory_t*>(entry->get_factory(CLAP_PLUGIN_FACTORY_ID));require(factory,"factory");const auto* descriptor=factory->get_plugin_descriptor(factory,0);require(descriptor&&!std::strcmp(descriptor->id,"io.github.zkamiyama.boiled-egg"),"legacy identity");
 Host host;unsigned cases=0;
 for(unsigned rate:{44100u,48000u,88200u,96000u})for(unsigned block:{32u,257u})for(unsigned policy:{0u,1u,2u,3u}){
     const bool pv=policy!=3;if(pv&&!bp::spectral_available())continue;
     auto* plugin=factory->create_plugin(factory,&host.api,descriptor->id);require(plugin&&plugin->init(plugin),"plugin init");
     auto* params=static_cast<const clap_plugin_params_t*>(plugin->get_extension(plugin,CLAP_EXT_PARAMS));auto* state=static_cast<const clap_plugin_state_t*>(plugin->get_extension(plugin,CLAP_EXT_STATE));auto* delay=static_cast<const clap_plugin_latency_t*>(plugin->get_extension(plugin,CLAP_EXT_LATENCY));
     require(params&&state&&delay&&params->count(plugin)==bp::Count,"new params");clap_param_info_t info{};require(params->get_info(plugin,0,&info)&&info.id==0x42450001u&&info.min_value==-24&&info.max_value==24,"old Pitch ID/range");
     State old;old.size=16;bp::write_word(old.bytes.data(),bp::state_magic);bp::write_word(old.bytes.data()+4,1);bp::write_word(old.bytes.data()+8,std::bit_cast<unsigned>(-7.f));require(state->load(plugin,&old.in),"legacy state load");double value{};require(params->get_value(plugin,bp::clap_param_id(bp::Pitch),&value)&&value==-7,"legacy pitch state");
     auto initial=bp::defaults();initial[bp::Backend]=pv?1:0;initial[bp::Quality]=1;initial[bp::Policy]=pv?float(policy):0;initial[bp::Pitch]=-3;
     State fresh;fresh.bytes=bp::encode(initial);require(state->load(plugin,&fresh.in),"v2 state load");State saved;require(state->save(plugin,&saved.out)&&saved.bytes==fresh.bytes,"v2 roundtrip partial IO");
     State bad;bad.bytes=fresh.bytes;bad.bytes[4]=99;require(!state->load(plugin,&bad.in),"unknown state version");
     require(plugin->activate(plugin,rate,1,block)&&plugin->start_processing(plugin),"activate");const auto L=delay->get(plugin);
     bp::Processor reference;require(reference.request(initial)&&reference.activate(rate,block)&&reference.latency()==L,"reference and host delay");
     const std::array<bp::Event,12> schedule{{{799,bp::Pitch,-7},{799,bp::Fine,23},{1931,bp::Formant,pv&&policy?3.f:0.f},{2137,bp::Wet,.78f},
         {2137,bp::Dry,.13f},{4111,bp::Pitch,7},{4519,bp::Pan,-.31f},{6709,bp::Volume,-3},{7919,bp::FormantFine,pv&&policy?-13.f:0.f},
         {11003,bp::Bypass,1},{13001,bp::Bypass,0},{15701,bp::Pitch,0}}};
     std::array<std::vector<float>,2> input{std::vector<float>(block),std::vector<float>(block)},result=input,expected=input;
     for(unsigned pos=0;pos<19013+L;pos+=block){const auto n=std::min(block,19013+L-pos);Events events;std::array<bp::Event,256> re{};unsigned count=0;
         for(auto e:schedule)if(e.offset>=pos&&e.offset<pos+n){e.offset-=pos;events.add(e.offset,e.index,e.value);re[count++]=e;}
         for(unsigned i=0;i<n;++i){input[0][i]=.13f*std::sin(float(pos+i)*.0371f)+.07f*std::cos(float(pos+i)*.1231f);input[1][i]=-.5f*input[0][i];}
         const float* ri[]={input[0].data(),input[1].data()};float* ro[]={expected[0].data(),expected[1].data()};require(reference.process(ri,ro,n,{re.data(),count}),"reference events");
         float* in[]={input[0].data(),input[1].data()};float* out[]={input[0].data(),input[1].data()};clap_audio_buffer_t a{in,nullptr,2,0,0},b{out,nullptr,2,0,0};
         clap_process_t data{};data.frames_count=n;data.audio_inputs=&a;data.audio_outputs=&b;data.audio_inputs_count=data.audio_outputs_count=1;data.in_events=&events.api;
         counting_allocations=true;auto status=plugin->process(plugin,&data);counting_allocations=false;require(status!=CLAP_PROCESS_ERROR,"CLAP dynamic processing");
         for(unsigned ch=0;ch<2;++ch)require(std::equal(out[ch],out[ch]+n,expected[ch].begin()),"loaded CLAP differs from product bridge");require(delay->get(plugin)==L,"dynamic latency changed");
     }
     Events invalid;invalid.add(0,bp::Pitch,3);invalid.add(block,bp::Pitch,4);float* out[]={result[0].data(),result[1].data()};float* in[]={input[0].data(),input[1].data()};clap_audio_buffer_t a{in,nullptr,2,0,0},b{out,nullptr,2,0,0};clap_process_t d{};d.frames_count=block;d.audio_inputs=&a;d.audio_outputs=&b;d.audio_inputs_count=d.audio_outputs_count=1;d.in_events=&invalid.api;
     for(auto& ch:result)std::fill(ch.begin(),ch.end(),123.f);params->get_value(plugin,bp::clap_param_id(bp::Pitch),&value);const auto prior=value;
     require(plugin->process(plugin,&d)==CLAP_PROCESS_ERROR,"invalid offset accepted");params->get_value(plugin,bp::clap_param_id(bp::Pitch),&value);require(prior==value,"invalid batch changed target");for(auto& ch:result)for(float v:ch)require(v==123,"invalid batch changed output");
     plugin->stop_processing(plugin);plugin->deactivate(plugin);plugin->destroy(plugin);++cases;
 }
 require(allocation_count.load()==0,"plugin process allocated");
#ifdef BOILED_EGG_PLUGIN_X11
 if(ui){auto* plugin=factory->create_plugin(factory,&host.api,descriptor->id);require(plugin&&plugin->init(plugin),"GUI plugin");auto* gui=static_cast<const clap_plugin_gui_t*>(plugin->get_extension(plugin,CLAP_EXT_GUI));auto* timers=static_cast<const clap_plugin_timer_support_t*>(plugin->get_extension(plugin,CLAP_EXT_TIMER_SUPPORT));auto* params=static_cast<const clap_plugin_params_t*>(plugin->get_extension(plugin,CLAP_EXT_PARAMS));auto* state=static_cast<const clap_plugin_state_t*>(plugin->get_extension(plugin,CLAP_EXT_STATE));
     auto initial=bp::defaults();if(bp::spectral_available()){initial[bp::Backend]=1;initial[bp::Quality]=1;initial[bp::Policy]=1;initial[bp::Formant]=3;}initial[bp::Pitch]=-7;initial[bp::Fine]=23;initial[bp::Wet]=.75f;initial[bp::Dry]=.25f;initial[bp::Volume]=-3;
     State data;data.bytes=bp::encode(initial);require(state->load(plugin,&data.in)&&plugin->activate(plugin,48000,1,64),"GUI state activation");
     require(gui&&timers&&gui->is_api_supported(plugin,CLAP_WINDOW_API_X11,false)&&!gui->is_api_supported(plugin,CLAP_WINDOW_API_X11,true),"GUI supported embed");
     Display* display=XOpenDisplay(nullptr);require(display,"DISPLAY needed for GUI test");Window parent=XCreateSimpleWindow(display,DefaultRootWindow(display),10,10,900,640,0,0,0);XMapWindow(display,parent);XSync(display,False);
     require(gui->create(plugin,CLAP_WINDOW_API_X11,false),"GUI create");clap_window_t window{};window.api=CLAP_WINDOW_API_X11;window.x11=parent;require(gui->set_parent(plugin,&window)&&gui->show(plugin),"GUI attached");
     for(unsigned i=0;i<8;++i){timers->on_timer(plugin,7);XSync(display,False);}Window root{},returned{};Window* children=nullptr;unsigned child_count=0;require(XQueryTree(display,parent,&root,&returned,&children,&child_count)&&child_count==1,"XEmbed child");const Window child=children[0];XFree(children);
     capture(display,child,argc>3?argv[3]:nullptr);
     click(display,child,789,176);timers->on_timer(plugin,7);key(display,child,XK_a,ControlMask);for(auto sym:{XK_minus,XK_5,XK_period,XK_5,XK_Return})key(display,child,KeySym(sym));
     for(unsigned i=0;i<8;++i){timers->on_timer(plugin,7);XSync(display,False);}double value=0;require(params->get_value(plugin,bp::clap_param_id(bp::Pitch),&value)&&value==-5.5,"numeric UI edit");
     OutputEvents output;params->flush(plugin,nullptr,&output.api);require(output.count>=3&&output.types[0]==CLAP_EVENT_PARAM_GESTURE_BEGIN&&output.types[output.count-1]==CLAP_EVENT_PARAM_GESTURE_END,"UI gesture routing");require(host.flushes>0,"host flush request");
     click(display,child,64,323);for(unsigned i=0;i<8;++i){timers->on_timer(plugin,7);XSync(display,False);}params->get_value(plugin,bp::clap_param_id(bp::Wet),&value);require(std::abs(value-.5)<.01,"wet slider interaction");
     uint32_t w=1,h=1;require(gui->adjust_size(plugin,&w,&h)&&w==760&&h==560,"size constraints");require(gui->set_size(plugin,1125,800),"GUI resize");require(gui->get_size(plugin,&w,&h)&&w==1125&&h==800,"GUI size report");
     require(gui->hide(plugin)&&gui->show(plugin),"GUI visibility");gui->destroy(plugin);require(host.registered==0,"GUI timer leaked");XDestroyWindow(display,parent);XCloseDisplay(display);plugin->deactivate(plugin);plugin->destroy(plugin);
     std::cout<<"CLAP XEmbed editor: numeric entry, sliders, resize, gestures and timer lifetime passed\n";
 }
#else
 require(!ui,"UI was disabled in this build");
#endif
 entry->deinit();dlclose(library);std::cout<<cases<<" loaded CLAP dynamic/state/in-place cases, zero process allocations\n";
}catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}}
