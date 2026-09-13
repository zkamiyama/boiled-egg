#include "formant_common.hpp"
#include "test_alloc.hpp"
#include "public.sdk/source/vst/hosting/module.h"
#include "public.sdk/source/vst/hosting/hostclasses.h"
#include "public.sdk/source/vst/hosting/parameterchanges.h"
#include "public.sdk/source/common/memorystream.h"
#include "pluginterfaces/vst/ivstaudioprocessor.h"
#include "pluginterfaces/vst/ivsteditcontroller.h"
#include <algorithm>
#include <iostream>
#include <stdexcept>
#include <vector>
using namespace Steinberg;using namespace Steinberg::Vst;using namespace boiled_egg::lab;
static void require(bool v,const char* s){if(!v)throw std::runtime_error(s);}
int main(int argc,char** argv){try{
    require(argc==2,"module path");std::string error;auto module=VST3::Hosting::Module::create(argv[1],error);require(bool(module),error.c_str());
    HostApplication host;module->getFactory().setHostContext(&host);auto classes=module->getFactory().classInfos();require(classes.size()==1,"one research class");unsigned comparisons=0;
    for(unsigned sr:{44100U,48000U,96000U})for(unsigned block:{32U,64U,257U})for(bool inplace:{false,true}){
        auto c=module->getFactory().createInstance<IComponent>(classes[0].ID());require(bool(c),"component");require(c->initialize(&host)==kResultOk,"initialize");
        FUnknownPtr<IAudioProcessor> p(c);FUnknownPtr<IEditController> ctl(c);require(p&&ctl,"interfaces");
        require(ctl->setParamNormalized(parameter_id,9./24.)==kResultOk,"controller target");MemoryStream saved;require(c->getState(&saved)==kResultOk,"state save");
        ctl->setParamNormalized(parameter_id,.75);saved.seek(0,IBStream::kIBSeekSet,nullptr);require(c->setState(&saved)==kResultOk,"state restore");
        auto bytes=save(-3);bytes[4]=9;MemoryStream bad(bytes.data(),16);require(c->setState(&bad)!=kResultOk,"invalid state version");
        ProcessSetup setup{kRealtime,kSample32,static_cast<int32>(block),static_cast<double>(sr)};
        require(p->setupProcessing(setup)==kResultOk,"setup");unsigned L=p->getLatencySamples();require(L==latency(sr),"inactive declared delay");
        require(c->setActive(true)==kResultOk&&p->setProcessing(true)==kResultOk,"activate");require(p->getLatencySamples()==L,"activation delay mismatch");
        auto cfg=boiledegg_research_host_default_config(sr,2,block);cfg.formant_ratio=to_ratio(-3);boiledegg_research_pv_rt_result rr{};auto* ref=boiledegg_research_host_create(&cfg,&rr);require(ref&&!rr,"reference");
        std::array<std::vector<float>,2> in{std::vector<float>(block),std::vector<float>(block)},out=in,oracle=in;
        const unsigned marks[]={0U,777U,1559U,4097U,6200U};unsigned mark=0;ParameterChanges changes(1);
        for(unsigned pos=0;pos<sr/3+L;pos+=block){unsigned n=std::min(block,sr/3+L-pos);changes.clearQueue();int32 index=0;auto* q=changes.addParameterData(parameter_id,index);
            std::array<boiledegg_research_host_event,8> re{};unsigned rc=0;
            while(mark<5&&marks[mark]<pos+n){if(marks[mark]>=pos){float st=mark%2?-12.F:12.F;q->addPoint(static_cast<int32>(marks[mark]-pos),(st+12.)/24.,index);re[rc++]={sizeof(re[0]),marks[mark]-pos,to_ratio(st),0};}++mark;}
            for(unsigned i=0;i<n;++i){in[0][i]=.17F*std::sin(.041F*float(pos+i))+.07F*std::cos(.12F*float(pos+i));in[1][i]=-.5F*in[0][i];}
            const float* ri[]={in[0].data(),in[1].data()};float* ro[]={oracle[0].data(),oracle[1].data()};require(boiledegg_research_host_process(ref,ri,ro,n,re.data(),rc)==0,"reference process");
            float* ins[]={in[0].data(),in[1].data()};float* outs[]={inplace?ins[0]:out[0].data(),inplace?ins[1]:out[1].data()};
            AudioBusBuffers a{},b{};a.numChannels=b.numChannels=2;a.channelBuffers32=ins;b.channelBuffers32=outs;
            ProcessData d{};d.symbolicSampleSize=kSample32;d.numSamples=static_cast<int32>(n);d.numInputs=d.numOutputs=1;d.inputs=&a;d.outputs=&b;d.inputParameterChanges=&changes;
            count_allocations=true;auto status=p->process(d);count_allocations=false;require(status==kResultOk,"VST3 process");
            for(unsigned ch=0;ch<2;++ch)require(std::equal(outs[ch],outs[ch]+n,oracle[ch].begin()),"VST3 equals bridge");require(p->getLatencySamples()==L,"automation changed delay");
        }
        // Invalid offsets and nonfinite values must fail before audio changes.
        changes.clearQueue();int32 index=0;auto* q=changes.addParameterData(parameter_id,index);q->addPoint(0,.5,index);q->addPoint(static_cast<int32>(block),.7,index);
        float* ins[]={in[0].data(),in[1].data()};float* outs[]={out[0].data(),out[1].data()};AudioBusBuffers a{},b{};a.numChannels=b.numChannels=2;a.channelBuffers32=ins;b.channelBuffers32=outs;
        ProcessData d{};d.symbolicSampleSize=kSample32;d.numSamples=static_cast<int32>(block);d.numInputs=d.numOutputs=1;d.inputs=&a;d.outputs=&b;d.inputParameterChanges=&changes;
        for(auto& ch:out)std::fill(ch.begin(),ch.end(),123.F);require(p->process(d)!=kResultOk,"invalid offset accepted");for(auto& ch:out)for(float v:ch)require(v==123.F,"invalid offset changed audio");
        boiledegg_research_host_destroy(ref);p->setProcessing(false);c->setActive(false);require(c->terminate()==kResultOk,"terminate");++comparisons;
    }
    require(!allocations.load(),"VST3 process allocated");std::cout<<comparisons<<" loaded VST3 bridge-equality cases; automation/state/in-place; zero process allocations\n";
}catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}}
