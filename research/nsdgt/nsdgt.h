#ifndef BE_RESEARCH_NSDGT_H
#define BE_RESEARCH_NSDGT_H
#include <stdint.h>
#ifdef __cplusplus
extern "C" {
#endif
/* Uninstalled, finite-file numerical research interface, not the SDK ABI.
   Complex buffers are interleaved float real/imag, sizes count COMPLEX samples.
   Caller owns stable, valid, disjoint buffers. Each call is synchronous.
   Windows are real double samples, explicitly supplied, with local origin
   r-floor(window_length/2). Centers are in [0, frames) and strictly increasing.
   FFT bins use exp(-i*2*pi*k*(r-floor(W/2))/M); input is zero outside [0,L).
   No original input is passed to synthesis. Outputs/info unchanged on error. */
typedef struct {
    uint32_t struct_size, fft_size;
    uint64_t frames, memory_limit_bytes;
} be_nsg_config;
typedef struct {
    int64_t center;
    uint32_t window_length, window_offset;
} be_nsg_frame;
typedef struct {
    uint64_t coefficient_count, storage_estimate_bytes;
    double minimum_diagonal, maximum_diagonal, condition_number, maximum_dual;
} be_nsg_info;
/* 0 success; 2 invalid input; 3 budget/allocation; 4 uncovered;
   5 ill-conditioned; 6 arithmetic overflow/nonfinite output. */
int be_nsg_analyze(const be_nsg_config*, const be_nsg_frame*, uint32_t frame_count,
                   const double* windows, uint64_t window_count,
                   const float* input_ri, uint64_t input_count,
                   float* coefficients_ri, uint64_t coefficient_capacity,
                   be_nsg_info*);
int be_nsg_synthesize(const be_nsg_config*, const be_nsg_frame*, uint32_t frame_count,
                      const double* windows, uint64_t window_count,
                      const float* coefficients_ri, uint64_t coefficient_count,
                      float* output_ri, uint64_t output_capacity,
                      be_nsg_info*);
#ifdef __cplusplus
}
#endif
#endif
