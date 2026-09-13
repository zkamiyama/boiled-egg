#ifndef BOILED_EGG_EXECUTION_CLI_HPP
#define BOILED_EGG_EXECUTION_CLI_HPP
#include "boiled_egg_research_execution.h"
#include <stdexcept>
#include <string>
inline bool parse_execution_option(int& i,int argc,char** argv,boiledegg_research_execution& e) {
    const std::string option=argv[i];
    if (option!="--execution" && option!="--simd") return false;
    if (i+1>=argc) throw std::runtime_error("missing value for "+option);
    const std::string value=argv[++i];
    if (option=="--execution") {
        if (value=="immediate") e.scheduled=0;
        else if (value=="scheduled") e.scheduled=1;
        else throw std::runtime_error("invalid execution policy");
    } else {
        if (value=="off") e.simd=0;
        else if (value=="on") e.simd=1;
        else throw std::runtime_error("invalid SIMD policy");
    }
    return true;
}
#endif
