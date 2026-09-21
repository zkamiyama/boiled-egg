#include <algorithm>
#include <stdexcept>
#include <boiled_egg/boiled_egg.hpp>
#include <array>
#include <cmath>
#include <iostream>
#include <type_traits>
#include <utility>
static_assert(!std::is_copy_constructible_v<boiled_egg::engine>);
static_assert(std::is_nothrow_move_constructible_v<boiled_egg::engine>);
int main() { try {
    for (auto rate : {48000u, 96000u}) for (auto block : {32u, 64u}) {
        auto cfg = boiledegg_default_config(rate, 1); cfg.max_block_size = block;
        boiled_egg::engine original(cfg);
        auto engine = std::move(original);
        auto state = engine.parameter_state();
        engine.set_parameter_state(state);
        std::array<float, 8192> source{}, output{}, previous{};
        for (unsigned i=0; i<source.size(); ++i) source[i] = float(int(i%257)-128)/512.f;
        for (unsigned repeat=0; repeat<2; ++repeat) {
            if (repeat) engine.reset();
            unsigned count=0;
            auto pull = [&] {
                while (engine.available()) {
                    std::array<float,64> scratch{}; float* out[] = {scratch.data()};
                    auto n = engine.pull(out,block);
                    if (!n || count+n>output.size()) throw std::runtime_error("invalid output progress");
                    std::copy_n(scratch.begin(), n, output.begin()+count); count+=n;
                }
            };
            for (unsigned i=0; i<source.size(); i+=block) {
                const float* in[] = {source.data()+i};
                if (engine.push(in,block)!=block) return 1;
                pull();
            }
            engine.flush(); pull();
            if (!engine.drained() || count!=source.size()) return 2;
            double energy=0, error=0;
            for (unsigned i=0; i<count; ++i) {
                if (!std::isfinite(output[i])) return 3;
                error=std::max(error,std::abs(double(output[i])-source[i]));
                energy+=double(output[i])*output[i];
            }
            if (energy<1 || error>3e-6 || (repeat && output!=previous)) return 4;
            previous=output;
            std::cout << "rate=" << rate << " block=" << block << " frames=" << count
                      << " repeat=" << repeat << " max_error=" << error << " energy=" << energy << '\n';
        }
    }
    return 0;
} catch (const std::exception& e) { std::cerr << e.what() << '\n'; return 5; } }
