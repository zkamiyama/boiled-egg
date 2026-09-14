#ifndef BOILED_EGG_BENCH_RT_AUDIT_PROTOCOL_HPP
#define BOILED_EGG_BENCH_RT_AUDIT_PROTOCOL_HPP
#include <algorithm>
#include <cstdint>
#include <limits>
#include <stdexcept>
#include <string_view>

namespace boiled_egg::bench {
// Diagnostic timing only. Never include this header in the processing library.
using ns = std::int64_t;
enum class bracket { legacy, cpu, wall };
inline bracket parse_bracket(std::string_view s) {
    if (s=="legacy") return bracket::legacy;
    if (s=="cpu") return bracket::cpu;
    if (s=="wall") return bracket::wall;
    throw std::invalid_argument("bracket must be legacy, cpu or wall");
}
struct interval { ns cpu{-1}, wall{-1}; };
// Legacy measures wall-clock read overhead INSIDE its CPU bracket. Separate
// passes isolate the observer, rather than subtracting independent percentiles.
// A CPU clock reading still has its own boundary overhead in the cpu-only pass.
template<class Clock, class Work>
interval measure(Clock& clock, Work&& work, bracket kind) {
    interval value;
    if (kind==bracket::legacy) {
        const ns c0=clock.cpu(), w0=clock.wall();
        work();
        const ns w1=clock.wall(), c1=clock.cpu();
        value={c1-c0,w1-w0};
    } else if(kind==bracket::cpu) {
        const ns start=clock.cpu(); work(); value.cpu=clock.cpu()-start;
    } else {
        const ns start=clock.wall(); work(); value.wall=clock.wall()-start;
    }
    if ((kind!=bracket::wall && value.cpu<0) || (kind!=bracket::cpu && value.wall<0))
        throw std::runtime_error("nonmonotonic measurement");
    return value;
}
// Rational frame time: no cumulative truncation drift at e.g.44.1/96 kHz.
// Bounds are deliberately narrower than uint64; callers reject invalid inputs.
inline ns frame_time(std::uint64_t frames, std::uint32_t rate) {
    if (!rate || frames>100000000000ULL) throw std::invalid_argument("frame clock bounds");
    const auto sec=frames/rate, remainder=frames%rate;
    if (sec>static_cast<std::uint64_t>(std::numeric_limits<ns>::max()/1000000000LL)-1)
        throw std::overflow_error("frame clock overflow");
    return static_cast<ns>(sec*1000000000ULL+remainder*1000000000ULL/rate);
}
inline ns release_at(ns epoch, std::uint64_t index, std::uint32_t block, std::uint32_t rate) {
    if (epoch<0 || !block || index>1000000 || block>16384)
        throw std::invalid_argument("release clock bounds");
    const ns offset=frame_time(index*block,rate);
    if (epoch>std::numeric_limits<ns>::max()-offset) throw std::overflow_error("release overflow");
    return epoch+offset;
}
struct periodic_result { ns wake_late{}, response{}, slack{}; bool missed{}; };
inline periodic_result classify(ns release, ns next_release, ns wake, ns finished) {
    if (next_release<=release || wake<release || finished<wake)
        throw std::invalid_argument("invalid release timeline");
    return {wake-release, finished-release, next_release-finished, finished>next_release};
}
// Beyond declared fixed latency and a half-second of actual audio processing;
// iteration count alone is not a sample-rate/block-independent warmup policy.
inline std::uint32_t warmup_calls(std::uint32_t requested, std::uint32_t latency,
                                  std::uint32_t rate, std::uint32_t block) {
    if (!rate || !block || requested>100000) throw std::invalid_argument("warmup bounds");
    const auto frames=std::uint64_t(latency)+(rate+1U)/2U;
    const auto required=(frames+block-1U)/block;
    if (required>100000) throw std::invalid_argument("warmup too long");
    return std::max(requested,static_cast<std::uint32_t>(required));
}
}
#endif
