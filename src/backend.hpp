#pragma once
#include <boiled_egg/backend.h>
#include "engine.hpp"
#include <optional>
#ifdef BOILED_EGG_ENABLE_EXPERIMENTAL_SPECTRAL
#include "spectral_backend.hpp"
#endif
namespace boiled_egg::detail {
// Dispatch is outside the existing WSOLA loops. Same core, same arithmetic,
// same allocations at construction; no allocation or virtual call per sample.
class BackendEngine {
public:
    BackendEngine(const boiledegg_config& c, const boiledegg_backend_config& b);
    boiledegg_result reset() noexcept;
    boiledegg_result set_time_ratio(float) noexcept;
    boiledegg_result set_pitch_ratio(float) noexcept;
    boiledegg_result set_formant_ratio(float) noexcept;
    uint32_t available() const noexcept;
    uint32_t input_latency_frames() const noexcept;
    uint32_t quantum(const boiledegg_config&) const noexcept;
    uint32_t realtime_latency(const boiledegg_config&) const noexcept;
    uint32_t realtime_tail(const boiledegg_config&) const noexcept;
    bool drained() const noexcept;
    boiledegg_result push(const float* const*,uint32_t,uint32_t&) noexcept;
    boiledegg_result pull(float* const*,uint32_t,uint32_t&) noexcept;
    boiledegg_result flush() noexcept;
private:
    std::optional<Engine> wsola_;
#ifdef BOILED_EGG_ENABLE_EXPERIMENTAL_SPECTRAL
    std::optional<SpectralBackend> spectral_;
#endif
};
boiledegg_config wsola_profile(boiledegg_config c, uint32_t quality) noexcept;
boiledegg_handle* create_selected_backend(const boiledegg_config&,
    const boiledegg_backend_config&, boiledegg_result*);
}
