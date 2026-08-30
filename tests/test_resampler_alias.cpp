#include <boiled_egg/boiled_egg.hpp>

#include <algorithm>
#include <cmath>
#include <cstdint>
#include <iostream>
#include <vector>

namespace {
constexpr double kPi = 3.141592653589793238462643383279502884;

std::vector<float> render_tone(double hz, float pitch_st) {
    constexpr uint32_t sr = 48000;
    constexpr uint32_t total = sr * 3;
    constexpr uint32_t block = 128;
    boiled_egg::engine e(sr, 1);
    e.set_pitch_semitones(pitch_st);
    e.set_time_ratio(1.0f);

    std::vector<float> in(block), out(block * 4);
    std::vector<float> rendered;
    rendered.reserve(total + sr);
    const float* ip[1]{in.data()};
    float* op[1]{out.data()};

    auto drain = [&] {
        while (e.available()) {
            const auto n = e.pull(op, static_cast<uint32_t>(out.size()));
            rendered.insert(rendered.end(), out.begin(), out.begin() + n);
        }
    };

    for (uint32_t pos = 0; pos < total;) {
        const uint32_t n = std::min(block, total - pos);
        for (uint32_t i = 0; i < n; ++i) {
            in[i] = 0.4f * static_cast<float>(std::sin(2.0 * kPi * hz * (pos + i) / sr));
        }
        uint32_t off = 0;
        while (off < n) {
            const float* p[1]{in.data() + off};
            const auto accepted = e.push(p, n - off);
            if (accepted == 0) return {};
            off += accepted;
            drain();
        }
        pos += n;
    }
    e.flush();
    for (int guard = 0; guard < 10000 && !e.drained(); ++guard) {
        drain();
        if (!e.available()) {
            const auto n = e.pull(op, static_cast<uint32_t>(out.size()));
            rendered.insert(rendered.end(), out.begin(), out.begin() + n);
        }
    }
    drain();
    return rendered;
}

double middle_rms(const std::vector<float>& x) {
    constexpr size_t trim = 24000;
    if (x.size() <= 2 * trim) return 0.0;
    double sum = 0.0;
    for (size_t i = trim; i < x.size() - trim; ++i) sum += static_cast<double>(x[i]) * x[i];
    return std::sqrt(sum / static_cast<double>(x.size() - 2 * trim));
}
} // namespace

int main() {
    const auto pass = render_tone(10000.0, 12.0f);
    const auto stop = render_tone(14000.0, 12.0f);
    if (pass.empty() || stop.empty()) return 1;
    const double pass_rms = middle_rms(pass);
    const double stop_rms = middle_rms(stop);
    if (pass_rms < 0.10) return 2;
    const double ratio = stop_rms / std::max(pass_rms, 1e-12);
    if (ratio > 0.01) return 3;
    std::cout << "pass_rms=" << pass_rms << " stop_rms=" << stop_rms
              << " rejection_db=" << 20.0 * std::log10(std::max(ratio, 1e-12)) << "\n";
    return 0;
}
