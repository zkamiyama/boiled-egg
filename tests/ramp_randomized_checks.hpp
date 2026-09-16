#ifndef BOILED_EGG_TEST_RAMP_RANDOMIZED_CHECKS_HPP
#define BOILED_EGG_TEST_RAMP_RANDOMIZED_CHECKS_HPP
#include <boiled_egg/boiled_egg.hpp>
#include <algorithm>
#include <array>
#include <cmath>
#include <cstdint>
#include <limits>
#include <stdexcept>
#include <vector>

namespace boiled_egg::test::ramp_randomized {
inline void require(bool ok, const char* message) {
    if (!ok) throw std::runtime_error(message);
}
// Independent closed-form oracle: no imported private ramp code or recurrence.
struct curve {
    long double current{1}, origin{1}, target{1};
    std::uint32_t length{}, elapsed{}, shape{};
    void start(float value, std::uint32_t n, std::uint32_t kind) {
        origin = current; target = value; length = n; elapsed = 0; shape = kind;
        if (!n) current = target;
    }
    void tick() {
        if (elapsed >= length) return;
        ++elapsed;
        const long double f = static_cast<long double>(elapsed) / length;
        current = elapsed == length ? target : shape
            ? origin * std::exp(std::log(target / origin) * f)
            : origin + (target - origin) * f;
    }
    std::uint32_t remaining() const { return length - elapsed; }
};
struct checkpoint {
    long double pitch, time, output, intermediate;
    std::uint32_t pitch_remaining, time_remaining;
};
struct plan {
    std::vector<boiledegg_ramp_event> events;
    std::vector<checkpoint> expected;
};
inline plan make_plan(std::uint32_t frames, std::uint32_t seed) {
    plan result;
    auto draw = [&] { seed = seed * 1664525U + 1013904223U; return seed; };
    constexpr std::array<std::uint32_t, 7> lengths{0, 1, 2, 31, 257, 1500,
        std::numeric_limits<std::uint32_t>::max()};
    for (std::uint32_t at = 0; at < frames; at += 17U + draw() % 193U) {
        for (std::uint32_t id : {1U, 2U}) {
            const float target = .5F + static_cast<float>(draw() % 15U) / 16.F;
            result.events.push_back({sizeof(boiledegg_ramp_event), at, id,
                lengths[draw() % lengths.size()], draw() % 2U, target, {0, 0}});
        }
        // Repeated parameter at the same offset exercises deterministic order.
        if (draw() % 3U == 0U) {
            auto event = result.events.back(); event.duration_frames = lengths[draw() % lengths.size()];
            result.events.push_back(event);
        }
    }
    // Every target <=1.375: the rectangular coupled bound stays below two.
    curve p, t; long double w = 0, v = 0; std::size_t event = 0;
    result.expected.push_back({1, 1, 0, 0, 0, 0});
    for (std::uint32_t n = 0; n < frames; ++n) {
        while (event < result.events.size() && result.events[event].sample_offset == n) {
            const auto& e = result.events[event++];
            (e.parameter_id == 1U ? t : p).start(e.value, e.duration_frames, e.curve);
        }
        p.tick(); t.tick(); w += t.current; v += t.current * p.current;
        result.expected.push_back({p.current, t.current, w, v, p.remaining(), t.remaining()});
    }
    return result;
}
using audio = std::array<std::vector<float>, 2>;
inline audio run(const plan& trajectory, unsigned rate, unsigned quality, unsigned policy,
                 unsigned block, bool stall, std::uint64_t& checked) {
    const auto frames = static_cast<unsigned>(trajectory.expected.size() - 1U);
    auto config = boiledegg_default_config(rate, 2); config.max_block_size = 257;
    auto backend = boiledegg_default_backend_config();
    backend.backend_id = BOILEDEGG_BACKEND_PHASE_VOCODER;
    backend.flags = BOILEDEGG_BACKEND_ALLOW_EXPERIMENTAL | BOILEDEGG_BACKEND_CONTINUOUS_PITCH |
                    BOILEDEGG_BACKEND_CONTINUOUS_TIME;
    backend.io_contract = BOILEDEGG_IO_STREAMING; backend.quality_mode = quality; backend.formant_policy = policy;
    boiled_egg::engine engine(config, backend);
    audio input{std::vector<float>(frames), std::vector<float>(frames)}, output;
    for (unsigned n = 0; n < frames; ++n) {
        input[0][n] = .13F * std::sin(.0571F * static_cast<float>(n));
        input[1][n] = -.5F * input[0][n];
    }
    std::array<float, 4096> left{}, right{}; float* out[]{left.data(), right.data()};
    auto drain = [&] {
        while (engine.available()) {
            const auto n = engine.pull(out, static_cast<unsigned>(left.size()));
            require(n > 0, "random ramp drain makes progress");
            output[0].insert(output[0].end(), left.begin(), left.begin() + n);
            output[1].insert(output[1].end(), right.begin(), right.begin() + n);
        }
    };
    unsigned at = 0, pressure = 0;
    while (at < frames) {
        const auto count = std::min(block, frames - at);
        std::array<boiledegg_ramp_event, BOILEDEGG_MAX_RAMP_EVENTS> batch{}; unsigned size = 0;
        for (auto event : trajectory.events) {
            if (event.sample_offset >= at && event.sample_offset < at + count) {
                require(size < batch.size(), "random batch capacity"); event.sample_offset -= at; batch[size++] = event;
            }
        }
        const float* in[]{input[0].data() + at, input[1].data() + at};
        const auto used = engine.push_ramps(in, count, std::span(batch.data(), size));
        require(used <= count, "accepted prefix in range");
        if (used < count) ++pressure;
        at += used;
        const auto actual = engine.automation_info(); const auto& expected = trajectory.expected[at];
        require(actual.input_frames == at, "random accepted clock");
        require(std::abs(actual.effective_pitch_ratio - expected.pitch) < 3e-9L &&
                std::abs(actual.effective_time_ratio - expected.time) < 3e-9L, "random interrupted closed-form controls");
        require(std::abs(actual.output_position - expected.output) < 2e-5L &&
                std::abs(actual.intermediate_position - expected.intermediate) < 2e-5L, "random independent dual integrals");
        require(actual.pitch_remaining_frames == expected.pitch_remaining &&
                actual.time_remaining_frames == expected.time_remaining, "random remaining durations");
        ++checked;
        if (!stall || used < count) {
            drain(); const auto after = engine.automation_info();
            require(after.input_frames == actual.input_frames && after.output_position == actual.output_position &&
                    after.intermediate_position == actual.intermediate_position, "pull must not advance randomized clocks");
        }
    }
    drain(); const auto before = engine.automation_info(); engine.flush(); drain(); const auto after = engine.automation_info();
    require(before.input_frames == after.input_frames && before.output_position == after.output_position &&
            before.pitch_remaining_frames == after.pitch_remaining_frames && before.time_remaining_frames == after.time_remaining_frames,
            "random EOS does not finish remaining ramps");
    require(engine.drained() && output[0].size() == static_cast<std::size_t>(std::floor(trajectory.expected.back().output + .5L)),
            "random independent EOS duration");
    if (stall) require(pressure > 0, "randomized backpressure was actually exercised");
    for (std::size_t n = 0; n < output[0].size(); ++n)
        require(std::isfinite(output[0][n]) && std::isfinite(output[1][n]) &&
                std::abs(output[1][n] + .5F * output[0][n]) < 3e-6F, "random finite linked output");
    return output;
}
inline std::uint64_t verify() {
    std::uint64_t checked = 0;
    for (unsigned rate : {48000U, 96000U}) for (unsigned quality : {0U, 1U}) for (unsigned policy : {0U, 1U, 2U}) {
        const auto trajectory = make_plan(12017, 20260915U + rate + 13U * quality + policy);
        require(run(trajectory, rate, quality, policy, 31, false, checked) ==
                run(trajectory, rate, quality, policy, 257, false, checked), "random waveform partition equality");
    }
    const auto long_plan = make_plan(80017, 99231);
    require(run(long_plan, 48000, 1, 1, 31, true, checked) ==
            run(long_plan, 48000, 1, 1, 257, true, checked), "random accepted-prefix retry equivalence");
    return checked;
}
}
#endif
