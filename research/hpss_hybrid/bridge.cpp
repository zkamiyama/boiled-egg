#include "kernels.hpp"
extern "C" {
unsigned hpss_masks(const double* h,const double* p,double* m,std::size_t n) {
    return boiled_egg::research::hpss::masks(h,p,m,n)?1U:0U;
}
unsigned hpss_overlap_add(const double* x,std::size_t frames,unsigned channels,
    const std::int64_t* source,const std::int64_t* target,std::size_t grains,
    const double* window,unsigned length,double* output,std::size_t output_frames,double* weights) {
    return boiled_egg::research::hpss::overlap_add(x,frames,channels,source,target,
        grains,window,length,output,output_frames,weights)?1U:0U;
}
}
