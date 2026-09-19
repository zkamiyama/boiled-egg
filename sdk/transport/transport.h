#ifndef BOILED_EGG_FILE_TRANSPORT_H
#define BOILED_EGG_FILE_TRANSPORT_H
#include <stdint.h>
#if defined(_WIN32)
# if defined(BE_TRANSPORT_BUILD)
#  define BE_T_API __declspec(dllexport)
# else
#  define BE_T_API __declspec(dllimport)
# endif
#else
# define BE_T_API __attribute__((visibility("default")))
#endif
#ifdef __cplusplus
extern "C" {
#endif
/* Experimental additive SDK module. Does not change libboiled_egg's ABI.
 * Prepared file data are copied at create(), never retained by pointer.
 * One owner thread for render/events/seek/info/destroy; synchronize externally.
 * No live-input retention policy, no reverse playback, no implicit fallback.
 */
#define BE_TRANSPORT_VERSION 1u
typedef struct be_transport be_transport;
enum be_transport_mode {
    BE_T_PV_CLASSIC=0, BE_T_PV_LOCKED=1, BE_T_PV_TRANSIENT=2,
    BE_T_WSOLA=3, BE_T_WSOLA_TRANSIENT=4, BE_T_WSOLA_EFFICIENT=5
};
enum be_transport_parameter { BE_T_SPEED=0, BE_T_PITCH_SEMITONES=1, BE_T_FORMANT_SEMITONES=2 };
enum be_transport_result { BE_T_OK=0, BE_T_INVALID=1, BE_T_UNSUPPORTED=2, BE_T_NO_MEMORY=3, BE_T_INTERNAL=4 };
enum be_transport_capability { BE_T_SPECTRAL_FREEZE=1, BE_T_TIME_DOMAIN_FREEZE=2, BE_T_FORMANTS=4 };
typedef struct be_transport_config {
    uint32_t struct_size, version, source_rate, output_rate, channels;
    uint32_t mode, formant_policy, max_block_frames; /* policy 0=off,1=harmonic,2=mono */
} be_transport_config;
typedef struct be_transport_event {
    uint32_t offset, parameter, ramp_frames, reserved;
    double value;
} be_transport_event;
typedef struct be_transport_info {
    uint32_t struct_size, version, capabilities, ended;
    uint64_t output_frames, source_frames, synthesis_frames, analysis_frames;
    double source_position, analysis_anchor, speed, pitch_semitones, formant_semitones;
    uint32_t window_frames, hop_frames;
    uint64_t owned_bytes;
} be_transport_info;
BE_T_API be_transport_config be_transport_default_config(uint32_t source_rate, uint32_t channels);
/* Interleaved float PCM, frames may be zero. Only create copies/allocates.
 * The source plus DSP allocations are bounded at construction. Maximum 2^27
 * source scalar samples. Only finite input is accepted. */
BE_T_API be_transport* be_transport_create(const be_transport_config*, const float* interleaved,
                                           uint64_t frames, int* result);
BE_T_API void be_transport_destroy(be_transport*);
/* Exactly frames interleaved output frames (<=max_block_frames). Validated before
 * any mutation. speed in [0,4]; pitch in [-24,24] semitones, 0=unity.
 * Events are ordered by offset in [0,frames], stable at equal offsets.
 * ramp_frames uses OUTPUT samples, including during hold. Zero is a step.
 * Events at offset==frames are applied after audio; zero-frame calls accept offset0.
 * At speed0 the source clock is exactly stationary and synthesis continues.
 * Source-rate / output-rate scaling is included. Endpoint is clamped; samples
 * outside file bounds are zero. Ended is set after a window-length tail.
 * Controls take effect in frame synthesis with up to one window of overlap;
 * source clock accuracy is not an assertion of sample-sharp audible transitions.
 * Native transport modes are not bit-identical replacements for legacy backends.
 */
BE_T_API int be_transport_render(be_transport*, float* output, uint32_t frames,
                                const be_transport_event*, uint32_t event_count);
/* seek resets synthesis history/output clock, retains control targets; a hard
 * discontinuity is allowed. UI should stop/clear device buffering around seek. */
BE_T_API int be_transport_seek(be_transport*, double source_frame);
BE_T_API int be_transport_get_info(const be_transport*, be_transport_info*);
#ifdef __cplusplus
}
#endif
#endif
