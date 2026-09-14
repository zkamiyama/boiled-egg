#pragma once
#include <algorithm>
#include <cmath>
#include <cstdint>
namespace boiled_egg::research::detail {
// Allocation-free value state. All validation is performed before start().
// Recurrence preserves the legacy ratio-ramp arithmetic; endpoint snaps avoid
// drift after completion. Clamps prevent overshoot on very long trajectories.
struct ratio_ramp {
    double value{1},target{1},step{},factor{1};
    std::uint32_t remaining{},curve{};
    void reset(double v) noexcept {value=target=v;step=0;factor=1;remaining=curve=0;}
    void start(double v,std::uint32_t n,std::uint32_t shape) noexcept {
        target=v;remaining=n;curve=shape;
        if(!n){value=v;step=0;factor=1;return;}
        step=(target-value)/double(n);
        factor=shape?std::exp(std::log(target/value)/double(n)):1.;
    }
    void tick() noexcept {
        if(!remaining)return;
        const double next=remaining==1?target:(curve?value*factor:value+step);
        value=std::clamp(next,std::min(value,target),std::max(value,target));
        --remaining;
    }
};
struct automation_plan {ratio_ramp pitch,time;};
}
