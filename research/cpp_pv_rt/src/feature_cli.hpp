#ifndef BOILED_EGG_FEATURE_CLI_HPP
#define BOILED_EGG_FEATURE_CLI_HPP
#include "boiled_egg_research_features.h"
#include <cmath>
#include <stdexcept>
#include <string>
inline bool parse_feature_option(int& i, int argc, char** argv, boiledegg_research_features& f) {
    const std::string option = argv[i];
    if (option != "--timing" && option != "--rate-policy" && option != "--formant-ratio"
        && option != "--formant-semitones") return false;
    if (i + 1 >= argc) throw std::runtime_error("missing value for " + option);
    const std::string value = argv[++i];
    if (option == "--timing") {
        if (value == "legacy") f.timing_policy = BOILEDEGG_RESEARCH_TIMING_LEGACY;
        else if (value == "centered") f.timing_policy = BOILEDEGG_RESEARCH_TIMING_CENTERED;
        else throw std::runtime_error("invalid timing policy");
    } else if (option == "--rate-policy") {
        if (value == "fixed") f.rate_policy = BOILEDEGG_RESEARCH_RATE_FIXED;
        else if (value == "scaled") f.rate_policy = BOILEDEGG_RESEARCH_RATE_SCALED;
        else throw std::runtime_error("invalid rate policy");
    } else {
        std::size_t end = 0;
        const float number = std::stof(value, &end);
        if (end != value.size() || !std::isfinite(number)) throw std::runtime_error("invalid formant value");
        f.initial_formant_ratio = option == "--formant-ratio" ? number : std::exp2(number/12.0F);
    }
    return true;
}
#endif
