// Isolated primitives, not FFT/HPSS/full-pipeline realtime qualification.
#include "kernels.hpp"
#include "power_weights.hpp"
#include <algorithm>
#include <chrono>
#include <cmath>
#include <iostream>
#include <numeric>
#include <numbers>
#include <stdexcept>
#include <vector>
int main(){
    double sink=0;
    std::cout<<"repeat,window,time_ratio,kind,iterations,mean_us,p99_us,max_us\n";
    for(unsigned repeat=1;repeat<=3;++repeat)for(unsigned length:{256U,512U})for(double alpha:{.5,1.5,2.}){
        constexpr unsigned frames=4096,channels=2;auto target=static_cast<unsigned>(std::floor(frames*alpha+.5));
        std::vector<double>x(frames*channels),out(target*channels),den(target),power(target),scratch(target),window(length);std::vector<std::int64_t>keys(target),src,dst;
        for(unsigned i=0;i<x.size();++i)x[i]=.1*std::sin(.0157*i);
        for(unsigned i=0;i<length;++i)window[i]=.5-.5*std::cos(2*std::numbers::pi*i/length);
        auto hop=static_cast<unsigned>(length/(8*std::max(1.,alpha)));
        for(unsigned i=0;i<frames+length;i+=hop){src.push_back(i);dst.push_back(static_cast<std::int64_t>(std::floor(i*alpha+.5)));}
        for(unsigned kind=0;kind<2;++kind){std::vector<double>cost;cost.reserve(1200);
            for(unsigned iteration=0;iteration<1400;++iteration){
                std::fill(out.begin(),out.end(),0.);std::fill(den.begin(),den.end(),0.);
                auto before=std::chrono::steady_clock::now();
                bool ok=kind?boiled_egg::research::hpss::grouped_power(frames,src.data(),dst.data(),src.size(),window.data(),length,target,power.data(),keys.data(),scratch.data()):
                    boiled_egg::research::hpss::overlap_add(x.data(),frames,channels,src.data(),dst.data(),src.size(),window.data(),length,out.data(),target,den.data());
                auto after=std::chrono::steady_clock::now();if(!ok)return 1;
                sink+=kind?power[target/2]:out[target];
                if(iteration>=200)cost.push_back(std::chrono::duration<double,std::micro>(after-before).count());
            }
            auto mean=std::accumulate(cost.begin(),cost.end(),0.)/cost.size();std::sort(cost.begin(),cost.end());
            std::cout<<repeat<<','<<length<<','<<alpha<<','<<(kind?"grouped_weights":"waveform_ola")<<",1200,"<<mean<<','<<cost[1187]<<','<<cost.back()<<'\n';
        }
    }
    if(!std::isfinite(sink))return 2;
}
