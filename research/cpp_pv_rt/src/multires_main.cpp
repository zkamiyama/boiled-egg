#include "boiled_egg_multires_rt.h"
#include "wav.hpp"
#include "feature_cli.hpp"

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
            std::cerr << "usage: boiled_egg_multires_rt_cli input.wav output.wav --time R "
                         "[--pitch-semitones ST | --pitch-ratio P] "
                         "[--formant off|harmonic|monophonic] [--block N] "
                         "[--crossover HZ] [--taps N]\n";
            std::cerr << "features: [--timing legacy|centered] [--rate-policy fixed|scaled] "
                         "[--formant-ratio R | --formant-semitones ST]\n";
            return 2;
        }
        const std::string input_path = argv[1];
        const std::string output_path = argv[2];
        float time_ratio = 1.0F;
        float pitch_ratio = 1.0F;
        std::uint32_t formant_mode = BOILEDEGG_RESEARCH_PV_RT_FORMANT_OFF;
        std::uint32_t block = 256U;
        float crossover = 6500.0F;
        std::uint32_t taps = 129U;
        auto features = boiledegg_research_default_features();
        for (int i = 3; i < argc; ++i) {
            if (parse_feature_option(i, argc, argv, features)) continue;
            const std::string argument = argv[i];
            if (argument == "--time" && i + 1 < argc) time_ratio = std::stof(argv[++i]);
            else if (argument == "--pitch-ratio" && i + 1 < argc) pitch_ratio = std::stof(argv[++i]);
            else if (argument == "--pitch-semitones" && i + 1 < argc)
                pitch_ratio = std::pow(2.0F, std::stof(argv[++i]) / 12.0F);
            else if (argument == "--block" && i + 1 < argc) block = static_cast<std::uint32_t>(std::stoul(argv[++i]));
            else if (argument == "--crossover" && i + 1 < argc) crossover = std::stof(argv[++i]);
            else if (argument == "--taps" && i + 1 < argc) taps = static_cast<std::uint32_t>(std::stoul(argv[++i]));
            else if (argument == "--formant" && i + 1 < argc) {
                const std::string requested = argv[++i];
                if (requested == "off") formant_mode = BOILEDEGG_RESEARCH_PV_RT_FORMANT_OFF;
                else if (requested == "harmonic") formant_mode = BOILEDEGG_RESEARCH_PV_RT_FORMANT_HARMONIC;
                else if (requested == "monophonic") formant_mode = BOILEDEGG_RESEARCH_PV_RT_FORMANT_MONOPHONIC;
                else throw std::runtime_error("unknown formant mode: " + requested);
            } else {
                throw std::runtime_error("unknown argument: " + argument);
            }
        }

        const auto audio = read_wav(input_path);
        const std::size_t input_frames = audio.interleaved.size() / audio.channels;
        auto config = boiledegg_research_multires_rt_default_config(audio.sample_rate, audio.channels, block);
        config.initial_time_ratio = time_ratio;
        config.initial_pitch_ratio = pitch_ratio;
        config.formant_mode = formant_mode;
        config.crossover_hz = crossover;
        config.fir_taps = taps;
        boiledegg_research_pv_rt_result result{};
        auto* handle = boiledegg_research_multires_rt_create_ex(&config, &features, &result);
        if (handle == nullptr) throw std::runtime_error(boiledegg_research_pv_rt_result_string(result));

        std::vector<std::vector<float>> input(audio.channels, std::vector<float>(block));
        std::vector<std::vector<float>> output(audio.channels, std::vector<float>(static_cast<std::size_t>(block) * 16U));
        std::vector<const float*> input_ptrs(audio.channels);
        std::vector<float*> output_ptrs(audio.channels);
        for (std::uint16_t channel = 0; channel < audio.channels; ++channel) {
            input_ptrs[channel] = input[channel].data();
            output_ptrs[channel] = output[channel].data();
        }

        wav_audio rendered{audio.sample_rate, audio.channels, {}};
        rendered.interleaved.reserve(
            static_cast<std::size_t>(std::llround(static_cast<double>(input_frames) * time_ratio)) * audio.channels);
        const auto drain = [&]() {
            while (boiledegg_research_multires_rt_available(handle) != 0U) {
                const auto count = boiledegg_research_multires_rt_pull(
                    handle, output_ptrs.data(), static_cast<std::uint32_t>(output[0].size()));
                for (std::uint32_t frame = 0U; frame < count; ++frame) {
                    for (std::uint16_t channel = 0U; channel < audio.channels; ++channel) {
                        rendered.interleaved.push_back(output[channel][frame]);
                    }
                }
            }
        };

        for (std::size_t position = 0U; position < input_frames; position += block) {
            const auto count = static_cast<std::uint32_t>(std::min<std::size_t>(block, input_frames - position));
            for (std::uint16_t channel = 0; channel < audio.channels; ++channel) {
                for (std::uint32_t frame = 0U; frame < count; ++frame) {
                    input[channel][frame] = audio.interleaved[(position + frame) * audio.channels + channel];
                }
            }
            result = boiledegg_research_multires_rt_push(handle, input_ptrs.data(), count);
            if (result != BOILEDEGG_RESEARCH_PV_RT_OK) throw std::runtime_error(boiledegg_research_pv_rt_result_string(result));
            drain();
        }
        drain();
        result = boiledegg_research_multires_rt_flush(handle);
        if (result != BOILEDEGG_RESEARCH_PV_RT_OK) throw std::runtime_error(boiledegg_research_pv_rt_result_string(result));
        drain();
        const auto expected = static_cast<std::size_t>(std::llround(static_cast<double>(input_frames) * time_ratio));
        if (rendered.interleaved.size() != expected * audio.channels) {
            throw std::runtime_error("multi-resolution exact-duration contract failed");
        }
        boiledegg_research_multires_rt_destroy(handle);
        write_wav_float32(output_path, rendered);
        return 0;
    } catch (const std::exception& error) {
        std::cerr << error.what() << '\n';
        return 1;
    }
}
