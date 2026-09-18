// Standalone old/new VST3 host replay; no boiled-egg headers or shared Processor.
#include "public.sdk/source/vst/hosting/module.h"
#include "public.sdk/source/vst/hosting/hostclasses.h"
#include "public.sdk/source/vst/hosting/parameterchanges.h"
#include "public.sdk/source/common/memorystream.h"
#include "pluginterfaces/vst/ivstaudioprocessor.h"
#include "pluginterfaces/vst/ivsteditcontroller.h"
#include <algorithm>
#include <array>
#include <bit>
#include <cmath>
#include <cstdint>
#include <iostream>
#include <stdexcept>
#include <vector>
using namespace Steinberg;using namespace Steinberg::Vst;
static void check(bool ok,const char* why){if(!ok)throw std::runtime_error(why);}
static void put(std::uint8_t* p,std::uint32_t v){for(unsigned i=0;i<4;++i)p[i]=std::uint8_t(v>>(8*i));}
static std::uint32_t get(const char* p){std::uint32_t v=0;for(unsigned i=0;i<4;++i)v|=std::uint32_t(std::uint8_t(p[i]))<<(8*i);return v;}
int main(int argc,char** argv){try{
 check(argc==2,"bundle path");std::string error;auto module=VST3::Hosting::Module::create(argv[1],error);check(bool(module),error.c_str());
 HostApplication host;module->getFactory().setHostContext(&host);auto classes=module->getFactory().classInfos();check(classes.size()==1,"one identity");
 std::cout<<"rate,block,pitch,scenario,frames,latency,tail,last_pitch,audio_hash\n";
 for(unsigned rate:{44100u,48000u,88200u,96000u})for(unsigned block:{32u,257u})for(int pitch:{-12,0,12})for(unsigned scenario:{0u,1u}){
  auto c=module->getFactory().createInstance<IComponent>(classes[0].ID());check(c&&c->initialize(&host)==kResultOk,"initialize");
  FUnknownPtr<IAudioProcessor> p(c);FUnknownPtr<IEditController> ctl(c);check(p&&ctl,"interfaces");
  ParameterInfo info{};check(ctl->getParameterInfo(0,info)==kResultOk&&info.id==1000,"pitch ID");
  check(ctl->normalizedParamToPlain(1000,0)==-24&&ctl->normalizedParamToPlain(1000,1)==24,"pitch range");
  std::array<std::uint8_t,12> bytes{};put(bytes.data(),0x42454747);put(bytes.data()+4,1);put(bytes.data()+8,std::bit_cast<std::uint32_t>(float(pitch)));
  MemoryStream saved(bytes.data(),bytes.size());check(c->setState(&saved)==kResultOk,"v1 state");
  ProcessSetup setup{kRealtime,kSample32,257,double(rate)};
  check(p->setupProcessing(setup)==kResultOk&&c->setActive(true)==kResultOk&&p->setProcessing(true)==kResultOk,"activate");
  auto L=p->getLatencySamples(),T=p->getTailSamples();check(L>0,"latency");unsigned frames=24001+L;
  std::array<std::vector<float>,2>x{std::vector<float>(frames),std::vector<float>(frames)};unsigned rng=260917;
  for(unsigned i=0;i<24001;++i){rng=1664525U*rng+1013904223U;double time=double(i)/rate;
   x[0][i]=float(.1*std::sin(6.283185307179586*173*time)+.02*(double(rng>>8)/16777216.-.5));x[1][i]=-.375F*x[0][i];}
  std::array<float,257>a{},b{};float* output[]{a.data(),b.data()};std::uint64_t hash=1469598103934665603ULL;
  ParameterChanges changes(1);
  for(unsigned pos=0;pos<frames;){unsigned n=std::min(block,frames-pos);float* input[]{x[0].data()+pos,x[1].data()+pos};changes.clearQueue();
   if(scenario)for(auto [at,value]:std::array<std::pair<unsigned,double>,3>{{{777,7},{4101,-5},{12289,0}}})if(at>=pos&&at<pos+n){int32 qi{},point{};
    auto* q=changes.addParameterData(1000,qi);check(q&&q->addPoint(int32(at-pos),(value+24)/48,point)==kResultOk,"queue");}
   AudioBusBuffers in{},out{};in.numChannels=out.numChannels=2;in.channelBuffers32=input;out.channelBuffers32=output;
   ProcessData d{};d.symbolicSampleSize=kSample32;d.numSamples=n;d.numInputs=d.numOutputs=1;d.inputs=&in;d.outputs=&out;d.inputParameterChanges=&changes;
   check(p->process(d)==kResultOk,"process");
   for(unsigned i=0;i<n;++i)for(unsigned ch=0;ch<2;++ch){float v=output[ch][i];check(std::isfinite(v),"finite");if(pos+i<L)check(v==0,"startup");hash^=std::bit_cast<std::uint32_t>(v);hash*=1099511628211ULL;}pos+=n;
  }
  MemoryStream final;check(c->getState(&final)==kResultOk&&final.getSize()>=12,"saved state");
  auto version=get(final.getData()+4);check(version==1||version==2,"state version");
  if(version==2)check(final.getSize()==64,"v2 size");float last=std::bit_cast<float>(get(final.getData()+(version==1?8:16)));
  check(last==float(scenario?0:pitch),"final pitch");check(p->getLatencySamples()==L&&p->getTailSamples()==T,"fixed latency/tail");
  std::cout<<rate<<','<<block<<','<<pitch<<','<<scenario<<','<<frames<<','<<L<<','<<T<<','<<last<<','<<hash<<'\n';
  p->setProcessing(false);c->setActive(false);check(c->terminate()==kResultOk,"terminate");
 }
}catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}}
