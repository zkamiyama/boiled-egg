#ifndef BOILED_EGG_PRIVATE_PITCH_TIMELINE_HPP
#define BOILED_EGG_PRIVATE_PITCH_TIMELINE_HPP
#include "automation_curve.hpp"
#include <algorithm>
#include <cmath>
#include <cstddef>
#include <cstdint>
#include <vector>
namespace boiled_egg::research::detail {
// Preallocated source-clock map. Position is V(u)=sum(T*p) and output is
// W(u)=sum(T). Samples use the post-tick effective control (right endpoint).
class pitch_timeline {
public:
    struct node {double position{};float pitch{1},formant{1};double output{};};
    void prepare(std::size_t capacity,std::uint32_t rate,float time,float pitch,float formant) {
        nodes_.resize(capacity);ramp_frames_=std::max(1U,rate/100U);
        plan_.time.reset(time);reset(pitch,formant);
    }
    [[nodiscard]] bool enabled() const noexcept {return !nodes_.empty();}
    void reset(float pitch,float formant) noexcept {
        written_=0;position_=output_=0;plan_.pitch.reset(pitch);
        plan_.time.reset(plan_.time.target);
        if(enabled())nodes_[0]={0,pitch,formant,0};
    }
    void target(float pitch) noexcept {
        if(plan_.pitch.target==pitch)return;
        plan_.pitch.start(pitch,written_?ramp_frames_:0U,0);
    }
    void ramp(float value,std::uint32_t frames,std::uint32_t curve) noexcept {plan_.pitch.start(value,frames,curve);}
    [[nodiscard]] double effective_pitch() const noexcept {return plan_.pitch.value;}
    [[nodiscard]] std::uint32_t remaining() const noexcept {return plan_.pitch.remaining;}
    [[nodiscard]] const automation_plan& plan() const noexcept {return plan_;}
    [[nodiscard]] bool can_append(std::uint64_t oldest) const noexcept {
        return oldest<=written_ && written_+1U-oldest<nodes_.size();
    }
    void append(float formant,bool advance=true) noexcept {
        if(advance){plan_.pitch.tick();plan_.time.tick();}
        nodes_[static_cast<std::size_t>(written_%nodes_.size())]=
            {position_,static_cast<float>(plan_.pitch.value),formant,output_};
        position_+=plan_.time.value*plan_.pitch.value;output_+=plan_.time.value;++written_;
        nodes_[static_cast<std::size_t>(written_%nodes_.size())]=
            {position_,static_cast<float>(plan_.pitch.value),formant,output_};
    }
    [[nodiscard]] bool contains(std::uint64_t i) const noexcept {return i<=written_ && written_-i<nodes_.size();}
    [[nodiscard]] node at(std::uint64_t i) const noexcept {return nodes_[static_cast<std::size_t>(i%nodes_.size())];}
    [[nodiscard]] double position(double input) const noexcept {
        const auto i=static_cast<std::uint64_t>(input);const auto a=at(i);
        const double fraction=input-static_cast<double>(i);
        return fraction==0?a.position:a.position+fraction*(at(i+1U).position-a.position);
    }
    [[nodiscard]] double end_position() const noexcept {return position_;}
    [[nodiscard]] double end_output() const noexcept {return output_;}
    [[nodiscard]] std::uint64_t written() const noexcept {return written_;}
private:
    std::vector<node> nodes_;
    std::uint64_t written_{};
    std::uint32_t ramp_frames_{1};
    double position_{},output_{};
    automation_plan plan_;
};
}
#endif
