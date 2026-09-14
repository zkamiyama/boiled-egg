#pragma once
#include <boiled_egg/backend.h>
#include "engine.hpp"
#include <optional>
namespace boiled_egg::detail {
// Dispatch is outside the existing WSOLA loops. Same core, same arithmetic,
// same allocations at construction; no allocation or virtual call per sample.
class BackendEngine {
public:
    BackendEngine(const boiledegg_config& c, const boiledegg_backend_config& b);
    boiledegg_result reset() noexcept { return wsola_->reset(); }
    boiledegg_result set_time_ratio(float v) noexcept { return wsola_->set_time_ratio(v); }
    boiledegg_result set_pitch_ratio(float v) noexcept { return wsola_->set_pitch_ratio(v); }
    uint32_t available() const noexcept { return wsola_->available(); }
    uint32_t input_latency_frames() const noexcept { return wsola_->input_latency_frames(); }
    bool drained() const noexcept { return wsola_->drained(); }
    boiledegg_result push(const float* const* x, uint32_t n, uint32_t& accepted) noexcept { return wsola_->push(x,n,accepted); }
    boiledegg_result pull(float* const* y, uint32_t n, uint32_t& produced) noexcept { return wsola_->pull(y,n,produced); }
    boiledegg_result flush() noexcept { return wsola_->flush(); }
private:
    std::optional<Engine> wsola_;
};
boiledegg_config wsola_profile(boiledegg_config c, uint32_t quality) noexcept;
boiledegg_handle* create_selected_backend(const boiledegg_config&,
    const boiledegg_backend_config&, boiledegg_result*);
}
