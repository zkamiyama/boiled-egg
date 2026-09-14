#include "backend.hpp"
#include <cmath>
namespace boiled_egg::detail {
BackendEngine::BackendEngine(const boiledegg_config& c,const boiledegg_backend_config&) {
    wsola_.emplace(c);
}
boiledegg_config wsola_profile(boiledegg_config c,uint32_t quality) noexcept {
    if (quality == BOILEDEGG_QUALITY_TRANSIENT) {
        auto window = std::max<uint32_t>(256u, (c.window_frames * 3u) / 4u);
        window &= ~1u;
        c.window_frames = window;
        c.search_frames = std::min<uint32_t>(c.search_frames, std::max<uint32_t>(16u, window / 8u));
    } else if (quality == BOILEDEGG_QUALITY_EFFICIENT) {
        c.search_frames = std::max<uint32_t>(8u, c.search_frames / 2u);
    }
    return c;
}
}
namespace {
bool ratio(float x,float lo,float hi) noexcept {return std::isfinite(x) && x>=lo && x<=hi;}
bool valid_audio(const boiledegg_config& c) noexcept {
    return c.abi_version==BOILEDEGG_ABI_VERSION && c.sample_rate>=8000 && c.sample_rate<=384000 &&
        c.channels>=1 && c.channels<=BOILEDEGG_MAX_CHANNELS && c.max_block_size>=1 && c.max_block_size<=65536 &&
        c.window_frames>=128 && c.window_frames%2==0 && c.search_frames<c.window_frames/2 &&
        uint64_t(c.fifo_frames)>=uint64_t(c.window_frames)*8+uint64_t(c.max_block_size)*2;
}
}
extern "C" {
boiledegg_backend_config boiledegg_default_backend_config(void) {
    return {sizeof(boiledegg_backend_config),BOILEDEGG_BACKEND_API_VERSION,
        BOILEDEGG_BACKEND_WSOLA,BOILEDEGG_QUALITY_GENERAL,BOILEDEGG_FORMANT_POLICY_OFF,
        BOILEDEGG_IO_AUTO,0,1.0f,1.0f,1.0f,{0,0}};
}
boiledegg_result boiledegg_query_backend(uint32_t id,boiledegg_backend_info* out) {
    if (!out || out->struct_size<sizeof(*out) || id>BOILEDEGG_BACKEND_PHASE_VOCODER) return BOILEDEGG_INVALID_ARGUMENT;
    boiledegg_backend_info info{};
    info.struct_size=sizeof(info); info.version=BOILEDEGG_BACKEND_API_VERSION; info.backend_id=id;
    if (id==BOILEDEGG_BACKEND_WSOLA) {
        info.status=BOILEDEGG_BACKEND_STABLE;
        info.feature_flags=BOILEDEGG_BACKEND_STREAMING|BOILEDEGG_BACKEND_REALTIME|
            BOILEDEGG_BACKEND_DYNAMIC_TIME|BOILEDEGG_BACKEND_DYNAMIC_PITCH|BOILEDEGG_BACKEND_PARAMETER_EVENTS;
        info.quality_mode_mask=(1u<<BOILEDEGG_QUALITY_GENERAL)|(1u<<BOILEDEGG_QUALITY_TRANSIENT)|(1u<<BOILEDEGG_QUALITY_EFFICIENT);
        info.formant_policy_mask=1u<<BOILEDEGG_FORMANT_POLICY_OFF;
        info.min_sample_rate=8000; info.max_sample_rate=384000;
        info.max_channels=BOILEDEGG_MAX_CHANNELS; info.max_block_frames=65536;
        info.min_time_ratio=info.min_pitch_ratio=.25f;
        info.max_time_ratio=info.max_pitch_ratio=4.0f;
        info.min_formant_ratio=info.max_formant_ratio=1.0f;
    }
    *out=info;
    return BOILEDEGG_OK;
}
boiledegg_result boiledegg_validate_backend_config(const boiledegg_config* c,const boiledegg_backend_config* b) {
    // Check prefix sizes BEFORE dereferencing the remainder of either record.
    if (!c || c->struct_size<sizeof(*c) || !b || b->struct_size<sizeof(*b)) return BOILEDEGG_INVALID_ARGUMENT;
    if (!valid_audio(*c) || b->version!=BOILEDEGG_BACKEND_API_VERSION || b->backend_id>BOILEDEGG_BACKEND_PHASE_VOCODER ||
        b->quality_mode>BOILEDEGG_QUALITY_MONOPHONIC || b->formant_policy>BOILEDEGG_FORMANT_POLICY_MONOPHONIC ||
        b->io_contract>BOILEDEGG_IO_REALTIME || (b->flags & ~BOILEDEGG_BACKEND_ALLOW_EXPERIMENTAL) ||
        b->reserved[0] || b->reserved[1] || !ratio(b->initial_time_ratio,.25f,4.0f) ||
        !ratio(b->initial_pitch_ratio,.25f,4.0f) || !ratio(b->initial_formant_ratio,.5f,2.0f)) return BOILEDEGG_INVALID_ARGUMENT;
    boiledegg_backend_info info{}; info.struct_size=sizeof(info);
    (void)boiledegg_query_backend(b->backend_id,&info);
    if (info.status==BOILEDEGG_BACKEND_UNAVAILABLE ||
        (info.status==BOILEDEGG_BACKEND_EXPERIMENTAL && !(b->flags&BOILEDEGG_BACKEND_ALLOW_EXPERIMENTAL)) ||
        !(info.quality_mode_mask&(1u<<b->quality_mode)) || !(info.formant_policy_mask&(1u<<b->formant_policy)) ||
        (b->formant_policy==BOILEDEGG_FORMANT_POLICY_OFF && b->initial_formant_ratio!=1.0f) ||
        (b->io_contract==BOILEDEGG_IO_REALTIME && b->initial_time_ratio!=1.0f)) return BOILEDEGG_UNSUPPORTED_MODE;
    if (!valid_audio(boiled_egg::detail::wsola_profile(*c,b->quality_mode))) return BOILEDEGG_INVALID_ARGUMENT;
    return BOILEDEGG_OK;
}
boiledegg_handle* boiledegg_create_backend(const boiledegg_config* c,const boiledegg_backend_config* b,boiledegg_result* result) {
    const auto status=boiledegg_validate_backend_config(c,b);
    if (result) *result=status;
    if (status!=BOILEDEGG_OK) return nullptr;
    return boiled_egg::detail::create_selected_backend(boiled_egg::detail::wsola_profile(*c,b->quality_mode),*b,result);
}
}
