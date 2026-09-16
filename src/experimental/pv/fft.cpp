#include "fft.hpp"
#include <cmath>
#include <numbers>
#include <stdexcept>
#include <algorithm>
#if defined(__SSE2__) && !defined(BOILED_EGG_DISABLE_SIMD)
#include <emmintrin.h>
#endif

namespace boiled_egg::research::detail {
namespace {
bool is_power_of_two(std::size_t value) noexcept { return value >= 2 && (value & (value - 1)) == 0; }
}
fft_plan::fft_plan(std::size_t size) : size_(size), bit_reverse_(size), roots_(size / 2), stage_roots_(size-1) {
    if (!is_power_of_two(size)) throw std::invalid_argument("FFT size must be a power of two");
    unsigned bits = 0;
    for (std::size_t n = size; n > 1; n >>= 1) ++bits;
    for (std::size_t i = 0; i < size_; ++i) {
        std::size_t x = i, reversed = 0;
        for (unsigned b = 0; b < bits; ++b) { reversed = (reversed << 1) | (x & 1U); x >>= 1; }
        bit_reverse_[i] = reversed;
    }
    for (std::size_t k = 0; k < roots_.size(); ++k) {
        const float angle = -2.0F * std::numbers::pi_v<float> * static_cast<float>(k) / static_cast<float>(size_);
        roots_[k] = {std::cos(angle), std::sin(angle)};
    }
    for (std::size_t length=2;length<=size_;length<<=1)
        for(std::size_t j=0;j<length/2;++j)
            stage_roots_[length/2-1+j]=roots_[j*(size_/length)];
}
void fft_plan::forward(std::complex<float>* data) const noexcept { transform(data, false); }
void fft_plan::inverse(std::complex<float>* data) const noexcept { transform(data, true); }
void fft_plan::transform(std::complex<float>* data, bool inverse_flag) const noexcept {
    for (std::size_t i = 0; i < size_; ++i) {
        const std::size_t j = bit_reverse_[i];
        if (j > i) { const auto tmp = data[i]; data[i] = data[j]; data[j] = tmp; }
    }
    for (std::size_t length = 2; length <= size_; length <<= 1) {
        const std::size_t half = length / 2;
        const std::size_t root_step = size_ / length;
        for (std::size_t base = 0; base < size_; base += length) {
            for (std::size_t j = 0; j < half; ++j) {
                std::complex<float> root = roots_[j * root_step];
                if (inverse_flag) root = std::conj(root);
                const auto even = data[base + j];
                const auto odd = data[base + j + half] * root;
                data[base + j] = even + odd;
                data[base + j + half] = even - odd;
            }
        }
    }
    if (inverse_flag) {
        const float scale = 1.0F / static_cast<float>(size_);
        for (std::size_t i = 0; i < size_; ++i) data[i] *= scale;
    }
}

bool fft_plan::simd_available() noexcept {
#if defined(__SSE2__) && !defined(BOILED_EGG_DISABLE_SIMD)
    return true;
#else
    return false;
#endif
}
void fft_plan::start(cursor& s,std::complex<float>* data,bool inverse,bool simd) const noexcept {
    s={};s.data=data;s.inverse=inverse;s.simd=simd && simd_available();
}
bool fft_plan::advance(cursor& s,std::size_t budget) const noexcept {
    while(budget && s.stage<3) {
        if(s.stage==0) {
            const auto end=std::min(size_,s.position+budget);
            budget-=end-s.position;
            for(;s.position<end;++s.position){
                const auto j=bit_reverse_[s.position];
                if(j>s.position)std::swap(s.data[s.position],s.data[j]);
            }
            if(s.position==size_){s.stage=1;s.position=0;}
        } else if(s.stage==1) {
            const auto half=s.length/2;
            auto count=std::min({half-s.column,budget,(std::size_t)256});
            budget-=count;
            auto* even=s.data+s.base+s.column;
            auto* odd=even+half;
            const auto* roots=stage_roots_.data()+half-1+s.column;
            std::size_t j=0;
#if defined(__SSE2__) && !defined(BOILED_EGG_DISABLE_SIMD)
            if(s.simd){
                const auto sign_real=_mm_set_ps(0.F,-0.F,0.F,-0.F);
                const auto sign_imag=_mm_set_ps(-0.F,0.F,-0.F,0.F);
                for(;j+1<count;j+=2){
                    auto a=_mm_loadu_ps(reinterpret_cast<const float*>(even+j));
                    auto b=_mm_loadu_ps(reinterpret_cast<const float*>(odd+j));
                    auto w=_mm_loadu_ps(reinterpret_cast<const float*>(roots+j));
                    if(s.inverse)w=_mm_xor_ps(w,sign_imag);
                    auto real=_mm_shuffle_ps(b,b,_MM_SHUFFLE(2,2,0,0));
                    auto imag=_mm_shuffle_ps(b,b,_MM_SHUFFLE(3,3,1,1));
                    auto swap=_mm_shuffle_ps(w,w,_MM_SHUFFLE(2,3,0,1));
                    auto product=_mm_add_ps(_mm_mul_ps(real,w),_mm_xor_ps(_mm_mul_ps(imag,swap),sign_real));
                    _mm_storeu_ps(reinterpret_cast<float*>(even+j),_mm_add_ps(a,product));
                    _mm_storeu_ps(reinterpret_cast<float*>(odd+j),_mm_sub_ps(a,product));
                }
            }
#endif
            for(;j<count;++j){
                auto root=s.inverse?std::conj(roots[j]):roots[j];
                auto a=even[j],b=odd[j]*root;even[j]=a+b;odd[j]=a-b;
            }
            s.column+=count;
            if(s.column==half){s.column=0;s.base+=s.length;}
            if(s.base==size_){s.base=0;s.length<<=1;}
            if(s.length>size_){s.stage=s.inverse?2:3;s.position=0;}
        } else {
            const auto end=std::min(size_,s.position+budget);
            budget-=end-s.position;
            const float scale=1.F/static_cast<float>(size_);
#if defined(__SSE2__) && !defined(BOILED_EGG_DISABLE_SIMD)
            if(s.simd)for(;s.position+1<end;s.position+=2){
                auto* p=reinterpret_cast<float*>(s.data+s.position);
                _mm_storeu_ps(p,_mm_mul_ps(_mm_loadu_ps(p),_mm_set1_ps(scale)));
            }
#endif
            for(;s.position<end;++s.position)s.data[s.position]*=scale;
            if(s.position==size_)s.stage=3;
        }
    }
    return s.stage!=3;
}
}
