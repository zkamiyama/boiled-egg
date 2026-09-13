#include "formant_common.hpp"
#include "base/source/fstreamer.h"
#include "pluginterfaces/base/ibstream.h"
#include "pluginterfaces/vst/ivstparameterchanges.h"
#include "public.sdk/source/main/pluginfactory.h"
#include "public.sdk/source/vst/vstsinglecomponenteffect.h"
#include <algorithm>
#include <vector>
namespace Steinberg::Vst {
using namespace boiled_egg::lab;
class FormantLab final:public SingleComponentEffect {
public:
    ~FormantLab()override{destroy();}
    static FUnknown* createInstance(void*){return static_cast<IAudioProcessor*>(new FormantLab);}
    tresult PLUGIN_API initialize(FUnknown* context)override{
        auto r=SingleComponentEffect::initialize(context);if(r!=kResultOk)return r;
        addAudioInput(STR16("Stereo In"),SpeakerArr::kStereo);addAudioOutput(STR16("Stereo Out"),SpeakerArr::kStereo);
        auto* p=new RangeParameter(STR16("Formant"),parameter_id,STR16("st"),-12,12,0,0,ParameterInfo::kCanAutomate);p->setPrecision(2);parameters.addParameter(p);return kResultOk;
    }
    tresult PLUGIN_API terminate()override{destroy();return SingleComponentEffect::terminate();}
    tresult PLUGIN_API setupProcessing(ProcessSetup& setup)override{
        if(core_||!valid_rate(setup.sampleRate)||setup.maxSamplesPerBlock<=0||setup.maxSamplesPerBlock>16384||setup.symbolicSampleSize!=kSample32)return kInvalidArgument;
        zero_.assign(static_cast<std::size_t>(setup.maxSamplesPerBlock),0.F);
        return SingleComponentEffect::setupProcessing(setup);
    }
    tresult PLUGIN_API setBusArrangements(SpeakerArrangement* i,int32 ni,SpeakerArrangement* o,int32 no)override{
        if(!i||!o||ni!=1||no!=1||i[0]!=SpeakerArr::kStereo||o[0]!=SpeakerArr::kStereo)return kResultFalse;
        return SingleComponentEffect::setBusArrangements(i,ni,o,no);
    }
    tresult PLUGIN_API canProcessSampleSize(int32 size)override{return size==kSample32?kResultTrue:kResultFalse;}
    tresult PLUGIN_API setActive(TBool active)override{
        if(active&&!core_){
            if(!valid_rate(processSetup.sampleRate)||processSetup.maxSamplesPerBlock<=0)return kResultFalse;
            auto c=boiledegg_research_host_default_config(static_cast<unsigned>(processSetup.sampleRate),2,static_cast<unsigned>(processSetup.maxSamplesPerBlock));
            c.formant_ratio=to_ratio(control_.get());boiledegg_research_pv_rt_result r{};core_=boiledegg_research_host_create(&c,&r);
            if(!core_)return kResultFalse;control_.pending.store(0,std::memory_order_relaxed);
        }else if(!active)destroy();return SingleComponentEffect::setActive(active);
    }
    // Lightweight transition: creation/reset belongs to inactive lifecycle.
    tresult PLUGIN_API setProcessing(TBool active)override{processing_=active!=0;return kResultOk;}
    uint32 PLUGIN_API getLatencySamples()override{return core_?boiledegg_research_host_latency_frames(core_):latency(rate());}
    uint32 PLUGIN_API getTailSamples()override{return tail(rate());}
    ParamValue PLUGIN_API getParamNormalized(ParamID id)override{return id==parameter_id?(control_.get()+12.)/24.:0.;}
    tresult PLUGIN_API setParamNormalized(ParamID id,ParamValue v)override{
        if(id!=parameter_id||!std::isfinite(v)||v<0||v>1)return kInvalidArgument;
        auto r=SingleComponentEffect::setParamNormalized(id,v);if(r!=kResultOk)return r;
        return control_.request(v*24.-12.)?kResultOk:kResultFalse;
    }
    tresult PLUGIN_API process(ProcessData& data)override{
        if(!core_||!processing_||data.symbolicSampleSize!=kSample32||data.numSamples<0||data.numSamples>processSetup.maxSamplesPerBlock)return kResultFalse;
        std::array<boiledegg_research_host_event,max_events> events{};unsigned count=0;float last=0;
        if(data.inputParameterChanges){
            int32 queues=data.inputParameterChanges->getParameterCount();if(queues<0||queues>256)return kResultFalse;bool found=false;
            for(int32 i=0;i<queues;++i){auto* q=data.inputParameterChanges->getParameterData(i);if(!q)return kResultFalse;if(q->getParameterId()!=parameter_id)continue;
                if(found)return kResultFalse;found=true;int32 n=q->getPointCount();if(n<0||n>static_cast<int32>(max_events))return kResultFalse;
                for(int32 j=0;j<n;++j){int32 offset=0;ParamValue v=0;if(q->getPoint(j,offset,v)!=kResultTrue||!std::isfinite(v)||v<0||v>1||offset<0||
                    (data.numSamples?offset>=data.numSamples:offset!=0)||(count&&static_cast<unsigned>(offset)<events[count-1].sample_offset))return kResultFalse;
                    last=static_cast<float>(v*24.-12.);events[count++]={sizeof(events[0]),static_cast<unsigned>(offset),to_ratio(last),0};}
            }
        }
        if(!data.numSamples){if(count)control_.request(last);return control_.consume(core_)?kResultOk:kResultFalse;}
        if(data.numInputs!=1||data.numOutputs!=1||!data.inputs||!data.outputs||data.inputs[0].numChannels!=2||data.outputs[0].numChannels!=2||
            !data.inputs[0].channelBuffers32||!data.outputs[0].channelBuffers32)return kResultFalse;
        const float* input[2]{};
        for(unsigned ch=0;ch<2;++ch){if(!data.outputs[0].channelBuffers32[ch]||!data.inputs[0].channelBuffers32[ch])return kResultFalse;
            input[ch]=(data.inputs[0].silenceFlags&(uint64{1}<<ch))?zero_.data():data.inputs[0].channelBuffers32[ch];}
        if(!control_.consume(core_))return kResultFalse;
        auto r=boiledegg_research_host_process(core_,input,data.outputs[0].channelBuffers32,static_cast<unsigned>(data.numSamples),events.data(),count);
        if(r!=BOILEDEGG_RESEARCH_PV_RT_OK)return kResultFalse;if(count)control_.observed(last);data.outputs[0].silenceFlags=0;return kResultOk;
    }
    tresult PLUGIN_API setState(IBStream* s)override{
        if(!s)return kInvalidArgument;std::array<std::uint8_t,16> bytes{};int32 pos=0;
        while(pos<16){int32 n=0;if(s->read(bytes.data()+pos,16-pos,&n)!=kResultOk||n<=0||n>16-pos)return kResultFalse;pos+=n;}
        float st=0;if(!load(bytes,st))return kResultFalse;return setParamNormalized(parameter_id,(st+12.)/24.);
    }
    tresult PLUGIN_API getState(IBStream* s)override{
        if(!s)return kInvalidArgument;auto bytes=save(control_.get());int32 pos=0;
        while(pos<16){int32 n=0;if(s->write(bytes.data()+pos,16-pos,&n)!=kResultOk||n<=0||n>16-pos)return kResultFalse;pos+=n;}return kResultOk;
    }
private:
    unsigned rate()const noexcept{return valid_rate(processSetup.sampleRate)?static_cast<unsigned>(processSetup.sampleRate):48000U;}
    void destroy()noexcept{boiledegg_research_host_destroy(core_);core_=nullptr;processing_=false;}
    boiledegg_research_host_handle* core_{};target control_;std::vector<float> zero_;bool processing_{};
};
}
BEGIN_FACTORY_DEF("zkamiyama", "https://github.com/zkamiyama/boiled-egg", "")
DEF_CLASS2(INLINE_UID(0xBF0A7692,0xA7E1476B,0x82775148,0xA9E1F013),Steinberg::PClassInfo::kManyInstances,kVstAudioEffectClass,
           "boiled egg Formant Lab",0,"Fx|Pitch Shift","0.1.0",kVstVersionString,Steinberg::Vst::FormantLab::createInstance)
END_FACTORY
