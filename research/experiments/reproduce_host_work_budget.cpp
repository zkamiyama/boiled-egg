// Diagnostic reproducer, not a callback benchmark or a quality score.
// Compile this SAME file against each runtime's static libraries:
// c++ -std=c++20 -O3 -I "$SRC/research/cpp_pv_rt/include" \
//   research/experiments/reproduce_host_work_budget.cpp \
//   "$BUILD/libboiled_egg_research_host.a" \
//   "$BUILD/libboiled_egg_research_multires_rt.a" \
//   "$BUILD/libboiled_egg_research_pv_rt.a" -o budget-reproducer
// The legacy fixed-delay creator avoids conflating work-budget and latency fixes.
// failing_block_start is the first input index of the failing 31-frame call,
// NOT the exact failing sample within that call. -1 means the run completed.
// Exit 2/3 indicates harness failure; a nonzero CSV status is observed DSP failure.
#include "boiled_egg_research_host.h"
#include <array>
#include <iostream>
int main() {
    std::cout << "profile,channels,formant,pitch,failing_block_start,status,frame_overruns,underruns,max_frame_steps,steps_per_input\n";
    for (unsigned profile : {0U, 2U, 3U}) {
        auto config = boiledegg_research_host_default_config(96000, 8, 31);
        config.profile = profile;
        config.formant_mode = BOILEDEGG_RESEARCH_PV_RT_FORMANT_MONOPHONIC;
        config.pitch_ratio = .5F;
        boiledegg_research_pv_rt_result status{};
        auto* handle = boiledegg_research_host_create(&config, &status);
        if (!handle) return 2;
        std::array<std::array<float, 31>, 8> input{}, output{};
        const float* in[8]{};
        float* out[8]{};
        for (unsigned channel = 0; channel < 8; ++channel) {
            in[channel] = input[channel].data();
            out[channel] = output[channel].data();
        }
        unsigned random = 129;
        int failure = -1;
        for (unsigned position = 0; position < 50000; position += 31) {
            for (unsigned channel = 0; channel < 8; ++channel) {
                for (unsigned frame = 0; frame < 31; ++frame) {
                    random = 1664525U * random + 1013904223U;
                    input[channel][frame] = ((position / 127) % 3)
                        ? float(int(random >> 16) - 32768) / 100000.F : 0.F;
                }
            }
            boiledegg_research_host_event event{
                sizeof(event), 13, (position / 31) % 2 ? .5F : 2.F, 0};
            status = boiledegg_research_host_process(handle, in, out, 31, &event, 1);
            if (status) {
                failure = static_cast<int>(position);
                break;
            }
        }
        boiledegg_research_host_stats stats{};
        stats.struct_size = sizeof(stats);
        if (boiledegg_research_host_get_stats(handle, &stats)) {
            boiledegg_research_host_destroy(handle);
            return 3;
        }
        std::cout << profile << ",8,2,0.5," << failure << ',' << status << ','
                  << stats.execution.frame_overruns << ',' << stats.underruns << ','
                  << stats.execution.max_frame_steps << ','
                  << stats.execution.steps_per_input << '\n';
        boiledegg_research_host_destroy(handle);
    }
}
