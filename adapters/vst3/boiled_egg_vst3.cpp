#include <boiled_egg/boiled_egg.h>

#include "base/source/fstreamer.h"
#include "pluginterfaces/base/ibstream.h"
#include "pluginterfaces/vst/ivstparameterchanges.h"
#include "public.sdk/source/main/pluginfactory.h"
#include "public.sdk/source/vst/vstsinglecomponenteffect.h"

#include <algorithm>
#include <atomic>
#include <bit>
#include <cmath>
#include <cstdint>
#include <cstring>

namespace Steinberg::Vst {
namespace {

constexpr ParamID kPitchParamId = 1000;
constexpr uint32 kStateMagic = 0x42454747u; // BEGG
constexpr int32 kStateVersion = 1;

constexpr float normalizedToSemitones(ParamValue value) noexcept {
    return static_cast<float>(value * 48.0 - 24.0);
}
constexpr ParamValue semitonesToNormalized(float value) noexcept {
    return static_cast<ParamValue>((value + 24.0f) / 48.0f);
}
uint32_t floatBits(float value) noexcept { return std::bit_cast<uint32_t>(value); }
float bitsFloat(uint32_t bits) noexcept { return std::bit_cast<float>(bits); }

uint32 defaultWindow(double sampleRate) noexcept {
    return sampleRate >= 88200.0 ? 1536u : 1024u;
}
uint32 defaultLatency(double sampleRate) noexcept {
    const uint32 window = defaultWindow(sampleRate);
    const uint32 search = window / 8u;
    return window + search + window / 2u;
}

} // namespace

class BoiledEggVst3 final : public SingleComponentEffect {
public:
    BoiledEggVst3() = default;
    ~BoiledEggVst3() override { destroyCore(); }

    static FUnknown* createInstance(void*) { return static_cast<IAudioProcessor*>(new BoiledEggVst3); }

    tresult PLUGIN_API initialize(FUnknown* context) override {
        const tresult result = SingleComponentEffect::initialize(context);
        if (result != kResultOk) return result;
        addAudioInput(STR16("Stereo In"), SpeakerArr::kStereo);
        addAudioOutput(STR16("Stereo Out"), SpeakerArr::kStereo);
        auto* pitch = new RangeParameter(STR16("Pitch"), kPitchParamId, STR16("st"),
                                         -24.0, 24.0, 0.0, 0,
                                         ParameterInfo::kCanAutomate);
        pitch->setPrecision(2);
        parameters.addParameter(pitch);
        pitchNormalizedBits_.store(floatBits(0.5f), std::memory_order_relaxed);
        return kResultOk;
    }

    tresult PLUGIN_API terminate() override {
        destroyCore();
        return SingleComponentEffect::terminate();
    }

    tresult PLUGIN_API setupProcessing(ProcessSetup& setup) override {
        if (!std::isfinite(setup.sampleRate) || setup.sampleRate < 8000.0 ||
            setup.sampleRate > 384000.0 || setup.maxSamplesPerBlock <= 0 ||
            setup.maxSamplesPerBlock > 65536) return kInvalidArgument;
        return SingleComponentEffect::setupProcessing(setup);
    }

    tresult PLUGIN_API setBusArrangements(SpeakerArrangement* inputs, int32 numIns,
                                          SpeakerArrangement* outputs, int32 numOuts) override {
        if (!inputs || !outputs || numIns != 1 || numOuts != 1 ||
            SpeakerArr::getChannelCount(inputs[0]) != 2 ||
            SpeakerArr::getChannelCount(outputs[0]) != 2) return kResultFalse;
        return SingleComponentEffect::setBusArrangements(inputs, numIns, outputs, numOuts);
    }

    tresult PLUGIN_API canProcessSampleSize(int32 symbolicSampleSize) override {
        return symbolicSampleSize == kSample32 ? kResultTrue : kResultFalse;
    }

