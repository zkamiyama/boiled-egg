#include "boiled_egg_pv_rt.h"

extern "C" {

boiledegg_research_pv_rt_result boiledegg_research_pv_rt_configure_quality_profile(
    boiledegg_research_pv_rt_config* config,
    uint32_t profile) {
    if (config == nullptr) return BOILEDEGG_RESEARCH_PV_RT_INVALID_ARGUMENT;
    if (config->struct_size < sizeof(boiledegg_research_pv_rt_config) ||
        config->abi_version != BOILEDEGG_RESEARCH_PV_RT_ABI_VERSION) {
        return BOILEDEGG_RESEARCH_PV_RT_INVALID_CONFIG;
    }

    switch (profile) {
        case BOILEDEGG_RESEARCH_PV_RT_PROFILE_GENERAL:
            config->fft_size = 2048U;
            config->analysis_hop = 256U;
            config->mode = BOILEDEGG_RESEARCH_PV_RT_PHASE_LOCKED;
            return BOILEDEGG_RESEARCH_PV_RT_OK;
        case BOILEDEGG_RESEARCH_PV_RT_PROFILE_TRANSIENT:
            config->fft_size = 1024U;
            config->analysis_hop = 128U;
            config->mode = BOILEDEGG_RESEARCH_PV_RT_PHASE_LOCKED;
            return BOILEDEGG_RESEARCH_PV_RT_OK;
        default:
            return BOILEDEGG_RESEARCH_PV_RT_INVALID_ARGUMENT;
    }
}

} // extern "C"
