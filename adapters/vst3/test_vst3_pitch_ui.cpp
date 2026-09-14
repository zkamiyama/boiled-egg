#include "pitch_processor.hpp"
#include "test_allocations.hpp"
#include "base/source/fobject.h"
#include "public.sdk/source/vst/hosting/module.h"
#include "public.sdk/source/vst/hosting/hostclasses.h"
#include "public.sdk/source/vst/hosting/parameterchanges.h"
#include "public.sdk/source/common/memorystream.h"
#include "pluginterfaces/vst/ivstaudioprocessor.h"
#include "pluginterfaces/vst/ivsteditcontroller.h"
#include "pluginterfaces/gui/iplugview.h"
#include "pluginterfaces/base/keycodes.h"
#include <algorithm>
#include <cmath>
#include <iostream>
#include <stdexcept>
#include <vector>
#ifdef BOILED_EGG_PLUGIN_X11
#include <X11/Xlib.h>
#endif
namespace bp=boiled_egg::plugin;
using namespace Steinberg;using namespace Steinberg::Vst;
static void require(bool v,const char* s){if(!v)throw std::runtime_error(s);}
class Handler final: public FObject,public IComponentHandler {
public:
 unsigned begin{},values{},end{},restarts{};int32 restart_flags{};
 tresult PLUGIN_API beginEdit(ParamID) override {++begin;return kResultOk;}
 tresult PLUGIN_API performEdit(ParamID,ParamValue) override {++values;return kResultOk;}
 tresult PLUGIN_API endEdit(ParamID) override {++end;return kResultOk;}
 tresult PLUGIN_API restartComponent(int32 f) override {++restarts;restart_flags|=f;return kResultOk;}
 OBJ_METHODS(Handler,FObject)
 DEFINE_INTERFACES
  DEF_INTERFACE(IComponentHandler)
 END_DEFINE_INTERFACES(FObject)
 REFCOUNT_METHODS(FObject)
};
#ifdef BOILED_EGG_PLUGIN_X11
class Frame final: public FObject,public IPlugFrame,public Linux::IRunLoop {
public:
 IPtr<Linux::ITimerHandler> timer;
 tresult PLUGIN_API resizeView(IPlugView* view,ViewRect* size) override {return view&&size?view->onSize(size):kInvalidArgument;}
 tresult PLUGIN_API registerEventHandler(Linux::IEventHandler*,Linux::FileDescriptor) override {return kNotImplemented;}
 tresult PLUGIN_API unregisterEventHandler(Linux::IEventHandler*) override {return kNotImplemented;}
 tresult PLUGIN_API registerTimer(Linux::ITimerHandler* h,Linux::TimerInterval ms) override {if(timer||!h||!ms)return kResultFalse;timer=h;return kResultOk;}
 tresult PLUGIN_API unregisterTimer(Linux::ITimerHandler* h) override {if(timer.get()!=h)return kResultFalse;timer=nullptr;return kResultOk;}
 OBJ_METHODS(Frame,FObject)
 DEFINE_INTERFACES
  DEF_INTERFACE(IPlugFrame)
  DEF_INTERFACE(Linux::IRunLoop)
 END_DEFINE_INTERFACES(FObject)
 REFCOUNT_METHODS(FObject)
};
static void click(Display* d,Window w,int x,int y){
 for(int type:{ButtonPress,ButtonRelease}){XEvent e{};e.xbutton.type=type;e.xbutton.display=d;e.xbutton.window=w;e.xbutton.root=DefaultRootWindow(d);
 e.xbutton.x=x;e.xbutton.y=y;e.xbutton.button=1;e.xbutton.same_screen=True;XSendEvent(d,w,False,type==ButtonPress?ButtonPressMask:ButtonReleaseMask,&e);}XSync(d,False);
}
#endif
static auto initial_values(bool pv,unsigned policy){auto v=bp::defaults();v[bp::Backend]=pv?1:0;v[bp::Quality]=1;v[bp::Policy]=pv?float(policy):0;v[bp::Pitch]=-3;return v;}
int main(int argc,char** argv){try{
 require(argc>=2,"VST3 bundle path required");const bool ui=argc>=3;
 std::string error;auto module=VST3::Hosting::Module::create(argv[1],error);require(bool(module),error.c_str());
 HostApplication host;module->getFactory().setHostContext(&host);auto classes=module->getFactory().classInfos();require(classes.size()==1,"one existing product identity");
 unsigned cases=0;
 for(unsigned rate:{44100u,48000u,88200u,96000u})for(unsigned block:{32u,257u})for(unsigned policy:{0u,1u,2u,3u}){
  const bool pv=policy!=3;if(pv&&!bp::spectral_available())continue;
  auto c=module->getFactory().createInstance<IComponent>(classes[0].ID());require(bool(c)&&c->initialize(&host)==kResultOk,"component init");
  FUnknownPtr<IAudioProcessor> p(c);FUnknownPtr<IEditController> ctl(c);require(p&&ctl,"interfaces");
  auto handler=owned(new Handler);require(ctl->setComponentHandler(handler)==kResultOk,"handler");
  require(ctl->getParameterCount()==bp::Count,"parameter count");ParameterInfo info{};require(ctl->getParameterInfo(0,info)==kResultOk&&info.id==1000,"legacy pitch ID");
  require(ctl->normalizedParamToPlain(1000,0)==-24&&ctl->normalizedParamToPlain(1000,1)==24,"legacy normalization");
  std::array<std::uint8_t,12> legacy{};bp::write_word(legacy.data(),bp::state_magic);bp::write_word(legacy.data()+4,1);bp::write_word(legacy.data()+8,std::bit_cast<unsigned>(-7.f));
  MemoryStream old(legacy.data(),12);require(c->setState(&old)==kResultOk&&ctl->getParamNormalized(1000)==17./48.,"VST3 v1 state");
  auto initial=initial_values(pv,policy);auto bytes=bp::encode(initial);MemoryStream state(bytes.data(),int32(bytes.size()));require(c->setState(&state)==kResultOk,"state v2 load");
  MemoryStream saved;require(c->getState(&saved)==kResultOk&&saved.getSize()==int64(bytes.size()),"state v2 size");
  require(std::memcmp(saved.getData(),bytes.data(),bytes.size())==0,"state v2 exact roundtrip");
  auto corrupt=bytes;corrupt[4]=91;MemoryStream bad(corrupt.data(),int32(corrupt.size()));require(c->setState(&bad)!=kResultOk,"state version rejection");
  ProcessSetup setup{kRealtime,kSample32,int32(block),double(rate)};require(p->setupProcessing(setup)==kResultOk,"setup");
  auto delay=p->getLatencySamples();require(c->setActive(true)==kResultOk&&p->setProcessing(true)==kResultOk,"activate");require(delay==p->getLatencySamples(),"activation delay changed");
  bp::Processor reference;require(reference.request(initial)&&reference.activate(rate,block)&&reference.latency()==delay,"reference init");
  const std::array<bp::Event,12> schedule{{{799,bp::Pitch,-7},{799,bp::Fine,23},{1931,bp::Formant,pv&&policy?3.f:0.f},{2137,bp::Wet,.78f},
    {2137,bp::Dry,.13f},{4111,bp::Pitch,7},{4519,bp::Pan,-.31f},{6709,bp::Volume,-3},{7919,bp::FormantFine,pv&&policy?-13.f:0.f},
    {11003,bp::Bypass,1},{13001,bp::Bypass,0},{15701,bp::Pitch,0}}};
  std::array<std::vector<float>,2> input{std::vector<float>(block),std::vector<float>(block)},expected=input,result=input;
  ParameterChanges changes(bp::Count);
  for(unsigned pos=0;pos<19013+delay;pos+=block){auto n=std::min(block,19013+delay-pos);std::array<bp::Event,256> re{};unsigned count=0;changes.clearQueue();
   // Opposite queue order verifies cross-parameter chronological sorting.
   for(unsigned rev=bp::Count;rev>0;--rev)for(auto event:schedule)if(event.index==rev-1&&event.offset>=pos&&event.offset<pos+n){int32 qi{},point{};
    auto* q=changes.addParameterData(bp::vst_id(event.index),qi);require(q&&q->addPoint(int32(event.offset-pos),bp::normalize(event.index,event.value),point)==kResultOk,"fixture queue");}
   for(auto event:schedule)if(event.offset>=pos&&event.offset<pos+n){event.offset-=pos;re[count++]=event;}
   for(unsigned i=0;i<n;++i){input[0][i]=.13f*std::sin(float(pos+i)*.0371f)+.07f*std::cos(float(pos+i)*.1231f);input[1][i]=-.5f*input[0][i];}
   const float* ri[]={input[0].data(),input[1].data()};float* ro[]={expected[0].data(),expected[1].data()};require(reference.process(ri,ro,n,{re.data(),count}),"reference events");
   float* ins[]={input[0].data(),input[1].data()};float* outs[]={input[0].data(),input[1].data()};AudioBusBuffers a{},b{};a.numChannels=b.numChannels=2;a.channelBuffers32=ins;b.channelBuffers32=outs;
   ProcessData d{};d.symbolicSampleSize=kSample32;d.numSamples=int32(n);d.numInputs=d.numOutputs=1;d.inputs=&a;d.outputs=&b;d.inputParameterChanges=&changes;
   counting_allocations=true;auto status=p->process(d);counting_allocations=false;require(status==kResultOk,"VST3 dynamic processing");
   for(unsigned ch=0;ch<2;++ch)require(std::equal(outs[ch],outs[ch]+n,expected[ch].begin()),"loaded VST3 differs from public SDK model");
   require(p->getLatencySamples()==delay,"dynamic latency changed");
  }
  changes.clearQueue();int32 index{};auto* q=changes.addParameterData(bp::vst_id(bp::Pitch),index);q->addPoint(0,bp::normalize(bp::Pitch,3),index);q->addPoint(int32(block),bp::normalize(bp::Pitch,4),index);
  float* ins[]={input[0].data(),input[1].data()};float* outs[]={result[0].data(),result[1].data()};AudioBusBuffers a{},b{};a.numChannels=b.numChannels=2;a.channelBuffers32=ins;b.channelBuffers32=outs;ProcessData d{};
  d.symbolicSampleSize=kSample32;d.numSamples=int32(block);d.numInputs=d.numOutputs=1;d.inputs=&a;d.outputs=&b;d.inputParameterChanges=&changes;
  for(auto& v:result)std::fill(v.begin(),v.end(),123.f);const double prior=ctl->getParamNormalized(1000);require(p->process(d)!=kResultOk,"bad offset accepted");
  require(prior==ctl->getParamNormalized(1000),"bad batch changed targets");for(auto& v:result)for(float sample:v)require(sample==123,"bad batch changed output");
  // Backend config is non-automatable and takes effect only after host restart.
  const auto before=handler->restarts;require(ctl->setParamNormalized(bp::vst_id(bp::Quality),0)==kResultOk,"configuration request");
  require(handler->restarts>before&&(handler->restart_flags&kLatencyChanged)&&p->getLatencySamples()==delay,"restart request / fixed active delay");
  p->setProcessing(false);c->setActive(false);ctl->setComponentHandler(nullptr);require(c->terminate()==kResultOk,"terminate");++cases;
 }
 require(allocation_count.load()==0,"VST3 process allocation");
#ifdef BOILED_EGG_PLUGIN_X11
 if(ui){auto c=module->getFactory().createInstance<IComponent>(classes[0].ID());require(c&&c->initialize(&host)==kResultOk,"UI component");FUnknownPtr<IEditController> ctl(c);FUnknownPtr<IAudioProcessor> p(c);
  auto handler=owned(new Handler);ctl->setComponentHandler(handler);auto values=initial_values(bp::spectral_available(),1);auto bytes=bp::encode(values);MemoryStream state(bytes.data(),int32(bytes.size()));require(c->setState(&state)==kResultOk,"UI state");
  ProcessSetup setup{kRealtime,kSample32,64,48000.};require(p->setupProcessing(setup)==kResultOk&&c->setActive(true)==kResultOk,"UI activate");
  auto view=owned(ctl->createView(ViewType::kEditor));require(view!=nullptr,"custom IPlugView");auto frame=owned(new Frame);
  require(view->setFrame(frame)==kResultOk&&view->isPlatformTypeSupported(kPlatformTypeX11EmbedWindowID)==kResultTrue,"XEmbed support");
  Display* display=XOpenDisplay(nullptr);require(display,"DISPLAY");Window parent=XCreateSimpleWindow(display,DefaultRootWindow(display),0,0,900,640,0,0,0);XMapWindow(display,parent);XSync(display,False);
  require(view->attached(reinterpret_cast<void*>(parent),kPlatformTypeX11EmbedWindowID)==kResultOk&&frame->timer,"attach and timer");
  for(unsigned i=0;i<8;++i){frame->timer->onTimer();XSync(display,False);}Window root{},returned{},*children=nullptr;unsigned count{};
  require(XQueryTree(display,parent,&root,&returned,&children,&count)&&count==1,"editor child");const auto child=children[0];XFree(children);
  click(display,child,789,176);frame->timer->onTimer();
  require(view->onKeyDown(u'a',0,kCommandKey)==kResultTrue,"host Ctrl+A");
  for(char16 key:{u'-',u'5',u'.',u'5'})require(view->onKeyDown(key,0,0)==kResultTrue,"host numeric input");
  require(view->onKeyDown(0,KEY_RETURN,0)==kResultTrue,"host enter");frame->timer->onTimer();
  require(ctl->getParamNormalized(1000)==bp::normalize(bp::Pitch,-5.5f),"numeric entry value");require(handler->begin&&handler->values&&handler->end,"UI edit gestures");
  require(view->onKeyDown(u'z',0,kCommandKey)==kResultFalse,"host shortcut not consumed");
  ViewRect size{0,0,1125,800};require(view->onSize(&size)==kResultOk,"resize");ViewRect check{};require(view->getSize(&check)==kResultOk&&check.right==1125&&check.bottom==800,"size report");
  require(view->removed()==kResultOk&&!frame->timer,"timer unregister");view->setFrame(nullptr);view=nullptr;XDestroyWindow(display,parent);XCloseDisplay(display);
  c->setActive(false);ctl->setComponentHandler(nullptr);require(c->terminate()==kResultOk,"UI terminate");
  std::cout<<"VST3 XEmbed editor: host keyboard, parameter gestures, resize and timer lifecycle passed\n";
 }
#else
 require(!ui,"UI disabled");
#endif
 std::cout<<cases<<" loaded VST3 dynamic/state/in-place cases; zero process allocations\n";
}catch(const std::exception& error){std::cerr<<error.what()<<'\n';return 1;}}
