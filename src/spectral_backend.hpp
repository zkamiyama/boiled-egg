#pragma once
#include <boiled_egg/backend.h>
#include "experimental/pv/boiled_egg_research_execution.h"
namespace boiled_egg::detail {
class SpectralBackend {
public:
    SpectralBackend(const boiledegg_config&,const boiledegg_backend_config&);
    ~SpectralBackend();
    SpectralBackend(const SpectralBackend&)=delete;
    SpectralBackend& operator=(const SpectralBackend&)=delete;
    boiledegg_result reset() noexcept;
    boiledegg_result set_time_ratio(float v) noexcept;
    boiledegg_result set_pitch_ratio(float v) noexcept;
    boiledegg_result set_formant_ratio(float v) noexcept;
    uint32_t available() const noexcept;
    uint32_t input_latency_frames() const noexcept;
    uint32_t realtime_latency_frames() const noexcept { return latency_; }
    uint32_t realtime_tail_frames() const noexcept { return latency_+8u*fft_+128u; }
    uint32_t quantum() const noexcept { return hop_; }
    bool drained() const noexcept { return flushed_ && !fault_ && available()==0; }
    boiledegg_result push(const float* const*,uint32_t,uint32_t&) noexcept;
    boiledegg_result pull(float* const*,uint32_t,uint32_t&) noexcept;
    boiledegg_result flush() noexcept;
private:
    boiledegg_research_pv_rt_handle* handle_{};
    const boiledegg_backend_config backend_;
    uint32_t channels_{},max_block_{},fft_{},hop_{},latency_{};
    bool flushed_{},fault_{};
};
}
