#include "../common/pitch_processor.hpp"
#include "../common/pitch_editor.hpp"
#include "pluginterfaces/base/ibstream.h"
#include "pluginterfaces/vst/ivstparameterchanges.h"
#include "public.sdk/source/main/pluginfactory.h"
#include "public.sdk/source/vst/vstsinglecomponenteffect.h"
#ifdef BOILED_EGG_PLUGIN_X11
#include "public.sdk/source/common/pluginview.h"
#include "pluginterfaces/base/keycodes.h"
#include <X11/keysym.h>
#endif
#include <algorithm>
#include <array>
#include <cmath>
#include <cstring>
#include <memory>
#include <vector>

namespace Steinberg::Vst {
namespace bp = boiled_egg::plugin;
class BoiledEggVst3;
#ifdef BOILED_EGG_PLUGIN_X11
class PitchView final : public CPluginView, public Linux::ITimerHandler {
public:
    explicit PitchView(BoiledEggVst3* owner);
    ~PitchView() override;
    tresult PLUGIN_API isPlatformTypeSupported(FIDString type) override;
    tresult PLUGIN_API attached(void* parent,FIDString type) override;
    tresult PLUGIN_API removed() override;
    tresult PLUGIN_API setFrame(IPlugFrame* frame) override;
    tresult PLUGIN_API onSize(ViewRect* size) override;
    tresult PLUGIN_API onKeyDown(char16 key,int16 keyCode,int16 modifiers) override;
    tresult PLUGIN_API onKeyUp(char16,int16,int16) override {return kResultFalse;}
    tresult PLUGIN_API onFocus(TBool focused) override {if(!focused&&editor_)editor_->focus_lost();return kResultOk;}
    tresult PLUGIN_API canResize() override {return kResultTrue;}
    tresult PLUGIN_API checkSizeConstraint(ViewRect* size) override;
    void PLUGIN_API onTimer() override;
    OBJ_METHODS(PitchView,CPluginView)
    DEFINE_INTERFACES
        DEF_INTERFACE(Linux::ITimerHandler)
    END_DEFINE_INTERFACES(CPluginView)
    REFCOUNT_METHODS(CPluginView)
private:
    void unregister() noexcept;
    BoiledEggVst3* owner_;
    std::unique_ptr<bp::PitchEditor> editor_;
    IPtr<Linux::IRunLoop> loop_;
    bool registered_{};
};
#endif

class BoiledEggVst3 final : public SingleComponentEffect {
public:
    static FUnknown* createInstance(void*) {return static_cast<IAudioProcessor*>(new BoiledEggVst3);}
    tresult PLUGIN_API initialize(FUnknown* context) override {
        auto status=SingleComponentEffect::initialize(context);
        if(status!=kResultOk)return status;
        addAudioInput(STR16("Stereo In"),SpeakerArr::kStereo);
        addAudioOutput(STR16("Stereo Out"),SpeakerArr::kStereo);
        for(unsigned i=0;i<bp::Count;++i){
            const auto& d=bp::parameters[i];String128 name{},unit{};
            for(unsigned j=0;d.name[j]&&j<127;++j)name[j]=char16(d.name[j]);
            for(unsigned j=0;d.unit[j]&&j<127;++j)unit[j]=char16(d.unit[j]);
            int32 flags=d.automatable?ParameterInfo::kCanAutomate:0;
            if(i==bp::Bypass)flags|=ParameterInfo::kIsBypass;
            auto* p=new RangeParameter(name,bp::vst_id(i),unit,d.min,d.max,d.initial,
                d.stepped?int32(d.max-d.min):0,flags);
            p->setPrecision(i==bp::Fine||i==bp::FormantFine?1:2);
            parameters.addParameter(p);
        }
        return kResultOk;
    }
    tresult PLUGIN_API terminate() override {processor_.deactivate();processing_=false;return SingleComponentEffect::terminate();}
    tresult PLUGIN_API setupProcessing(ProcessSetup& setup) override {
        if(processor_.is_active()||!std::isfinite(setup.sampleRate)||setup.sampleRate<8000||setup.sampleRate>384000||
            std::floor(setup.sampleRate)!=setup.sampleRate||setup.maxSamplesPerBlock<1||setup.maxSamplesPerBlock>65536||
            setup.symbolicSampleSize!=kSample32)return kInvalidArgument;
        try {zeros_.assign(static_cast<std::size_t>(setup.maxSamplesPerBlock),0.f);}catch(...){return kOutOfMemory;}
        processor_.rate_hint(static_cast<unsigned>(setup.sampleRate));
        return SingleComponentEffect::setupProcessing(setup);
    }
    tresult PLUGIN_API setBusArrangements(SpeakerArrangement* in,int32 ni,SpeakerArrangement* out,int32 no) override {
        if(!in||!out||ni!=1||no!=1||in[0]!=SpeakerArr::kStereo||out[0]!=SpeakerArr::kStereo)return kResultFalse;
        return SingleComponentEffect::setBusArrangements(in,ni,out,no);
    }
    tresult PLUGIN_API canProcessSampleSize(int32 size) override {return size==kSample32?kResultTrue:kResultFalse;}
    tresult PLUGIN_API setActive(TBool active) override {
        if(active&&!processor_.is_active()){
            if(!std::isfinite(processSetup.sampleRate)||processSetup.maxSamplesPerBlock<1)return kResultFalse;
            try {if(!processor_.activate(static_cast<unsigned>(processSetup.sampleRate),static_cast<unsigned>(processSetup.maxSamplesPerBlock)))return kResultFalse;}
            catch(...){return kOutOfMemory;}
        } else if(!active){processing_=false;processor_.deactivate();}
        return SingleComponentEffect::setActive(active);
    }
    tresult PLUGIN_API setProcessing(TBool active) override {
        // No constructor, clearing a large history, mutex or allocation here.
        // Hosts may invoke this on their audio thread; reset is inactive lifecycle.
        if(active&&!processor_.is_active())return kResultFalse;
        processing_=active!=0;return kResultOk;
    }
    uint32 PLUGIN_API getLatencySamples() override {return processor_.latency();}
    uint32 PLUGIN_API getTailSamples() override {return processor_.tail();}
    ParamValue PLUGIN_API getParamNormalized(ParamID id) override {
        unsigned i;if(!bp::vst_index(id,i))return 0;
        return bp::normalize(i,processor_.targets.get(i));
    }
    tresult PLUGIN_API getParamStringByValue(ParamID id,ParamValue v,String128 text) override {
        unsigned i;if(!bp::vst_index(id,i)||!std::isfinite(v)||v<0||v>1)return kInvalidArgument;
        if(i>=bp::Backend){const char* s=bp::choice(i,int(std::round(bp::denormalize(i,v))));unsigned j=0;
            for(;s[j]&&j<127;++j)text[j]=char16(s[j]);text[j]=0;return kResultOk;}
        return SingleComponentEffect::getParamStringByValue(id,v,text);
    }
    tresult PLUGIN_API setParamNormalized(ParamID id,ParamValue v) override {
        unsigned i;if(!bp::vst_index(id,i)||!std::isfinite(v)||v<0||v>1)return kInvalidArgument;
        float plain=bp::denormalize(i,v);if(bp::parameters[i].stepped)plain=std::round(plain);
        if(!processor_.request(i,plain))return kResultFalse;
        const auto result=SingleComponentEffect::setParamNormalized(id,bp::normalize(i,plain));
        requestRestart();return result;
    }
    tresult PLUGIN_API process(ProcessData& d) override {
        if(!processor_.is_active()||!processing_||d.symbolicSampleSize!=kSample32||d.numSamples<0||d.numSamples>processSetup.maxSamplesPerBlock)return kResultFalse;
        std::array<bp::Event,256> events{};unsigned count=0;std::array<bool,bp::Count> seen{};
        if(d.inputParameterChanges){
            const auto queues=d.inputParameterChanges->getParameterCount();if(queues<0||queues>4096)return kResultFalse;
            for(int32 qi=0;qi<queues;++qi){
                auto* q=d.inputParameterChanges->getParameterData(qi);if(!q)return kResultFalse;
                unsigned index;if(!bp::vst_index(q->getParameterId(),index))continue;
                if(seen[index]||!bp::parameters[index].automatable)return kResultFalse;seen[index]=true;
                auto n=q->getPointCount();if(n<0||unsigned(n)>256-count)return kResultFalse;int32 previous=-1;
                for(int32 j=0;j<n;++j){int32 offset{};ParamValue value{};
                    if(q->getPoint(j,offset,value)!=kResultTrue||offset<previous||offset<0||
                        (d.numSamples?offset>=d.numSamples:offset!=0)||!std::isfinite(value)||value<0||value>1)return kResultFalse;
                    previous=offset;auto plain=bp::denormalize(index,value);if(bp::parameters[index].stepped)plain=std::round(plain);
                    events[count++]={static_cast<unsigned>(offset),index,plain};
                }
            }
            // Stable bounded insertion sort; preserve duplicate ordering within
            // each parameter queue, group all same-offset controls atomically.
            for(unsigned i=1;i<count;++i){auto event=events[i];auto j=i;while(j&&events[j-1].offset>event.offset){events[j]=events[j-1];--j;}events[j]=event;}
        }
        if(!d.numSamples)return processor_.process(nullptr,nullptr,0,{events.data(),count})?kResultOk:kResultFalse;
        if(d.numInputs!=1||d.numOutputs!=1||!d.inputs||!d.outputs||d.inputs[0].numChannels!=2||d.outputs[0].numChannels!=2||
            !d.inputs[0].channelBuffers32||!d.outputs[0].channelBuffers32)return kResultFalse;
        const float* input[2]{};
        for(unsigned ch=0;ch<2;++ch){
            if(!d.outputs[0].channelBuffers32[ch]||!d.inputs[0].channelBuffers32[ch])return kResultFalse;
            input[ch]=(d.inputs[0].silenceFlags&(uint64{1}<<ch))?zeros_.data():d.inputs[0].channelBuffers32[ch];
        }
        if(!processor_.process(input,d.outputs[0].channelBuffers32,static_cast<unsigned>(d.numSamples),{events.data(),count}))return kResultFalse;
        d.outputs[0].silenceFlags=0;return kResultOk;
    }
    tresult PLUGIN_API setState(IBStream* stream) override {
        if(!stream)return kInvalidArgument;std::array<std::uint8_t,bp::state_size> bytes{};
        auto read=[&](int32 begin,int32 end){while(begin<end){int32 n=0;auto r=stream->read(bytes.data()+begin,end-begin,&n);
            if(r!=kResultOk||n<=0||n>end-begin)return false;begin+=n;}return true;};
        if(!read(0,8))return kResultFalse;
        const auto version=bp::read_word(bytes.data()+4);const auto size=version==1?12u:version==2?unsigned(bp::state_size):0u;
        if(!size||!read(8,int32(size)))return kResultFalse;
        bp::Values v;if(!bp::decode({bytes.data(),size},v)||!processor_.request(v))return kResultFalse;
        for(unsigned i=0;i<bp::Count;++i)SingleComponentEffect::setParamNormalized(bp::vst_id(i),bp::normalize(i,v[i]));
        if(componentHandler)componentHandler->restartComponent(kParamValuesChanged);
        requestRestart();return kResultOk;
    }
    tresult PLUGIN_API getState(IBStream* stream) override {
        if(!stream)return kInvalidArgument;auto v=processor_.targets.snapshot();if(!bp::valid_values(v))return kResultFalse;
        auto bytes=bp::encode(v);int32 position=0;while(position<int32(bytes.size())){int32 n=0;
            if(stream->write(bytes.data()+position,int32(bytes.size())-position,&n)!=kResultOk||n<=0||n>int32(bytes.size())-position)return kResultFalse;position+=n;}
        return kResultOk;
    }
    IPlugView* PLUGIN_API createView(FIDString name) override {
#ifdef BOILED_EGG_PLUGIN_X11
        if(name&&!std::strcmp(name,ViewType::kEditor))return new PitchView(this);
#else
        (void)name;
#endif
        return nullptr;
    }
    bp::Processor& model() noexcept {return processor_;}
#ifdef BOILED_EGG_PLUGIN_X11
    bool edit(unsigned i,float value,bp::Gesture stage) noexcept {
        if(i>=bp::Count)return false;
        if(stage==bp::Gesture::Begin)return beginEdit(bp::vst_id(i))==kResultOk;
        if(stage==bp::Gesture::End)return endEdit(bp::vst_id(i))==kResultOk;
        if(setParamNormalized(bp::vst_id(i),bp::normalize(i,value))!=kResultOk)return false;
        return performEdit(bp::vst_id(i),bp::normalize(i,value))==kResultOk;
    }
#endif
private:
    void requestRestart() noexcept {
        if(processor_.needs_restart()&&componentHandler)componentHandler->restartComponent(kIoChanged|kLatencyChanged);
    }
    bp::Processor processor_;std::vector<float> zeros_;bool processing_{};
};

#ifdef BOILED_EGG_PLUGIN_X11
PitchView::PitchView(BoiledEggVst3* owner):owner_(owner){
    owner_->addRef();rect={0,0,int32(bp::PitchEditor::default_width),int32(bp::PitchEditor::default_height)};
    bp::EditorCallbacks callbacks{owner_,[](void* p)noexcept{return static_cast<BoiledEggVst3*>(p)->model().targets.snapshot();},
        [](void* p,unsigned i,float v,bp::Gesture g)noexcept{return static_cast<BoiledEggVst3*>(p)->edit(i,v,g);},
        [](void* p)noexcept{return static_cast<BoiledEggVst3*>(p)->model().latency();},
        [](void* p)noexcept{return static_cast<BoiledEggVst3*>(p)->model().needs_restart();},
        [](void* p)noexcept{return static_cast<BoiledEggVst3*>(p)->model().error();}};
    editor_=std::make_unique<bp::PitchEditor>(callbacks);editor_->host_keyboard(true);
}
PitchView::~PitchView(){removed();owner_->release();}
void PitchView::unregister() noexcept {if(registered_&&loop_)loop_->unregisterTimer(this);registered_=false;loop_=nullptr;}
tresult PitchView::isPlatformTypeSupported(FIDString type){return type&&!std::strcmp(type,kPlatformTypeX11EmbedWindowID)?kResultTrue:kResultFalse;}
tresult PitchView::attached(void* parent,FIDString type){
    if(!parent||isAttached()||isPlatformTypeSupported(type)!=kResultTrue||!plugFrame)return kResultFalse;
    FUnknownPtr<Linux::IRunLoop> loop(plugFrame);if(!loop)return kResultFalse;
    if(!editor_->attach(reinterpret_cast<std::uintptr_t>(parent)))return kResultFalse;
    loop_=loop.get();if(loop_->registerTimer(this,33)!=kResultOk){editor_->detach();loop_=nullptr;return kResultFalse;}
    registered_=true;editor_->resize(unsigned(rect.getWidth()),unsigned(rect.getHeight()));editor_->show(true);
    return CPluginView::attached(parent,type);
}
tresult PitchView::removed(){unregister();if(editor_)editor_->detach();return CPluginView::removed();}
tresult PitchView::setFrame(IPlugFrame* frame){if(registered_&&frame!=plugFrame.get())return kResultFalse;return CPluginView::setFrame(frame);}
tresult PitchView::onSize(ViewRect* size){if(!size||size->getWidth()<760||size->getHeight()<560||size->getWidth()>1800||size->getHeight()>1280)return kResultFalse;
    if(isAttached()&&!editor_->resize(unsigned(size->getWidth()),unsigned(size->getHeight())))return kResultFalse;return CPluginView::onSize(size);}
tresult PitchView::checkSizeConstraint(ViewRect* size){if(!size)return kInvalidArgument;size->right=size->left+std::clamp(size->getWidth(),760,1800);size->bottom=size->top+std::clamp(size->getHeight(),560,1280);return kResultTrue;}
tresult PitchView::onKeyDown(char16 key,int16 code,int16 mods){
    if(!isAttached()||!editor_)return kResultFalse;
    unsigned long symbol=key;
    switch(code){case KEY_RETURN:case KEY_ENTER:symbol=XK_Return;break;case KEY_BACK:symbol=XK_BackSpace;break;
        case KEY_ESCAPE:symbol=XK_Escape;break;case KEY_TAB:symbol=XK_Tab;break;case KEY_LEFT:symbol=XK_Left;break;
        case KEY_RIGHT:symbol=XK_Right;break;case KEY_UP:symbol=XK_Up;break;case KEY_DOWN:symbol=XK_Down;break;case KEY_HOME:symbol=XK_Home;break;default:break;}
    return editor_->key_input(symbol,key<128?char(key):0,(mods&kShiftKey)!=0,(mods&(kCommandKey|kControlKey))!=0)?kResultTrue:kResultFalse;
}
void PitchView::onTimer(){if(editor_&&isAttached())editor_->pump();}
#endif
} // namespace Steinberg::Vst

BEGIN_FACTORY_DEF("zkamiyama", "https://github.com/zkamiyama/boiled-egg", "")
DEF_CLASS2(INLINE_UID(0x9C23D6A1,0x6E0B4F86,0xA5C74C2B,0x7D13F521),Steinberg::PClassInfo::kManyInstances,
 kVstAudioEffectClass,"boiled egg",0,"Fx|Pitch Shift","0.1.3-preview",kVstVersionString,Steinberg::Vst::BoiledEggVst3::createInstance)
END_FACTORY
