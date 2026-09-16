#include "spectral_backend.hpp"
#include "backend_error.hpp"
#include "experimental/pv/host_latency_bound.hpp"
#include <array>
#include <cmath>
namespace {
boiledegg_result translate(boiledegg_research_pv_rt_result r) noexcept {
    switch(r) {
        case BOILEDEGG_RESEARCH_PV_RT_OK:return BOILEDEGG_OK;
        case BOILEDEGG_RESEARCH_PV_RT_INVALID_ARGUMENT:
        case BOILEDEGG_RESEARCH_PV_RT_INVALID_CONFIG:return BOILEDEGG_INVALID_ARGUMENT;
        case BOILEDEGG_RESEARCH_PV_RT_OUT_OF_MEMORY:return BOILEDEGG_OUT_OF_MEMORY;
        case BOILEDEGG_RESEARCH_PV_RT_ALREADY_FLUSHED:return BOILEDEGG_END_OF_STREAM;
        default:return BOILEDEGG_INTERNAL_ERROR;
    }
}
}
namespace boiled_egg::detail {
SpectralBackend::SpectralBackend(const boiledegg_config& c,const boiledegg_backend_config& b)
    :backend_(b),channels_(c.channels),max_block_(c.max_block_size) {
    auto pv=boiledegg_research_pv_rt_default_config(c.sample_rate,c.channels,c.max_block_size);
    pv.fft_size=b.quality_mode==BOILEDEGG_QUALITY_GENERAL?2048u:1024u;
    pv.analysis_hop=256;pv.mode=BOILEDEGG_RESEARCH_PV_RT_PHASE_LOCKED;
    pv.formant_mode=b.formant_policy;
    pv.initial_pitch_ratio=b.initial_pitch_ratio;pv.initial_time_ratio=b.initial_time_ratio;
    auto f=boiledegg_research_default_features();f.timing_policy=1;f.rate_policy=1;
    f.initial_formant_ratio=b.initial_formant_ratio;
    auto execution=boiledegg_research_default_execution();
    execution.scheduled=b.io_contract==BOILEDEGG_IO_REALTIME?1u:0u;
    execution.simd=execution.scheduled;
    boiledegg_research_pv_rt_result result{};
    handle_=boiledegg_research_pv_rt_create_exec(&pv,&f,&execution,&result);
    if (!handle_) throw BackendConstructionError{translate(result)};
    if(b.flags&BOILEDEGG_BACKEND_CONTINUOUS_PITCH) {
        const auto enabled=boiledegg_private_pv_enable_timeline(handle_);
        if(enabled!=BOILEDEGG_RESEARCH_PV_RT_OK) {
            boiledegg_research_pv_rt_destroy(handle_);handle_=nullptr;
            throw BackendConstructionError{translate(enabled)};
        }
    }
    if(b.flags&BOILEDEGG_BACKEND_CONTINUOUS_TIME) {
        const auto status=boiledegg_private_pv_enable_time(handle_);
        if(status!=BOILEDEGG_OK) {
            boiledegg_research_pv_rt_destroy(handle_);handle_=nullptr;
            throw BackendConstructionError{status};
        }
    }
    const uint32_t scale=c.sample_rate>48000?2u:1u;
    fft_=pv.fft_size*scale;hop_=pv.analysis_hop*scale;
    latency_=boiled_egg::research::detail::compact_host_latency(scale,
        b.quality_mode==BOILEDEGG_QUALITY_GENERAL?0u:1u,
        (b.flags&BOILEDEGG_BACKEND_CONTINUOUS_PITCH)?.5f:b.initial_pitch_ratio);
}
SpectralBackend::~SpectralBackend(){boiledegg_research_pv_rt_destroy(handle_);}
boiledegg_result SpectralBackend::reset() noexcept {
    const auto r=translate(boiledegg_research_pv_rt_reset(handle_));
    if(r==BOILEDEGG_OK){flushed_=false;fault_=false;}return r;
}
boiledegg_result SpectralBackend::set_time_ratio(float v) noexcept {
    return v==backend_.initial_time_ratio?BOILEDEGG_OK:BOILEDEGG_UNSUPPORTED_MODE;
}
boiledegg_result SpectralBackend::set_pitch_ratio(float v) noexcept {
    if(backend_.flags&BOILEDEGG_BACKEND_CONTINUOUS_PITCH) {
        if(flushed_)return BOILEDEGG_OK; // public target survives to reset
        return translate(boiledegg_research_pv_rt_set_pitch_ratio(handle_,v));
    }
    return v==backend_.initial_pitch_ratio?BOILEDEGG_OK:BOILEDEGG_UNSUPPORTED_MODE;
}
boiledegg_result SpectralBackend::set_formant_ratio(float v) noexcept {
    if(flushed_)return BOILEDEGG_OK; // pending target is retained by the public mailbox for reset
    return translate(boiledegg_research_pv_rt_set_formant_ratio(handle_,v));
}
uint32_t SpectralBackend::available() const noexcept {return boiledegg_research_pv_rt_available(handle_);}
uint32_t SpectralBackend::input_latency_frames() const noexcept {return boiledegg_research_pv_rt_latency_frames(handle_);}
boiledegg_result SpectralBackend::push(const float* const* x,uint32_t n,uint32_t& accepted) noexcept {
    accepted=0;
    if(fault_)return BOILEDEGG_INVALID_STATE;
    if(flushed_)return BOILEDEGG_END_OF_STREAM;
    if(n>max_block_ || (n && !x))return BOILEDEGG_INVALID_ARGUMENT;
    for(uint32_t ch=0;ch<channels_;++ch){
        if(n && !x[ch])return BOILEDEGG_INVALID_ARGUMENT;
        for(uint32_t i=0;i<n;++i)if(!std::isfinite(x[ch][i]))return BOILEDEGG_INVALID_ARGUMENT;
    }
    std::array<const float*,2> input{};
    // Reserve >=32768 output samples for a full finalization burst. The private
    // engine has at least65536; this preview accepts at most1024-frame calls,
    // FFT<=4096,time<=2,pitch>=.5. Backpressure never drops accepted input.
    for(uint32_t i=0;i<n;++i){
        if(available()>=32768u)return BOILEDEGG_BUFFER_FULL;
        for(uint32_t ch=0;ch<channels_;++ch)input[ch]=x[ch]+i;
        const auto r=translate(boiledegg_research_pv_rt_push(handle_,input.data(),1));
        if(r!=BOILEDEGG_OK){fault_=true;return r;}++accepted;
    }
    return BOILEDEGG_OK;
}
boiledegg_result SpectralBackend::pull(float* const* y,uint32_t n,uint32_t& produced) noexcept {
    produced=0;if(fault_)return BOILEDEGG_INVALID_STATE;
    if(n && !y)return BOILEDEGG_INVALID_ARGUMENT;
    for(uint32_t ch=0;ch<channels_;++ch)if(n && !y[ch])return BOILEDEGG_INVALID_ARGUMENT;
    produced=boiledegg_research_pv_rt_pull(handle_,y,n);return BOILEDEGG_OK;
}
boiledegg_result SpectralBackend::flush() noexcept {
    if(fault_)return BOILEDEGG_INVALID_STATE;
    if(flushed_)return BOILEDEGG_OK;
    const auto r=translate(boiledegg_research_pv_rt_flush(handle_));
    if(r==BOILEDEGG_OK)flushed_=true;else fault_=true;
    return r;
}
}

namespace boiled_egg::detail {
boiledegg_result SpectralBackend::validate_ramps(const boiledegg_ramp_event* e,uint32_t n,uint32_t frames,float pitch) const noexcept {
    if(!(backend_.flags&BOILEDEGG_BACKEND_CONTINUOUS_PITCH))return BOILEDEGG_UNSUPPORTED_MODE;
    if(fault_)return BOILEDEGG_INVALID_STATE;
    if(flushed_)return BOILEDEGG_END_OF_STREAM;
    return boiledegg_private_pv_validate_ramps(handle_,e,n,frames,pitch);
}
boiledegg_result SpectralBackend::apply_ramp(const boiledegg_ramp_event& e) noexcept {
    return boiledegg_private_pv_apply_ramp(handle_,&e);
}
boiledegg_result SpectralBackend::automation_info(boiledegg_automation_info& i) const noexcept {
    return boiledegg_private_pv_automation_info(handle_,&i);
}
bool SpectralBackend::can_accept_ramp_sample() const noexcept {return !fault_&&!flushed_&&available()<32768u;}
}