    tresult PLUGIN_API setActive(TBool state) override {
        if (state) {
            if (core_) return kResultOk;
            if (!std::isfinite(processSetup.sampleRate) || processSetup.sampleRate < 8000.0 ||
                processSetup.maxSamplesPerBlock <= 0) return kResultFalse;
            auto config = boiledegg_default_config(static_cast<uint32_t>(std::lround(processSetup.sampleRate)), 2);
            config.max_block_size = static_cast<uint32_t>(processSetup.maxSamplesPerBlock);
            boiledegg_result created = BOILEDEGG_INTERNAL_ERROR;
            core_ = boiledegg_create(&config, &created);
            if (!core_ || created != BOILEDEGG_OK) {
                core_ = nullptr;
                return kResultFalse;
            }
            const float pitch = normalizedToSemitones(requestedPitchNormalized());
            if (boiledegg_set_pitch_semitones(core_, pitch) != BOILEDEGG_OK) {
                destroyCore();
                return kResultFalse;
            }
            runtime_.struct_size = sizeof(runtime_);
            if (boiledegg_get_runtime_info(core_, &runtime_) != BOILEDEGG_OK) {
                destroyCore();
                return kResultFalse;
            }
        } else {
            destroyCore();
        }
        return SingleComponentEffect::setActive(state);
    }

    tresult PLUGIN_API setProcessing(TBool state) override {
        if (state && core_ && boiledegg_reset(core_) != BOILEDEGG_OK) return kResultFalse;
        return kResultOk;
    }

    uint32 PLUGIN_API getLatencySamples() override {
        return core_ ? runtime_.realtime_latency_frames : defaultLatency(processSetup.sampleRate);
    }

    uint32 PLUGIN_API getTailSamples() override {
        return core_ ? runtime_.realtime_tail_frames : defaultLatency(processSetup.sampleRate);
    }

    tresult PLUGIN_API setParamNormalized(ParamID tag, ParamValue value) override {
        const tresult result = SingleComponentEffect::setParamNormalized(tag, value);
        if (result != kResultOk && result != kResultTrue) return result;
        if (tag == kPitchParamId) {
            const ParamValue clamped = std::clamp<ParamValue>(value, 0.0, 1.0);
            pitchNormalizedBits_.store(floatBits(static_cast<float>(clamped)), std::memory_order_relaxed);
            if (core_ && boiledegg_set_pitch_semitones(core_, normalizedToSemitones(clamped)) != BOILEDEGG_OK)
                return kResultFalse;
        }
        return result;
    }

    tresult PLUGIN_API process(ProcessData& data) override {
        if (!core_) return kResultFalse;
        if (data.symbolicSampleSize != kSample32) return kResultFalse;

        IParamValueQueue* pitchQueue = nullptr;
        if (data.inputParameterChanges) {
            const int32 parameterCount = data.inputParameterChanges->getParameterCount();
            for (int32 i = 0; i < parameterCount; ++i) {
                auto* queue = data.inputParameterChanges->getParameterData(i);
                if (queue && queue->getParameterId() == kPitchParamId) {
                    pitchQueue = queue;
                    break;
                }
            }
        }

        if (data.numSamples == 0) {
            if (pitchQueue) {
                const int32 points = pitchQueue->getPointCount();
                if (points > 0) {
                    int32 offset = 0;
                    ParamValue value = 0.5;
                    if (pitchQueue->getPoint(points - 1, offset, value) == kResultTrue &&
                        !applyPitchNormalized(value)) return kResultFalse;
                }
            }
            return kResultOk;
        }

        if (data.numInputs != 1 || data.numOutputs != 1 || !data.inputs || !data.outputs ||
            data.inputs[0].numChannels != 2 || data.outputs[0].numChannels != 2 ||
            !data.inputs[0].channelBuffers32 || !data.outputs[0].channelBuffers32 ||
            !data.inputs[0].channelBuffers32[0] || !data.inputs[0].channelBuffers32[1] ||
            !data.outputs[0].channelBuffers32[0] || !data.outputs[0].channelBuffers32[1]) {
            return kResultFalse;
        }

        int32 cursor = 0;
        if (pitchQueue) {
            const int32 points = pitchQueue->getPointCount();
            for (int32 i = 0; i < points; ++i) {
                int32 offset = 0;
                ParamValue value = 0.5;
                if (pitchQueue->getPoint(i, offset, value) != kResultTrue) return kResultFalse;
                if (offset < cursor || offset > data.numSamples) return kResultFalse;
                if (offset > cursor && !processRange(data, cursor, offset - cursor)) return kResultFalse;
                if (!applyPitchNormalized(value)) return kResultFalse;
                cursor = offset;
            }
        }
        if (cursor < data.numSamples && !processRange(data, cursor, data.numSamples - cursor))
            return kResultFalse;

        uint64 silence = 0;
        for (int32 channel = 0; channel < 2; ++channel) {
            const float* out = data.outputs[0].channelBuffers32[channel];
            bool zero = true;
            for (int32 i = 0; i < data.numSamples; ++i) {
                if (out[i] != 0.0f) { zero = false; break; }
            }
            if (zero) silence |= (uint64{1} << static_cast<uint32>(channel));
        }
        data.outputs[0].silenceFlags = silence;
        return kResultOk;
    }

