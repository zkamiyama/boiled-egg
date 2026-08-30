#include <boiled_egg/boiled_egg.hpp>

#include <algorithm>
#include <cmath>
#include <cstdint>
#include <iostream>
#include <vector>

namespace {
constexpr double kPi = 3.141592653589793238462643383279502884;

std::vector<float> render(uint32_t host_block) {
    constexpr uint32_t sr = 48000;
    constexpr uint32_t total = sr * 2 + 37;
    auto cfg = boiledegg_default_config(sr, 1);
    cfg.max_block_size = 2048;
    boiled_egg::engine e(cfg);
    e.set_time_ratio(1.25f);
    e.set_pitch_semitones(5.0f);

    std::vector<float> input(total);
    for (uint32_t i = 0; i < total; ++i) {
        input[i] = 0.25f * static_cast<float>(std::sin(2.0 * kPi * 223.0 * i / sr))
                 + 0.12f * static_cast<float>(std::sin(2.0 * kPi * 997.0 * i / sr));
        if ((i % 8191u) == 0u) input[i] += 0.35f;
    }

    std::vector<float> outbuf(4096), rendered;
    float* op[1]{outbuf.data()};
    auto drain = [&] {
        while (e.available()) {
            const auto n = e.pull(op, static_cast<uint32_t>(outbuf.size()));
            rendered.insert(rendered.end(), outbuf.begin(), outbuf.begin() + n);
        }
    };

    for (uint32_t pos = 0; pos < total;) {
        const uint32_t n = std::min(host_block, total - pos);
        uint32_t off = 0;
        while (off < n) {
            const float* ip[1]{input.data() + pos + off};
            const auto accepted = e.push(ip, n - off);
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
            const auto n = e.pull(op, static_cast<uint32_t>(outbuf.size()));
            rendered.insert(rendered.end(), outbuf.begin(), outbuf.begin() + n);
        }
    }
    drain();
    return rendered;
}
} // namespace

int main() {
    const auto a = render(64);
    const auto b = render(257);
    const auto c = render(1024);
    if (a.empty() || b.empty() || c.empty()) return 1;
    if (a.size() != b.size() || a.size() != c.size()) {
        std::cerr << "size mismatch\n";
        return 2;
    }
    double max_err_ab = 0.0, max_err_ac = 0.0;
    for (size_t i = 0; i < a.size(); ++i) {
        max_err_ab = std::max(max_err_ab, std::abs(static_cast<double>(a[i] - b[i])));
        max_err_ac = std::max(max_err_ac, std::abs(static_cast<double>(a[i] - c[i])));
    }
    if (max_err_ab > 1e-6 || max_err_ac > 1e-6) {
        std::cerr << "host block-size dependence: " << max_err_ab << ", " << max_err_ac << "\n";
        return 3;
    }
    std::cout << "block-size deterministic, frames=" << a.size() << "\n";
    return 0;
}
