#ifndef BOILED_EGG_RESEARCH_HPSS_KERNELS_HPP
#define BOILED_EGG_RESEARCH_HPSS_KERNELS_HPP
#include <algorithm>
#include <cmath>
#include <cstddef>
#include <cstdint>
#include <limits>

namespace boiled_egg::research::hpss {
// Independent research kernels, not the public product ABI. Buffers must not
// overlap. Input finiteness for OLA is checked once by the owner, not per grain.
// No allocation, lock, I/O or persistent mutable state.
inline bool masks(const double* harmonic, const double* percussive,
                  double* result, std::size_t count) noexcept {
    if (count && (!harmonic || !percussive || !result)) return false;
    for (std::size_t i=0; i<count; ++i)
        if (!std::isfinite(harmonic[i]) || !std::isfinite(percussive[i]) ||
            harmonic[i]<0 || percussive[i]<0) return false;
    for (std::size_t i=0; i<count; ++i) {
        const double scale=std::max(harmonic[i],percussive[i]);
        if (scale==0) { result[i]=.5; continue; }
        const double h=harmonic[i]/scale,p=percussive[i]/scale;
        result[i]=(h*h)/(h*h+p*p); // no squared-input overflow
    }
    return true;
}
// Overlap-add complete centered grains into caller-owned zeroed accumulators.
// A grain uses one Hann weight; the same weight accumulates in the denominator.
// Missing source samples are zero padding, not a reason to omit denominator.
// Work <= grains * window * (channels+constant), including validation.
inline bool overlap_add(const double* input, std::size_t frames, unsigned channels,
                        const std::int64_t* source_centers,
                        const std::int64_t* destination_centers, std::size_t grains,
                        const double* window, unsigned length,
                        double* output, std::size_t output_frames,
                        double* denominator) noexcept {
    constexpr auto limit=std::numeric_limits<std::int64_t>::max()/4;
    if (!channels || channels>8 || !length || length>16384 || !window ||
        (frames && !input) || (output_frames && (!output || !denominator)) ||
        (grains && (!source_centers || !destination_centers)) ||
        frames>static_cast<std::size_t>(limit) || output_frames>static_cast<std::size_t>(limit) ||
        frames>std::numeric_limits<std::size_t>::max()/channels ||
        output_frames>std::numeric_limits<std::size_t>::max()/channels) return false;
    for (unsigned k=0;k<length;++k)
        if (!std::isfinite(window[k]) || window[k]<0 || window[k]>1) return false;
    for (std::size_t i=0;i<grains;++i)
        if (source_centers[i]<0 || source_centers[i]>limit ||
            destination_centers[i]<0 || destination_centers[i]>limit) return false;
    const auto half=static_cast<std::int64_t>(length/2);
    for (std::size_t g=0;g<grains;++g) {
        const auto src=source_centers[g]-half,dst=destination_centers[g]-half;
        const auto start=std::max<std::int64_t>(0,-dst);
        const auto end=std::min<std::int64_t>(length,static_cast<std::int64_t>(output_frames)-dst);
        for (auto k=start;k<end;++k) {
            const auto output_index=static_cast<std::size_t>(dst+k);
            const double w=window[static_cast<std::size_t>(k)];
            denominator[output_index]+=w;
            if (src+k<0 || src+k>=static_cast<std::int64_t>(frames)) continue;
            const auto input_index=static_cast<std::size_t>(src+k);
            for(unsigned ch=0;ch<channels;++ch)
                output[output_index*channels+ch]+=input[input_index*channels+ch]*w;
        }
    }
    return true;
}
}
#endif
