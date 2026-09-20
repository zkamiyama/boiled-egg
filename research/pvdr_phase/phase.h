#ifndef BE_RESEARCH_PHASE_H
#define BE_RESEARCH_PHASE_H
#include <stdint.h>
#ifdef __cplusplus
extern "C" {
#endif
/* Uninstalled NRT coefficient interface. Not the product C ABI.
   Input/output: frame-major full Hermitian FFT, interleaved float real/imag.
   Trace: frame-major nonnegative bins, predecessor code -1=time, -2=low,
   -3=initial; nonnegative code is the current-frame source frequency bin.
   Caller owns stable, disjoint valid buffers with explicitly supplied counts.
   Each call owns all mutable state. No output/trace/info writes on failure. */
typedef struct {
    uint32_t struct_size, fft_size, frame_count, method; /* 0=backward PV,1=PVDR */
    double stretch, relative_tolerance;
    uint64_t seed, memory_limit_bytes;
} be_phase_config;
typedef struct {
    uint64_t temporal_edges, frequency_edges, low_bins, workspace_estimate_bytes;
    double maximum_magnitude_error, maximum_hermitian_correction;
} be_phase_info;
/* 0=success,2=invalid/scope,3=budget/allocation,4=arithmetic/nonfinite.
   centers start at0, strictly increase, <288000; synthesis centers round(alpha*a).
   Gradients are independent outputs (double) for bins0..M/2, size N*(M/2+1).
   dt is radians/sample, df is radians/bin BEFORE stretch scaling. */
int be_phase_process(const be_phase_config*, const int64_t* centers, uint64_t center_count,
                     const float* input, uint64_t complex_count,
                     float* output, uint64_t complex_capacity,
                     int32_t* predecessors, double* dt, double* df, uint64_t diagnostic_capacity,
                     be_phase_info*);
#ifdef __cplusplus
}
#endif
#endif
