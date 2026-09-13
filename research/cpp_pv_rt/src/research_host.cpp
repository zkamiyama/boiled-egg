#include "boiled_egg_research_host.h"
#include "research_features.hpp"
#include "host_latency_bound.hpp"
#include <algorithm>
#include <atomic>
#include <bit>
#include <cmath>
#include <cstdint>
#include <new>

namespace {
using result=boiledegg_research_pv_rt_result;
constexpr auto ok=BOILEDEGG_RESEARCH_PV_RT_OK;
constexpr auto invalid=BOILEDEGG_RESEARCH_PV_RT_INVALID_ARGUMENT;
constexpr auto internal=BOILEDEGG_RESEARCH_PV_RT_INTERNAL_ERROR;
static_assert(std::atomic<std::uint32_t>::is_always_lock_free,"host mailbox requires lock-free uint32");
bool ratio_valid(float v,unsigned mode) noexcept {
    return boiled_egg::research::features::ratio_valid(v) && (mode!=0 || v==1.F);
}
bool valid(const boiledegg_research_host_config* c) noexcept {
    return c && c->struct_size>=sizeof(*c) && c->version==BOILEDEGG_RESEARCH_HOST_VERSION &&
        c->sample_rate>=16000 && c->sample_rate<=384000 && c->channels>=1 && c->channels<=8 &&
        c->max_block_frames>=1 && c->max_block_frames<=16384 && c->profile<=4 && c->formant_mode<=2 &&
        ratio_valid(c->formant_ratio,c->formant_mode) && std::isfinite(c->pitch_ratio) &&
        c->pitch_ratio>=.5F && c->pitch_ratio<=2.F && c->scheduled<=1 && c->simd<=1;
}
}
struct boiledegg_research_host_handle {
    boiledegg_research_host_config config;
    boiledegg_research_pv_rt_handle* pv{};
    boiledegg_research_multires_rt_handle* multi{};
    std::atomic<std::uint32_t> pending{0},target{0};
    std::uint32_t latency{};
    std::uint64_t clock{},events_applied{},underruns{};
    bool fault{};
    explicit boiledegg_research_host_handle(const boiledegg_research_host_config& c,bool compact=false):config(c) {
        auto f=boiledegg_research_default_features();f.timing_policy=1;f.rate_policy=1;f.initial_formant_ratio=c.formant_ratio;
        auto e=boiledegg_research_default_execution();e.scheduled=c.scheduled;e.simd=c.simd;
        result status{};
        if(c.profile==BOILEDEGG_RESEARCH_HOST_MULTIRES) {
            auto m=boiledegg_research_multires_rt_default_config(c.sample_rate,c.channels,c.max_block_frames);
            m.initial_pitch_ratio=c.pitch_ratio;m.formant_mode=c.formant_mode;
            multi=boiledegg_research_multires_rt_create_exec(&m,&f,&e,&status);
            if(!multi)throw status;
        } else {
            auto p=boiledegg_research_pv_rt_default_config(c.sample_rate,c.channels,c.max_block_frames);
            p.fft_size=c.profile==BOILEDEGG_RESEARCH_HOST_GENERAL?2048U:1024U;p.analysis_hop=256;
            p.initial_pitch_ratio=c.pitch_ratio;p.formant_mode=c.formant_mode;
            p.mode=c.profile==BOILEDEGG_RESEARCH_HOST_FUZZY?BOILEDEGG_RESEARCH_PV_RT_FUZZY:
                c.profile==BOILEDEGG_RESEARCH_HOST_FUZZY_NOISE?BOILEDEGG_RESEARCH_PV_RT_FUZZY_NOISE:BOILEDEGG_RESEARCH_PV_RT_PHASE_LOCKED;
            pv=boiledegg_research_pv_rt_create_exec(&p,&f,&e,&status);
            if(!pv)throw status;
        }
        const auto scale=boiled_egg::research::features::scale(c.sample_rate,f);
        const auto n=(c.profile==BOILEDEGG_RESEARCH_HOST_GENERAL?2048U:1024U)*scale;
        const auto hop=256U*scale;
        // Static time=1, pitch>=0.5: analysis lookahead + startup crop/resampler
        // support + hop rounding + one cooperative hop. FIR pairing adds half
        // its length. This conservative fixed delay is independent of formants,
        // caller block size and the SIMD choice. It is verified by delayed
        // waveform equality, not confused with pv_latency_frames()'s hint.
        latency=(2U*n+2U*hop+128U+(multi?64U*scale:0U)+31U)&~31U;
        if(compact)latency=boiled_egg::research::detail::compact_host_latency(scale,c.profile,c.pitch_ratio);
        target.store(std::bit_cast<std::uint32_t>(c.formant_ratio),std::memory_order_relaxed);
    }
    ~boiledegg_research_host_handle(){boiledegg_research_pv_rt_destroy(pv);boiledegg_research_multires_rt_destroy(multi);}
    result set(float v) noexcept {
        auto s=multi?boiledegg_research_multires_rt_set_formant_ratio(multi,v):boiledegg_research_pv_rt_set_formant_ratio(pv,v);
        if(s==ok){target.store(std::bit_cast<std::uint32_t>(v),std::memory_order_release);++events_applied;}
        return s;
    }
    result reset() noexcept {
        auto s=multi?boiledegg_research_multires_rt_reset(multi):boiledegg_research_pv_rt_reset(pv);
        if(s!=ok)return s;
        clock=events_applied=underruns=0;fault=false;
        const auto result=set(std::bit_cast<float>(target.load(std::memory_order_acquire)));
        events_applied=0; return result;
    }
    result process(const float* const* in,float* const* out,std::uint32_t frames,
                   const boiledegg_research_host_event* events,std::uint32_t count) noexcept {
        if(frames>config.max_block_frames || count>BOILEDEGG_RESEARCH_HOST_MAX_EVENTS ||
            (count && !events) || (frames && !out))return invalid;
        for(unsigned ch=0;ch<config.channels;++ch) {
            if(frames && (!out[ch] || (in && !in[ch])))return invalid;
            if(in)for(unsigned i=0;i<frames;++i)if(!std::isfinite(in[ch][i]))return invalid;
        }
        for(unsigned i=0;i<count;++i) {
            const auto& ev=events[i];
            if(ev.struct_size<sizeof(ev) || ev.reserved!=0 || ev.sample_offset>=frames ||
                (i && ev.sample_offset<events[i-1].sample_offset) || !ratio_valid(ev.formant_ratio,config.formant_mode))return invalid;
        }
        auto silence=[&](unsigned start){for(unsigned ch=0;ch<config.channels;++ch)std::fill(out[ch]+start,out[ch]+frames,0.F);};
        if(fault){if(frames)silence(0);return internal;}
        const auto mail=pending.exchange(0,std::memory_order_acq_rel);
        if(mail && set(std::bit_cast<float>(mail))!=ok){fault=true;if(frames)silence(0);return internal;}
        unsigned event=0;
        const float zeros[8]{};const float* inputs[8]{};float* outputs[8]{};
        for(unsigned n=0;n<frames;++n) {
            while(event<count && events[event].sample_offset==n) {
                if(set(events[event++].formant_ratio)!=ok){fault=true;silence(n);return internal;}
            }
            for(unsigned ch=0;ch<config.channels;++ch) {inputs[ch]=in?in[ch]+n:zeros+ch;outputs[ch]=out[ch]+n;}
            auto status=multi?boiledegg_research_multires_rt_push(multi,inputs,1):boiledegg_research_pv_rt_push(pv,inputs,1);
            if(status!=ok){fault=true;silence(n);return status;}
            if(clock<latency)for(unsigned ch=0;ch<config.channels;++ch)out[ch][n]=0.F;
            else {
                auto available=multi?boiledegg_research_multires_rt_available(multi):boiledegg_research_pv_rt_available(pv);
                if(!available){++underruns;fault=true;silence(n);return internal;}
                auto pulled=multi?boiledegg_research_multires_rt_pull(multi,outputs,1):boiledegg_research_pv_rt_pull(pv,outputs,1);
                if(pulled!=1){++underruns;fault=true;silence(n);return internal;}
            }
            ++clock;
        }
        return ok;
    }
};
extern "C" {
boiledegg_research_host_config boiledegg_research_host_default_config(uint32_t rate,uint32_t channels,uint32_t block) {
    return {sizeof(boiledegg_research_host_config),BOILEDEGG_RESEARCH_HOST_VERSION,rate,channels,block,
        BOILEDEGG_RESEARCH_HOST_FUZZY,BOILEDEGG_RESEARCH_PV_RT_FORMANT_HARMONIC,1.F,1.F,1,1};
}
boiledegg_research_host_handle* boiledegg_research_host_create(const boiledegg_research_host_config* c,result* status) {
    if(status)*status=BOILEDEGG_RESEARCH_PV_RT_INVALID_CONFIG;if(!valid(c))return nullptr;
    try {auto* h=new boiledegg_research_host_handle(*c);if(status)*status=ok;return h;}
    catch(result r){if(status)*status=r;}catch(const std::bad_alloc&){if(status)*status=BOILEDEGG_RESEARCH_PV_RT_OUT_OF_MEMORY;}
    catch(...){if(status)*status=internal;}return nullptr;
}
uint32_t boiledegg_research_host_compact_latency(const boiledegg_research_host_config* c) {
    if(!valid(c))return 0;
    auto f=boiledegg_research_default_features();f.rate_policy=1;
    return boiled_egg::research::detail::compact_host_latency(boiled_egg::research::features::scale(c->sample_rate,f),c->profile,c->pitch_ratio);
}
boiledegg_research_host_handle* boiledegg_research_host_create_compact(const boiledegg_research_host_config* c,result* status) {
    if(status)*status=BOILEDEGG_RESEARCH_PV_RT_INVALID_CONFIG;if(!valid(c))return nullptr;
    try {auto* h=new boiledegg_research_host_handle(*c,true);if(status)*status=ok;return h;}
    catch(result r){if(status)*status=r;}catch(const std::bad_alloc&){if(status)*status=BOILEDEGG_RESEARCH_PV_RT_OUT_OF_MEMORY;}
    catch(...){if(status)*status=internal;}return nullptr;
}
void boiledegg_research_host_destroy(boiledegg_research_host_handle* h){delete h;}
result boiledegg_research_host_reset(boiledegg_research_host_handle* h){return h?h->reset():invalid;}
result boiledegg_research_host_process(boiledegg_research_host_handle* h,const float* const* in,float* const* out,uint32_t frames,
    const boiledegg_research_host_event* events,uint32_t count){return h?h->process(in,out,frames,events,count):invalid;}
uint32_t boiledegg_research_host_latency_frames(const boiledegg_research_host_handle* h){return h?h->latency:0;}
result boiledegg_research_host_request_formant(boiledegg_research_host_handle* h,float v) {
    if(!h || !ratio_valid(v,h->config.formant_mode))return invalid;
    auto bits=std::bit_cast<std::uint32_t>(v);
    h->target.store(bits,std::memory_order_release);h->pending.store(bits,std::memory_order_release);return ok;
}
float boiledegg_research_host_get_target(const boiledegg_research_host_handle* h) {
    return h?std::bit_cast<float>(h->target.load(std::memory_order_acquire)):0.F;
}
result boiledegg_research_host_state_get(const boiledegg_research_host_handle* h,boiledegg_research_host_state* s) {
    if(!h || !s || s->struct_size<sizeof(*s))return invalid;
    *s={sizeof(*s),BOILEDEGG_RESEARCH_HOST_VERSION,boiledegg_research_host_get_target(h),0};return ok;
}
result boiledegg_research_host_state_request(boiledegg_research_host_handle* h,const boiledegg_research_host_state* s) {
    if(!s || s->struct_size<sizeof(*s) || s->version!=BOILEDEGG_RESEARCH_HOST_VERSION || s->reserved)return invalid;
    return boiledegg_research_host_request_formant(h,s->formant_ratio);
}
result boiledegg_research_host_get_stats(const boiledegg_research_host_handle* h,boiledegg_research_host_stats* s) {
    if(!h || !s || s->struct_size<sizeof(*s))return invalid;
    *s={sizeof(*s),h->latency,h->clock,h->events_applied,h->underruns,{sizeof(s->execution),0,0,0,0}};
    return h->multi?boiledegg_research_multires_rt_execution_stats(h->multi,&s->execution):boiledegg_research_pv_rt_execution_stats(h->pv,&s->execution);
}
}
