#include "power_weights.hpp"
extern "C" unsigned hpss_grouped_power(std::size_t frames,const std::int64_t* source,
    const std::int64_t* target,std::size_t count,const double* window,unsigned length,
    std::size_t output_frames,double* power,std::int64_t* keys,double* weights){
    return boiled_egg::research::hpss::grouped_power(frames,source,target,count,
        window,length,output_frames,power,keys,weights)?1U:0U;
}
