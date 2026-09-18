#ifndef BOILED_EGG_PLUGIN_PITCH_PROCESSOR_HPP
#define BOILED_EGG_PLUGIN_PITCH_PROCESSOR_HPP
#include "pitch_controls.hpp"
#include <vector>

namespace boiled_egg::plugin {
// One audio owner; Targets are atomic and may be updated on the UI thread.
// Activate/deactivate require host lifecycle exclusion. Configuration changes
// are pending until a host restart: never allocate/rebuild from process().
class Processor {
public:
 Targets targets;
 ~Processor(){deactivate();}
 Processor()=default;Processor(const Processor&)=delete;Processor& operator=(const Processor&)=delete;
 bool request(unsigned i,float v) noexcept;
 bool request(const Values& v) noexcept;
 bool activate(unsigned rate,unsigned max_block);
 void deactivate() noexcept;
 bool reset() noexcept;
 // CLAP live host edits may stage nonautomatable configuration changes.
 // Other callers retain strict automation-only behavior by default.
 bool process(const float* const* in,float* const* out,unsigned frames,std::span<const Event> events,bool live_configuration=false) noexcept;
 bool is_active() const noexcept {return active_;}
 bool needs_restart() const noexcept {return active_&&!same_configuration(targets.snapshot(),configuration_);}
 void rate_hint(unsigned rate) noexcept {if(!active_)rate_=rate;}
 unsigned latency() const noexcept {return active_?runtime_.realtime_latency_frames:predicted_latency();}
 unsigned tail() const noexcept {return active_?runtime_.realtime_tail_frames:predicted_latency();}
 const char* error() const noexcept;
 boiledegg_handle* handle() noexcept {return core_;}
private:
 bool apply(const Values& v) noexcept;
 bool segment(const float* const* in,float* const* out,unsigned offset,unsigned n) noexcept;
 unsigned predicted_latency() const noexcept;
 boiledegg_handle* core_{};
 boiledegg_runtime_info runtime_{};
 Values configuration_=defaults(),audio_=defaults();
 unsigned rate_{48000},max_block_{},core_block_{},mix_remaining_{},mix_frames_{240};
 std::array<float,4> mix_{1,1,0,0},mix_target_{1,1,0,0},mix_step_{};
 std::vector<float> dry_history_,dry_scratch_,zero_;
 std::uint64_t position_{};
 bool active_{},fault_{};
 std::atomic<unsigned> error_code_{};
};
}
#endif
