#ifndef BOILED_EGG_BACKEND_H
#define BOILED_EGG_BACKEND_H
#include "boiled_egg.h"
#ifdef __cplusplus
extern "C" {
#endif
#define BOILEDEGG_BACKEND_API_VERSION 1u

typedef enum boiledegg_backend_id {
    BOILEDEGG_BACKEND_WSOLA = 0,
    BOILEDEGG_BACKEND_PHASE_VOCODER = 1
} boiledegg_backend_id;
/* Orthogonal to quality_mode. These are NOT the legacy formant_mode enum. */
typedef enum boiledegg_formant_policy {
    BOILEDEGG_FORMANT_POLICY_OFF = 0,
    BOILEDEGG_FORMANT_POLICY_HARMONIC = 1,
    BOILEDEGG_FORMANT_POLICY_MONOPHONIC = 2
} boiledegg_formant_policy;
typedef enum boiledegg_io_contract {
    BOILEDEGG_IO_AUTO = 0, /* legacy: first processing call selects the mode */
    BOILEDEGG_IO_STREAMING = 1,
    BOILEDEGG_IO_REALTIME = 2
} boiledegg_io_contract;
typedef enum boiledegg_backend_status {
    BOILEDEGG_BACKEND_UNAVAILABLE = 0,
    BOILEDEGG_BACKEND_STABLE = 1,
    BOILEDEGG_BACKEND_EXPERIMENTAL = 2
} boiledegg_backend_status;
#define BOILEDEGG_BACKEND_ALLOW_EXPERIMENTAL (1u << 0)
/* Backend feature flags: distinct from boiledegg_runtime_info capabilities. */
#define BOILEDEGG_BACKEND_STREAMING          (1u << 0)
#define BOILEDEGG_BACKEND_REALTIME           (1u << 1)
#define BOILEDEGG_BACKEND_DYNAMIC_TIME       (1u << 2)
#define BOILEDEGG_BACKEND_DYNAMIC_PITCH      (1u << 3)
#define BOILEDEGG_BACKEND_DYNAMIC_FORMANT    (1u << 4)
#define BOILEDEGG_BACKEND_PARAMETER_EVENTS   (1u << 5)

typedef struct boiledegg_backend_config {
    uint32_t struct_size, version, backend_id, quality_mode;
    uint32_t formant_policy, io_contract, flags;
    float initial_time_ratio, initial_pitch_ratio, initial_formant_ratio;
    uint32_t reserved[2]; /* must be zero */
} boiledegg_backend_config;
typedef struct boiledegg_backend_info {
    uint32_t struct_size, version, backend_id, status;
    uint32_t feature_flags, quality_mode_mask, formant_policy_mask;
    uint32_t min_sample_rate, max_sample_rate, max_channels, max_block_frames;
    float min_time_ratio, max_time_ratio, min_pitch_ratio, max_pitch_ratio;
    float min_formant_ratio, max_formant_ratio;
    uint32_t reserved[3];
} boiledegg_backend_info;

#define BOILEDEGG_PARAMETER_FORMANT_RATIO 4u
#define BOILEDEGG_PARAMETER_FORMANT_SEMITONES 5u
/* State for this extension. Identity must match the live handle; restoring does
 * not silently switch backends/policies. Legacy state remains time/pitch only
 * and never overwrites the formant target. Snapshots are per-field atomic, not
 * a transaction with concurrently changing UI parameters. */
typedef struct boiledegg_backend_parameter_state {
    uint32_t struct_size, version, backend_id, formant_policy;
    float time_ratio, pitch_ratio, formant_ratio;
    uint32_t reserved;
} boiledegg_backend_parameter_state;
BOILEDEGG_API boiledegg_result boiledegg_set_formant_ratio(boiledegg_handle*,float ratio);
BOILEDEGG_API boiledegg_result boiledegg_set_formant_semitones(boiledegg_handle*,float semitones);
BOILEDEGG_API float boiledegg_get_formant_ratio(const boiledegg_handle*);
BOILEDEGG_API boiledegg_result boiledegg_get_backend_parameter_state(
    const boiledegg_handle*,boiledegg_backend_parameter_state*);
BOILEDEGG_API boiledegg_result boiledegg_set_backend_parameter_state(
    boiledegg_handle*,const boiledegg_backend_parameter_state*);

BOILEDEGG_API boiledegg_backend_config boiledegg_default_backend_config(void);
/* Allocation-free build-level inventory. Known but uncompiled backends return
 * OK with status UNAVAILABLE and zero feature/range masks. This is not a quality
 * or hard-RT certification. Config validation is the authority for combinations.
 * Unknown IDs/malformed output buffers return INVALID_ARGUMENT, no mutation. */
BOILEDEGG_API boiledegg_result boiledegg_query_backend(
    uint32_t backend_id, boiledegg_backend_info* out_info);
/* No construction, allocation or fallback. INVALID_ARGUMENT = malformed;
 * UNSUPPORTED_MODE = known choice unavailable in this build/configuration.
 * All sized input records must contain at least their four-byte size prefix.
 * Larger same-version records are accepted; unknown tail bytes are ignored. */
BOILEDEGG_API boiledegg_result boiledegg_validate_backend_config(
    const boiledegg_config* config, const boiledegg_backend_config* backend);
BOILEDEGG_API boiledegg_handle* boiledegg_create_backend(
    const boiledegg_config* config, const boiledegg_backend_config* backend,
    boiledegg_result* out_result);
/* Immutable construction configuration; current parameters use the normal
 * getters/state API. Writes only the known prefix; caller's tail is untouched. */
BOILEDEGG_API boiledegg_result boiledegg_get_backend_configuration(
    const boiledegg_handle* handle, boiledegg_backend_config* out_config);
#ifdef __cplusplus
}
#endif
#endif
