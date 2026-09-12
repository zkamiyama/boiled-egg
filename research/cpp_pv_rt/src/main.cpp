#include "boiled_egg_pv_rt.h"
#include "wav.hpp"

#include <algorithm>
#include <cmath>
#include <cstdint>
#include <iostream>
#include <limits>
#include <stdexcept>
#include <string>
#include <vector>

int main(int argc, char** argv) {
    try {
        if (argc < 4) {
            std::cerr << "usage: boiled_egg_pv_rt_cli input.wav output.wav --time R "
                         "[--pitch-semitones ST | --pitch-ratio P] "
                         "[--profile general|transient] "
                         "[--formant off|harmonic|monophonic] [--formant-order N] [--formant-gain-db X] "
                         "[--mode classic|locked|transient|fuzzy|fuzzy-noise] [--block N] [--fft N] [--hop N] "
                         "[--transient-floor X] [--transient-sigma X]\n"
                         "note: --mode transient is the low-level phase-reset experiment; "
                         "--profile transient selects the validated 1024/256 phase-locked profile.\n";
            return 2;
        }
        const std::string input_path = argv[1];
        const std::string output_path = argv[2];
        float ratio = 1.0F;
        float pitch_ratio = 1.0F;
        std::uint32_t quality_profile = BOILEDEGG_RESEARCH_PV_RT_PROFILE_GENERAL;
        std::uint32_t formant_mode = BOILEDEGG_RESEARCH_PV_RT_FORMANT_OFF;
        std::uint32_t formant_order = 40U;
        float formant_gain_db = 15.0F;
        std::uint32_t block = 256U;
        std::uint32_t mode_override = std::numeric_limits<std::uint32_t>::max();
        std::uint32_t fft_override = 0U;
        std::uint32_t hop_override = 0U;
        float transient_floor = 0.12F;
        float transient_sigma = 2.5F;
        for (int i = 3; i < argc; ++i) {
            const std::string argument = argv[i];
            if (argument == "--time" && i + 1 < argc) ratio = std::stof(argv[++i]);
            else if (argument == "--pitch-ratio" && i + 1 < argc) pitch_ratio = std::stof(argv[++i]);
            else if (argument == "--pitch-semitones" && i + 1 < argc) pitch_ratio = std::pow(2.0F, std::stof(argv[++i]) / 12.0F);
            else if (argument == "--profile" && i + 1 < argc) {
                const std::string requested = argv[++i];
                if (requested == "general") quality_profile = BOILEDEGG_RESEARCH_PV_RT_PROFILE_GENERAL;
                else if (requested == "transient") quality_profile = BOILEDEGG_RESEARCH_PV_RT_PROFILE_TRANSIENT;
                else throw std::runtime_error("unknown quality profile: " + requested);
            }
            else if (argument == "--formant-order" && i + 1 < argc) formant_order = static_cast<std::uint32_t>(std::stoul(argv[++i]));
            else if (argument == "--formant-gain-db" && i + 1 < argc) formant_gain_db = std::stof(argv[++i]);
            else if (argument == "--formant" && i + 1 < argc) {
                const std::string requested = argv[++i];
                if (requested == "off") formant_mode = BOILEDEGG_RESEARCH_PV_RT_FORMANT_OFF;
                else if (requested == "harmonic") formant_mode = BOILEDEGG_RESEARCH_PV_RT_FORMANT_HARMONIC;
                else if (requested == "monophonic") formant_mode = BOILEDEGG_RESEARCH_PV_RT_FORMANT_MONOPHONIC;
                else throw std::runtime_error("unknown formant mode: " + requested);
            }
            else if (argument == "--block" && i + 1 < argc) block = static_cast<std::uint32_t>(std::stoul(argv[++i]));
            else if (argument == "--fft" && i + 1 < argc) fft_override = static_cast<std::uint32_t>(std::stoul(argv[++i]));
            else if (argument == "--hop" && i + 1 < argc) hop_override = static_cast<std::uint32_t>(std::stoul(argv[++i]));
            else if (argument == "--transient-floor" && i + 1 < argc) transient_floor = std::stof(argv[++i]);
            else if (argument == "--transient-sigma" && i + 1 < argc) transient_sigma = std::stof(argv[++i]);
            else if (argument == "--mode" && i + 1 < argc) {
                const std::string requested = argv[++i];
                if (requested == "classic") mode_override = BOILEDEGG_RESEARCH_PV_RT_CLASSIC;
                else if (requested == "locked") mode_override = BOILEDEGG_RESEARCH_PV_RT_PHASE_LOCKED;
                else if (requested == "transient") mode_override = BOILEDEGG_RESEARCH_PV_RT_TRANSIENT;
                else if (requested == "fuzzy") mode_override = BOILEDEGG_RESEARCH_PV_RT_FUZZY;
                else if (requested == "fuzzy-noise") mode_override = BOILEDEGG_RESEARCH_PV_RT_FUZZY_NOISE;
                else throw std::runtime_error("unknown low-level mode: " + requested);
            } else throw std::runtime_error("unknown argument: " + argument);
        }

        const auto audio = read_wav(input_path);
        const std::size_t input_frames = audio.interleaved.size() / audio.channels;
        auto config = boiledegg_research_pv_rt_default_config(audio.sample_rate, audio.channels, block);
        auto result = boiledegg_research_pv_rt_configure_quality_profile(&config, quality_profile);
        if (result != BOILEDEGG_RESEARCH_PV_RT_OK) {
            throw std::runtime_error(boiledegg_research_pv_rt_result_string(result));
        }
        config.initial_time_ratio = ratio;
        config.initial_pitch_ratio = pitch_ratio;
        config.formant_mode = formant_mode;
        config.formant_cepstral_order = formant_order;
        config.formant_gain_limit_db = formant_gain_db;
        if (mode_override != std::numeric_limits<std::uint32_t>::max()) config.mode = mode_override;
        if (fft_override != 0U) config.fft_size = fft_override;
        if (hop_override != 0U) config.analysis_hop = hop_override;
        config.transient_floor = transient_floor;
        config.transient_sigma = transient_sigma;
        boiledegg_research_pv_rt_handle* handle = boiledegg_research_pv_rt_create(&config, &result);
        if (!handle) throw std::runtime_error(boiledegg_research_pv_rt_result_string(result));

        std::vector<std::vector<float>> input(audio.channels, std::vector<float>(block));
        std::vector<std::vector<float>> output(audio.channels, std::vector<float>(static_cast<std::size_t>(block) * 8U));
        std::vector<const float*> input_ptrs(audio.channels);
        std::vector<float*> output_ptrs(audio.channels);
        for (std::uint16_t channel = 0; channel < audio.channels; ++channel) {
            input_ptrs[channel] = input[channel].data();
            output_ptrs[channel] = output[channel].data();
        }
        wav_audio rendered{audio.sample_rate, audio.channels, {}};
        rendered.interleaved.reserve(static_cast<std::size_t>(std::llround(static_cast<double>(input_frames) * ratio)) * audio.channels);
        const auto drain = [&]() {
            while (boiledegg_research_pv_rt_available(handle) != 0U) {
                const auto count = boiledegg_research_pv_rt_pull(handle, output_ptrs.data(), static_cast<std::uint32_t>(output[0].size()));
                for (std::uint32_t frame = 0; frame < count; ++frame) {
                    for (std::uint16_t channel = 0; channel < audio.channels; ++channel) rendered.interleaved.push_back(output[channel][frame]);
                }
            }
        };
        for (std::size_t position = 0; position < input_frames; position += block) {
            const auto count = static_cast<std::uint32_t>(std::min<std::size_t>(block, input_frames - position));
            for (std::uint16_t channel = 0; channel < audio.channels; ++channel) {
                for (std::uint32_t frame = 0; frame < count; ++frame) input[channel][frame] = audio.interleaved[(position + frame) * audio.channels + channel];
            }
            result = boiledegg_research_pv_rt_push(handle, input_ptrs.data(), count);
            if (result != BOILEDEGG_RESEARCH_PV_RT_OK) throw std::runtime_error(boiledegg_research_pv_rt_result_string(result));
            drain();
        }
        result = boiledegg_research_pv_rt_flush(handle);
        if (result != BOILEDEGG_RESEARCH_PV_RT_OK) throw std::runtime_error(boiledegg_research_pv_rt_result_string(result));
        drain();
        boiledegg_research_pv_rt_destroy(handle);
        write_wav_float32(output_path, rendered);
        return 0;
    } catch (const std::exception& error) {
        std::cerr << error.what() << '\n';
        return 1;
    }
}