    tresult PLUGIN_API setState(IBStream* state) override {
        if (!state) return kInvalidArgument;
        IBStreamer stream(state, kLittleEndian);
        int32 magic = 0, version = 0;
        float semitones = 0.0f;
        if (!stream.readInt32(magic) || !stream.readInt32(version) || !stream.readFloat(semitones) ||
            static_cast<uint32>(magic) != kStateMagic || version != kStateVersion ||
            !std::isfinite(semitones) || semitones < -24.0f || semitones > 24.0f) return kResultFalse;
        return setParamNormalized(kPitchParamId, semitonesToNormalized(semitones));
    }

    tresult PLUGIN_API getState(IBStream* state) override {
        if (!state) return kInvalidArgument;
        IBStreamer stream(state, kLittleEndian);
        const float semitones = normalizedToSemitones(requestedPitchNormalized());
        if (!stream.writeInt32(static_cast<int32>(kStateMagic)) ||
            !stream.writeInt32(kStateVersion) || !stream.writeFloat(semitones)) return kResultFalse;
        return kResultOk;
    }

private:
    ParamValue requestedPitchNormalized() const noexcept {
        return static_cast<ParamValue>(bitsFloat(pitchNormalizedBits_.load(std::memory_order_relaxed)));
    }

    bool applyPitchNormalized(ParamValue value) noexcept {
        const ParamValue clamped = std::clamp<ParamValue>(value, 0.0, 1.0);
        pitchNormalizedBits_.store(floatBits(static_cast<float>(clamped)), std::memory_order_relaxed);
        return boiledegg_set_pitch_semitones(core_, normalizedToSemitones(clamped)) == BOILEDEGG_OK;
    }

    bool processRange(ProcessData& data, int32 offset, int32 frames) noexcept {
        if (frames <= 0) return true;
        const uint64 inputSilence = data.inputs[0].silenceFlags;
        const float* in[2]{};
        float* out[2]{};
        for (int32 channel = 0; channel < 2; ++channel) {
            out[channel] = data.outputs[0].channelBuffers32[channel] + offset;
            if ((inputSilence & (uint64{1} << static_cast<uint32>(channel))) != 0) {
                std::fill_n(out[channel], frames, 0.0f);
                in[channel] = out[channel];
            } else {
                in[channel] = data.inputs[0].channelBuffers32[channel] + offset;
            }
        }
        const auto result = boiledegg_process_realtime(
            core_, in, out, static_cast<uint32_t>(frames), nullptr, 0);
        return result == BOILEDEGG_OK || result == BOILEDEGG_REALTIME_UNDERRUN;
    }

    void destroyCore() noexcept {
        boiledegg_destroy(core_);
        core_ = nullptr;
        runtime_ = {};
        runtime_.struct_size = sizeof(runtime_);
    }

    boiledegg_handle* core_ = nullptr;
    boiledegg_runtime_info runtime_{sizeof(boiledegg_runtime_info), 0, 0, 0, 0, 0, 0, 0};
    std::atomic<uint32_t> pitchNormalizedBits_{floatBits(0.5f)};
};

} // namespace Steinberg::Vst

BEGIN_FACTORY_DEF("zkamiyama", "https://github.com/zkamiyama/boiled-egg", "")

DEF_CLASS2(INLINE_UID(0x9C23D6A1, 0x6E0B4F86, 0xA5C74C2B, 0x7D13F521),
           Steinberg::PClassInfo::kManyInstances,
           kVstAudioEffectClass,
           "boiled egg",
           0,
           "Fx|Pitch Shift",
           "0.1.2",
           kVstVersionString,
           Steinberg::Vst::BoiledEggVst3::createInstance)

END_FACTORY
