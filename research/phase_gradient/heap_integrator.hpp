#pragma once
// Independent implementation of Prusa/Holighaus, Phase Vocoder Done Right,
// Algorithm 1 (EUSIPCO 2017; arXiv:2202.07382). No reference code is imported.
// Inputs: radians/sample temporal gradient, radians/bin frequency gradient.
// One frame is processed with preallocated storage and <=2*bins heap removals.
// Low-magnitude bins retain input phase instead of randomizing it (ablation).
#include <algorithm>
#include <cstddef>
#include <cstdint>
#include <stdexcept>
#include <vector>
namespace boiled_egg::experiment {
class phase_heap {
    struct entry { double weight; std::uint32_t age,bin; };
    struct less {
        bool operator()(entry a,entry b)const noexcept {
            if(a.weight!=b.weight)return a.weight<b.weight;
            if(a.age!=b.age)return a.age>b.age;
            return a.bin>b.bin;
        }
    };
    static std::size_t checked(std::size_t bins) {
        if(bins<2||bins>16385)throw std::invalid_argument("phase heap bins");
        return bins;
    }
    std::size_t bins_,size_{};
    std::vector<entry> heap_;
    std::vector<std::uint8_t> unknown_;
    void push(entry e)noexcept {heap_[size_++]=e;std::push_heap(heap_.begin(),heap_.begin()+size_,less{});}
    entry pop()noexcept {std::pop_heap(heap_.begin(),heap_.begin()+size_,less{});return heap_[--size_];}
public:
    struct stats {std::uint32_t temporal{},frequency{},pops{};};
    explicit phase_heap(std::size_t bins):bins_(checked(bins)),heap_(2*bins_),unknown_(bins_) {}
    // Finite arrays of bins entries; output must not alias input arrays. Caller's
    // FFT setup supplies consistent gradients. No locks/allocations here.
    stats integrate(const double* mag,const double* oldmag,const double* dt,const double* olddt,
                    const double* df,const double* oldphase,const double* inputphase,
                    double synthesis_hop,double alpha,double tolerance,double* output)noexcept {
        stats result{};size_=0;double maximum=0;
        for(std::size_t k=0;k<bins_;++k)maximum=std::max({maximum,mag[k],oldmag[k]});
        const double threshold=tolerance*maximum;std::size_t remaining=0;
        for(std::size_t k=0;k<bins_;++k) {
            output[k]=inputphase[k];unknown_[k]=mag[k]>threshold;
            if(unknown_[k]){++remaining;push({oldmag[k],0,static_cast<std::uint32_t>(k)});}
        }
        while(remaining&&size_) {
            const auto top=pop();const auto k=top.bin;++result.pops;
            if(!top.age) {
                if(unknown_[k]) {
                    output[k]=oldphase[k]+.5*synthesis_hop*(olddt[k]+dt[k]);
                    unknown_[k]=0;--remaining;++result.temporal;push({mag[k],1,k});
                }
            } else for(int direction:{-1,1}) {
                const auto next=static_cast<int>(k)+direction;
                if(next<0||next>=static_cast<int>(bins_)||!unknown_[next])continue;
                output[next]=output[k]+direction*.5*alpha*(df[k]+df[next]);
                unknown_[next]=0;--remaining;++result.frequency;push({mag[next],1,static_cast<std::uint32_t>(next)});
            }
        }
        return result;
    }
};
}
