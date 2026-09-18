// Exercise a loaded VST3 through public interfaces, without the shared Processor.
#include "public.sdk/source/vst/hosting/module.h"
#include "public.sdk/source/vst/hosting/hostclasses.h"
#include "public.sdk/source/common/memorystream.h"
#include "pluginterfaces/vst/ivsteditcontroller.h"
#include "pluginterfaces/vst/ivstaudioprocessor.h"
#include <algorithm>
#include <array>
#include <bit>
#include <cmath>
#include <cstring>
#include <iostream>
#include <limits>
#include <stdexcept>
#include <vector>
using namespace Steinberg;
using namespace Steinberg::Vst;
static void check(bool ok,const char* text){if(!ok)throw std::runtime_error(text);}
static void word(std::uint8_t* p,std::uint32_t value){for(unsigned i=0;i<4;++i)p[i]=std::uint8_t(value>>(8*i));}
static std::vector<char> state(IComponent* c){MemoryStream s;check(c->getState(&s)==kResultOk,"getState");return {s.getData(),s.getData()+s.getSize()};}
static bool load(IComponent* c,const std::vector<char>& b){MemoryStream s(const_cast<char*>(b.data()),TSize(b.size()));return c->setState(&s)==kResultOk;}
static std::array<double,12> values(IEditController* c){std::array<double,12> v{};for(unsigned i=0;i<12;++i)v[i]=c->getParamNormalized(1000+i);return v;}
class Chunked final : public MemoryStream {
public:
 using MemoryStream::MemoryStream;
 tresult PLUGIN_API read(void* p,int32 n,int32* used) override {return MemoryStream::read(p,std::min(n,3),used);}
 tresult PLUGIN_API write(void* p,int32 n,int32* used) override {return MemoryStream::write(p,std::min(n,3),used);}
};
int main(int argc,char** argv){try{
 check(argc==2,"bundle path");std::string error;auto module=VST3::Hosting::Module::create(argv[1],error);
 check(bool(module),error.c_str());HostApplication host;module->getFactory().setHostContext(&host);
 auto classes=module->getFactory().classInfos();check(classes.size()==1,"one identity");
 auto c=module->getFactory().createInstance<IComponent>(classes[0].ID());check(c&&c->initialize(&host)==kResultOk,"initialize");
 FUnknownPtr<IEditController> ctl(c);FUnknownPtr<IAudioProcessor> p(c);check(ctl&&p,"interfaces");
 check(ctl->getParameterCount()==12,"twelve declared parameters");
 check(ctl->normalizedParamToPlain(1000,0)==-24&&ctl->normalizedParamToPlain(1000,1)==24,"old pitch range");
 unsigned failures=0,labels=0,negative_states=0;
 const std::array<std::vector<const char*>,3> names{{{"WSOLA","Spectral PV (preview)"},{"General","Transient","Efficient"},{"Off","Harmonic / polyphonic","Monophonic"}}};
 for(unsigned group=0;group<3;++group){const ParamID id=1009+group;ParameterInfo info{};
  check(ctl->getParameterInfo(int32(9+group),info)==kResultOk&&info.id==id,"configuration ID");
  if(!(info.flags&ParameterInfo::kIsList)){++failures;std::cerr<<"missing list metadata id="<<id<<'\n';}
  check(!(info.flags&ParameterInfo::kCanAutomate)&&info.stepCount==int32(names[group].size()-1),"configuration automation/steps");
  const auto before=values(ctl);
  for(unsigned i=0;i<names[group].size();++i){const double expected=double(i)/double(names[group].size()-1);String128 text{},label{};
   const char* s=names[group][i];for(unsigned j=0;s[j];++j)label[j]=TChar(s[j]);
   check(ctl->getParamStringByValue(id,expected,text)==kResultOk&&std::equal(text,text+128,label),"choice display label");
   ParamValue got=-1;const bool converted=ctl->getParamValueByString(id,label,got)==kResultOk;
   if(!converted||got!=expected){++failures;std::cerr<<"label round-trip failed id="<<id<<" value="<<i<<'\n';}
   check(ctl->normalizedParamToPlain(id,expected)==double(i)&&ctl->plainParamToNormalized(id,i)==expected,"choice normalized values");++labels;
  }
  String128 unknown{};const char* bad="not a supported choice";for(unsigned i=0;bad[i];++i)unknown[i]=TChar(bad[i]);
  ParamValue sentinel=.314;check(ctl->getParamValueByString(id,unknown,sentinel)!=kResultOk&&sentinel==.314,"invalid label changed output");
  check(values(ctl)==before,"display parsing changed parameters");
 }
 // A literal v1 VST3 state. No state encoder from the plug-in is used here.
 std::vector<char> old(12);auto* b=reinterpret_cast<std::uint8_t*>(old.data());
 word(b,0x42454747);word(b+4,1);word(b+8,std::bit_cast<std::uint32_t>(-7.f));
 check(load(c,old)&&ctl->getParamNormalized(1000)==17./48.,"v1 migration");
 check(ctl->getParamNormalized(1009)==0&&ctl->getParamNormalized(1011)==0,"v1 restores WSOLA/Off");
 check(ctl->setParamNormalized(1004,.65)==kResultOk&&ctl->setParamNormalized(1005,.2)==kResultOk,"set mix state");
 auto expected=state(c);check(expected.size()==64,"version2 state size");const auto snapshot=values(ctl);
 ProcessSetup setup{kRealtime,kSample32,64,48000.};check(p->setupProcessing(setup)==kResultOk&&c->setActive(true)==kResultOk,"activate");
 const auto latency=p->getLatencySamples();
 for(unsigned n=0;n<expected.size();++n){std::vector<char> truncated(expected.begin(),expected.begin()+n);
  check(!load(c,truncated),"truncated state accepted");check(state(c)==expected&&values(ctl)==snapshot&&p->getLatencySamples()==latency,"truncated state mutated active instance");++negative_states;
 }
 for(unsigned offset:{0u,4u,8u,12u,16u,48u,52u}){auto bad=expected;auto* bytes=reinterpret_cast<std::uint8_t*>(bad.data());
  word(bytes+offset,offset==16?std::bit_cast<std::uint32_t>(std::numeric_limits<float>::quiet_NaN()):0xffffffffu);
  check(!load(c,bad)&&state(c)==expected&&values(ctl)==snapshot&&p->getLatencySamples()==latency,"invalid state was nontransactional");++negative_states;
 }
 Chunked partial(expected.data(),TSize(expected.size()));check(c->setState(&partial)==kResultOk&&state(c)==expected,"short reads");
 Chunked output;check(c->getState(&output)==kResultOk&&output.getSize()==TSize(expected.size())&&std::memcmp(output.getData(),expected.data(),expected.size())==0,"short writes");
 c->setActive(false);check(c->terminate()==kResultOk,"terminate");
 std::cout<<"labels="<<labels<<" metadata_failures="<<failures<<" rejected_states="<<negative_states<<" short_read_write=passed legacy_state=passed\n";
 return failures?2:0;
}catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}}
