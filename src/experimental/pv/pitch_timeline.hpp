#ifndef BOILED_EGG_PRIVATE_PITCH_TIMELINE_HPP
#define BOILED_EGG_PRIVATE_PITCH_TIMELINE_HPP
#include <algorithm>
#include <cmath>
#include <cstddef>
#include <cstdint>
#include <vector>

namespace boiled_egg::research::detail {
// Source-clock map V(u)=integral(time_ratio*pitch(u),du). Both frame placement
// and resampler lookup use this SAME map, never the control value at callback
// execution time. Storage is allocated at construction; append/read are bounded.
// A target step ramps linearly in ratio over 10ms of INPUT, independent of host
// block partition. No instantaneous jump in position and no ring of UI events.
class pitch_timeline {
public:
    struct node { double position{}; float pitch{1.0F},formant{1.0F}; };
    void prepare(std::size_t capacity,std::uint32_t rate,float time,float pitch,float formant) {
        nodes_.resize(capacity);ramp_frames_=std::max(1U,rate/100U);time_=time;reset(pitch,formant);
    }
    [[nodiscard]] bool enabled() const noexcept { return !nodes_.empty(); }
    void reset(float pitch,float formant) noexcept {
        written_=0;position_=0;pitch_=target_=pitch;step_=0;remaining_=0;
        if(enabled())nodes_[0]={0,pitch,formant};
    }
    void target(float pitch) noexcept {
        if(target_==pitch)return;
        target_=pitch;
        if(!written_){pitch_=target_;step_=0;remaining_=0;return;}
        remaining_=ramp_frames_;step_=(target_-pitch_)/static_cast<double>(remaining_);
    }
    [[nodiscard]] bool can_append(std::uint64_t oldest) const noexcept {
        return written_+1U-oldest<nodes_.size();
    }
    void append(float formant) noexcept {
        if(remaining_){pitch_=remaining_==1?target_:pitch_+step_;--remaining_;}
        auto& current=nodes_[static_cast<std::size_t>(written_%nodes_.size())];
        current={position_,static_cast<float>(pitch_),formant};
        position_+=time_*pitch_;++written_;
        nodes_[static_cast<std::size_t>(written_%nodes_.size())]={position_,static_cast<float>(pitch_),formant};
    }
    [[nodiscard]] bool contains(std::uint64_t i) const noexcept {
        return i<=written_ && written_-i<nodes_.size();
    }
    [[nodiscard]] node at(std::uint64_t i) const noexcept { return nodes_[static_cast<std::size_t>(i%nodes_.size())]; }
    [[nodiscard]] double position(double input) const noexcept {
        const auto i=static_cast<std::uint64_t>(input);const auto a=at(i);
        // At an integer no future control or sample is needed.
        const double fraction=input-static_cast<double>(i);
        return fraction==0?a.position:a.position+fraction*(at(i+1U).position-a.position);
    }
    [[nodiscard]] double end_position() const noexcept { return position_; }
    [[nodiscard]] std::uint64_t written() const noexcept { return written_; }
private:
    std::vector<node> nodes_;
    std::uint64_t written_{};
    std::uint32_t ramp_frames_{1},remaining_{};
    double position_{},pitch_{1},target_{1},step_{},time_{1};
};
}
#endif
