#include "boiled_egg_pv_rt.h"
#include "wav.hpp"

#include <algorithm>
#include <cmath>
#include <cstdint>
#include <iostream>
#include <stdexcept>
#include <string>
#include <vector>

int main(int argc, char** argv) {
    try {
        if (argc < 4) {
            std::cerr << "usage: boiled_egg_pv_rt_cli input.wav output.wav --time R [--mode classic|locked|transient] [--block N] [--fft N] [--hop N] [--transient-floor X] [--transient-sigma X]\n";
            return 2;
        }
        const std::string input_path = argv[1];
        const std::string output_path = argv[2];
        float ratio = 1.0F;
        std::uint32_t block = 256U, mode = BOILEDEGG_RESEARCH_PV_RT_TRANSIENT, fft_size = 2048U, analysis_hop = 256U;
        float transient_floor = 0.12F, transient_sigma = 2.5F;
        for (int i = 3; i < argc; ++i) {
            const std::string argument = argv[i];
            if (argument == "--time" && i + 1 < argc) ratio = std::stof(argv[++i]);
            else if (argument == "--block" && i + 1 < argc) block = static_cast<std::uint32_t>(std::stoul(argv[++i]));
            else if (argument == "--fft" && i + 1 < argc) fft_size = static_cast<std::uint32_t>(std::stoul(argv[++i]));
            else if (argument == "--hop" && i + 1 < argc) analysis_hop = static_cast<std::uint32_t>(std::stoul(argv[++i]));
            else if (argument == "--transient-floor" && i + 1 < argc) transient_floor = std::stof(argv[++i]);
            else if (argument == "--transient-sigma" && i + 1 < argc) transient_sigma = std::stof(argv[++i]);
            else if (argument == "--mode" && i + 1 < argc) {
                const std::string requested = argv[++i];
                if (requested == "classic") mode = BOILEDEGG_RESEARCH_PV_RT_CLASSIC;
                else if (requested == "locked") mode = BOILEDEGG_RESEARCH_PV_RT_PHASE_LOCKED;
                else if (requested == "transient") mode = BOILEDEGG_RESEARCH_PV_RT_TRANSIENT;
                else throw std::runtime_error("unknown mode: " + requested);
            } else throw std::runtime_error("unknown argument: " + argument);
        }
        const auto audio = read_wav(input_path);
        const std::size_t input_frames = audio.interleaved.size() / audio.channels;
        auto config = boiledegg_research_pv_rt_default_config(audio.sample_rate, audio.channels, block);
        config.initial_time_ratio = ratio; config.mode = mode; config.fft_size = fft_size; config.analysis_hop = analysis_hop;
        config.transient_floor = transient_floor; config.transient_sigma = transient_sigma;
        boiledegg_research_pv_rt_result result{};
        auto* handle = boiledegg_research_pv_rt_create(&config, &result);
        if (!handle) throw std::runtime_error(boiledegg_research_pv_rt_result_string(result));
        std::vector<std::vector<float>> input(audio.channels, std::vector<float>(block));
        std::vector<std::vector<float>> output(audio.channels, std::vector<float>(static_cast<std::size_t>(block) * 8U));
        std::vector<const float*> input_ptrs(audio.channels); std::vector<float*> output_ptrs(audio.channels);
        for (std::uint16_t channel = 0; channel < audio.channels; ++channel) { input_ptrs[channel] = input[channel].data(); output_ptrs[channel] = output[channel].data(); }
        wav_audio rendered{audio.sample_rate, audio.channels, {}};
        rendered.interleaved.reserve(static_cast<std::size_t>(std::llround(static_cast<double>(input_frames) * ratio)) * audio.channels);
        const auto drain = [&]() {
            while (boiledegg_research_pv_rt_available(handle) != 0U) {
                const auto count = boiledegg_research_pv_rt_pull(handle, output_ptrs.data(), static_cast<std::uint32_t>(output[0].size()));
                for (std::uint32_t frame = 0; frame < count; ++frame) for (std::uint16_t channel = 0; channel < audio.channels; ++channel) rendered.interleaved.push_back(output[channel][frame]);
            }
        };
        for (std::size_t position = 0; position < input_frames; position += block) {
            const auto count = static_cast<std::uint32_t>(std::min<std::size_t>(block, input_frames - position));
            for (std::uint16_t channel = 0; channel < audio.channels; ++channel) for (std::uint32_t frame = 0; frame < count; ++frame) input[channel][frame] = audio.interleaved[(position + frame) * audio.channels + channel];
            result = boiledegg_research_pv_rt_push(handle, input_ptrs.data(), count);
            if (result != BOILEDEGG_RESEARCH_PV_RT_OK) throw std::runtime_error(boiledegg_research_pv_rt_result_string(result));
            drain();
        }
        result = boiledegg_research_pv_rt_flush(handle);
        if (result != BOILEDEGG_RESEARCH_PV_RT_OK) throw std::runtime_error(boiledegg_research_pv_rt_result_string(result));
        drain(); boiledegg_research_pv_rt_destroy(handle); write_wav_float32(output_path, rendered); return 0;
    } catch (const std::exception& error) { std::cerr << error.what() << '\n'; return 1; }
}
