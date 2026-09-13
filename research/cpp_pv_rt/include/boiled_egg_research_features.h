#ifndef BOILED_EGG_RESEARCH_FEATURES_H
#define BOILED_EGG_RESEARCH_FEATURES_H

#include "boiled_egg_pv_rt.h"
#include "boiled_egg_multires_rt.h"

#ifdef __cplusplus
extern "C" {
#endif

/* Opt-in research features. Existing create(), config layouts and defaults do
 * not change. No product ABI or automatic content classifier is introduced.
 * Every function uses the same single-audio-owner contract as the research API.
 */
#define BOILEDEGG_RESEARCH_FEATURES_VERSION 1u

typedef enum boiledegg_research_timing_policy {
    BOILEDEGG_RESEARCH_TIMING_LEGACY = 0,
    /* Center of the first synthesis frame maps to input time zero. Does not
     * eliminate transient smearing; static-ratio timing is tested separately.
     * latency_frames() reports a conservative input-lookahead bound across the
     * full research ratio range, NOT a fixed host/PDC output delay. */
    BOILEDEGG_RESEARCH_TIMING_CENTERED = 1
} boiledegg_research_timing_policy;

typedef enum boiledegg_research_rate_policy {
    BOILEDEGG_RESEARCH_RATE_FIXED = 0,
    /* Multiply FFT, hop and cepstral order by the smallest power of two s with
     * rate <= 48000*s. No down-scaling below 48k. Crossover remains in Hz.
     * Multi-resolution FIR length becomes (taps-1)*s+1. */
    BOILEDEGG_RESEARCH_RATE_SCALED = 1
} boiledegg_research_rate_policy;

typedef struct boiledegg_research_features {
    uint32_t struct_size;
    uint32_t version;
    uint32_t timing_policy;
    uint32_t rate_policy;
    /* Desired output envelope-frequency / input envelope-frequency, [0.5,2].
     * 1 preserves formants; matching pitch requests ordinary envelope motion.
     * A nonunity value requires HARMONIC or MONOPHONIC. It is not a gain knob. */
    float initial_formant_ratio;
} boiledegg_research_features;

boiledegg_research_features boiledegg_research_default_features(void);

boiledegg_research_pv_rt_handle* boiledegg_research_pv_rt_create_ex(
    const boiledegg_research_pv_rt_config* config,
    const boiledegg_research_features* features,
    boiledegg_research_pv_rt_result* result);
boiledegg_research_multires_rt_handle* boiledegg_research_multires_rt_create_ex(
    const boiledegg_research_multires_rt_config* config,
    const boiledegg_research_features* features,
    boiledegg_research_pv_rt_result* result);

/* Target ratio. Applied with a 10ms log-domain time constant per analysis frame.
 * Changes are audio-owner calls, not thread-safe control-mailbox operations.
 * Getters return the target. Reset retains current controls and clears smoothing. */
boiledegg_research_pv_rt_result boiledegg_research_pv_rt_set_formant_ratio(
    boiledegg_research_pv_rt_handle* handle, float ratio);
float boiledegg_research_pv_rt_get_formant_ratio(const boiledegg_research_pv_rt_handle* handle);
boiledegg_research_pv_rt_result boiledegg_research_multires_rt_set_formant_ratio(
    boiledegg_research_multires_rt_handle* handle, float ratio);
float boiledegg_research_multires_rt_get_formant_ratio(const boiledegg_research_multires_rt_handle* handle);

#ifdef __cplusplus
}
#endif
#endif
