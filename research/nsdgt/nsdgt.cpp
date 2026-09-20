#include "nsdgt.h"
#include "fft.hpp"
#include <algorithm>
#include <cmath>
#include <complex>
#include <cstdint>
#include <new>
#include <vector>
namespace {
using F = std::complex<float>;
using D = std::complex<double>;
struct Error { int code; };
void require(bool value, int code=2) { if (!value) throw Error{code}; }
struct Plan {
    const be_nsg_config& c;
    const be_nsg_frame* f;
    const double* windows;
    uint32_t count;
    uint64_t bins{}, storage{};
    std::vector<double> diagonal;
    double low{}, high{}, dual{};
    Plan(const be_nsg_config& config, const be_nsg_frame* frames, uint32_t n,
         const double* win, uint64_t wn):c(config),f(frames),windows(win),count(n) {
        const auto m=c.fft_size;
        require(c.struct_size==sizeof(c) && c.frames>=1 && c.frames<=288000);
        require(m>=16 && m<=16384 && !(m&(m-1)) && n>=1 && n<=4096);
        bins=static_cast<uint64_t>(m)*n;
        require(bins<=8388608 && wn<=8388608);
        require(frames && win);
        // Conservative peak-live array estimate, not allocator/RSS or caller storage.
        storage=64*c.frames+24*bins+128*static_cast<uint64_t>(m)+65536;
        require(storage<=c.memory_limit_bytes,3);
        for (uint32_t j=0;j<n;++j) {
            const auto& a=f[j];
            require(a.center>=0 && static_cast<uint64_t>(a.center)<c.frames);
            require(!j || a.center>f[j-1].center);
            require(a.window_length>=2 && a.window_length<=m);
            require(a.window_offset<=wn && a.window_length<=wn-a.window_offset);
            for(uint32_t r=0;r<a.window_length;++r) {
                const double g=win[a.window_offset+r];
                require(std::isfinite(g) && std::abs(g)<=1);
            }
        }
        diagonal.assign(static_cast<size_t>(c.frames),0.);
        for (uint32_t j=0;j<n;++j) visit(j,[&](size_t l,size_t r,size_t){
            const double g=windows[f[j].window_offset+r];diagonal[l]+=g*g;
        });
        const auto mm=std::minmax_element(diagonal.begin(),diagonal.end());
        low=*mm.first;high=*mm.second;
        require(low>0,4);
        require(low>=1e-8 && high/low<=1e6,5);
        for(uint32_t j=0;j<n;++j) visit(j,[&](size_t l,size_t r,size_t){
            dual=std::max(dual,std::abs(windows[f[j].window_offset+r]/diagonal[l]));
        });
    }
    template<class Fn> void visit(uint32_t j,Fn fn) const {
        const auto& a=f[j];
        for(uint32_t r=0;r<a.window_length;++r) {
            const int64_t t=static_cast<int64_t>(r)-a.window_length/2;
            const int64_t l=a.center+t;
            if(l<0 || static_cast<uint64_t>(l)>=c.frames) continue;
            const auto slot=static_cast<size_t>(t<0 ? t+c.fft_size : t);
            fn(static_cast<size_t>(l),static_cast<size_t>(r),slot);
        }
    }
    be_nsg_info info() const {return {bins,storage,low,high,high/low,dual};}
};
void finite(const std::vector<F>& values) {
    for(const auto z:values) require(std::isfinite(z.real())&&std::isfinite(z.imag()),6);
}
void copy_complex(const std::vector<F>& values,float* output) {
    for(size_t i=0;i<values.size();++i) {output[2*i]=values[i].real();output[2*i+1]=values[i].imag();}
}
}
extern "C" int be_nsg_analyze(const be_nsg_config* c,const be_nsg_frame* f,uint32_t n,
                               const double* windows,uint64_t wn,const float* input,uint64_t input_n,
                               float* output,uint64_t capacity,be_nsg_info* info) {
    try {
        require(c&&input&&output&&info);
        require(input_n==c->frames);
        Plan p(*c,f,n,windows,wn);require(capacity>=p.bins);
        for(uint64_t i=0;i<2*input_n;++i) require(std::isfinite(input[i])&&std::abs(input[i])<=1);
        boiled_egg::research::detail::fft_plan fft(c->fft_size);
        std::vector<F> result(static_cast<size_t>(p.bins));
        for(uint32_t j=0;j<n;++j) {
            F* frame=result.data()+static_cast<size_t>(j)*c->fft_size;
            p.visit(j,[&](size_t l,size_t r,size_t slot){
                const float g=static_cast<float>(windows[f[j].window_offset+r]);
                frame[slot]=F(input[2*l],input[2*l+1])*g;
            });
            fft.forward(frame);
        }
        finite(result);copy_complex(result,output);*info=p.info();return 0;
    } catch(const Error& e){return e.code;}catch(const std::bad_alloc&){return 3;}catch(...){return 2;}
}
extern "C" int be_nsg_synthesize(const be_nsg_config* c,const be_nsg_frame* f,uint32_t n,
                                  const double* windows,uint64_t wn,const float* coeff,uint64_t cn,
                                  float* output,uint64_t capacity,be_nsg_info* info) {
    try {
        require(c&&coeff&&output&&info);
        Plan p(*c,f,n,windows,wn);require(cn==p.bins&&capacity>=c->frames);
        for(uint64_t i=0;i<2*cn;++i) require(std::isfinite(coeff[i]));
        boiled_egg::research::detail::fft_plan fft(c->fft_size);
        std::vector<D> sum(static_cast<size_t>(c->frames));
        std::vector<F> frame(c->fft_size);
        for(uint32_t j=0;j<n;++j) {
            const auto offset=static_cast<size_t>(j)*c->fft_size;
            for(uint32_t k=0;k<c->fft_size;++k)frame[k]=F(coeff[2*(offset+k)],coeff[2*(offset+k)+1]);
            fft.inverse(frame.data());finite(frame);
            p.visit(j,[&](size_t l,size_t r,size_t slot){
                sum[l]+=static_cast<D>(frame[slot])*windows[f[j].window_offset+r];
            });
        }
        std::vector<F> result(static_cast<size_t>(c->frames));
        for(size_t l=0;l<result.size();++l) result[l]=static_cast<F>(sum[l]/p.diagonal[l]);
        finite(result);copy_complex(result,output);*info=p.info();return 0;
    } catch(const Error& e){return e.code;}catch(const std::bad_alloc&){return 3;}catch(...){return 2;}
}
