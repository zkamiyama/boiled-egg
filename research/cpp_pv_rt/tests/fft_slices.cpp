#include "../src/fft.hpp"
#include <algorithm>
#include <cmath>
#include <iostream>
#include <random>
#include <stdexcept>
#include <vector>
using namespace boiled_egg::research::detail;
int main(){try{
    std::mt19937 random(20260913);std::uniform_real_distribution<float>d(-1,1);
    double maximum=0;std::uint64_t checked=0;
    for(std::size_t n:{64,128,256,512,1024,2048,4096,8192,16384}){
        fft_plan plan(n);std::vector<std::complex<float>>x(n);
        for(auto&z:x)z={d(random),d(random)};
        for(bool inverse:{false,true}){
            auto expected=x;if(inverse)plan.inverse(expected.data());else plan.forward(expected.data());
            for(bool simd:{false,true})for(std::size_t budget:{1,3,31,128,257,4096}){
                auto y=x;fft_plan::cursor cursor;plan.start(cursor,y.data(),inverse,simd);
                auto initial=y;if(!plan.advance(cursor,0)||initial!=y)throw std::runtime_error("zero budget");
                std::size_t steps=0;while(plan.advance(cursor,budget))if(++steps>n*32)throw std::runtime_error("no progress");
                for(std::size_t i=0;i<n;++i){
                    maximum=std::max(maximum,static_cast<double>(std::abs(expected[i]-y[i])));++checked;
                    if(expected[i]!=y[i])throw std::runtime_error("scalar/SIMD or chunk mismatch");
                }
                auto again=y;if(plan.advance(cursor,100)||again!=y)throw std::runtime_error("completed cursor mutates");
            }
        }
    }
    std::cout<<checked<<" complex values checked; max error "<<maximum<<"; SSE2 "<<fft_plan::simd_available()<<'\n';
}catch(const std::exception&e){std::cerr<<e.what()<<'\n';return 1;}}
