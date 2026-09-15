#ifndef BOILED_EGG_RESEARCH_HPSS_POWER_WEIGHTS_HPP
#define BOILED_EGG_RESEARCH_HPSS_POWER_WEIGHTS_HPP
#include <algorithm>
#include <cmath>
#include <cstddef>
#include <cstdint>
#include <limits>
namespace boiled_egg::research::hpss {
// Expected white-input variance of the OLA numerator. Weights referencing the
// SAME source sample must sum before squaring. Different source samples are
// treated as uncorrelated: explicitly not a colored/tonal power guarantee.
// All output/scratch buffers are caller-owned and nonoverlapping. No allocation.
// Monotone source-minus-target offsets ensure identical groups are contiguous.
inline bool grouped_power(std::size_t frames,const std::int64_t* source,
                          const std::int64_t* target,std::size_t count,
                          const double* window,unsigned length,
                          std::size_t output_frames,double* power,
                          std::int64_t* last_key,double* group_weight) noexcept {
    constexpr auto limit=std::numeric_limits<std::int64_t>::max()/4;
    if(!length||length>16384||!window||(count&&(!source||!target))||
       (output_frames&&(!power||!last_key||!group_weight))||
       frames>static_cast<std::size_t>(limit)||output_frames>static_cast<std::size_t>(limit))return false;
    for(unsigned k=0;k<length;++k)if(!std::isfinite(window[k])||window[k]<0||window[k]>1)return false;
    bool increasing=false,decreasing=false;std::int64_t previous=0;
    for(std::size_t g=0;g<count;++g){
        if(source[g]<0||target[g]<0||source[g]>limit||target[g]>limit)return false;
        auto key=source[g]-target[g];
        if(g){increasing|=key>previous;decreasing|=key<previous;}
        previous=key;
    }
    if(increasing&&decreasing)return false;
    std::fill_n(power,output_frames,0.);std::fill_n(group_weight,output_frames,0.);
    std::fill_n(last_key,output_frames,std::numeric_limits<std::int64_t>::max());
    const auto half=static_cast<std::int64_t>(length/2);
    for(std::size_t g=0;g<count;++g){
        const auto key=source[g]-target[g],start=target[g]-half;
        const auto begin=std::max<std::int64_t>(0,-start);
        const auto end=std::min<std::int64_t>(length,static_cast<std::int64_t>(output_frames)-start);
        for(auto k=begin;k<end;++k){
            const auto j=static_cast<std::size_t>(start+k);
            if(start+k+key<0||start+k+key>=static_cast<std::int64_t>(frames))continue;
            const auto w=window[static_cast<std::size_t>(k)];
            if(last_key[j]==key){power[j]+=w*(w+2*group_weight[j]);group_weight[j]+=w;}
            else{power[j]+=w*w;last_key[j]=key;group_weight[j]=w;}
        }
    }
    return true;
}
}
#endif
