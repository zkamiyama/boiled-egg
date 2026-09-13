#include "../cpp_pv_rt/src/phase_innovation_guard.hpp"
#include <cmath>
#include <iostream>
#include <numbers>
#include <stdexcept>
namespace g=boiled_egg::research::detail::phase_innovation_guard;
static void require(bool ok,const char* why){if(!ok)throw std::runtime_error(why);}
static double principal(double x){return std::atan2(std::sin(x),std::cos(x));}
int main(){try{
    constexpr float pi=std::numbers::pi_v<float>;
    require(g::reliability(.2F,.2F,256.F,513,false)==0.F,"first frame is not a reliable estimate");
    require(g::reliability(.2F,.2F,256.F,513,true)==1.F,"constant IF has full confidence");
    unsigned cases=0;
    for(unsigned fft:{512U,1024U,2048U,4096U})for(float hop:{64.F,128.F,256.F}){
        const float halfbin=pi/static_cast<float>(fft);
        for(unsigned i=0;i<=200;++i){
            const float innovation=halfbin*static_cast<float>(i)/100.F;
            const float expected=std::max(0.F,1.F-static_cast<float>(i)/100.F);
            const float got=g::reliability(.2F+innovation,.2F,hop,fft/2+1,true);
            require(std::abs(got-expected)<5e-5F,"half-bin linear innovation calibration");
            require(got>=0.F&&got<=1.F,"confidence bounds");
            const float alias=g::reliability(.2F+innovation+2.F*pi/hop,.2F,hop,fft/2+1,true);
            require(std::abs(alias-got)<1e-4F,"hop alias invariance");++cases;
        }
    }
    for(unsigned i=0;i<101;++i)for(unsigned j=0;j<103;++j)for(unsigned k=0;k<=10;++k){
        const float a=-pi+2.F*pi*float(i)/101.F,b=-pi+2.F*pi*float(j)/103.F,w=float(k)/10.F;
        const double expected=principal(double(a)+double(w)*principal(double(b)-double(a)));
        const float got=g::blend(a,b,w);
        require(std::abs(principal(double(got)-expected))<2e-6,"shortest-arc interpolation");++cases;
    }
    const float crossing=g::blend(pi-.1F,-pi+.1F,.5F);
    require(std::abs(std::abs(crossing)-pi)<1e-6F,"do not interpolate a branch cut through zero");
    // Double rate and window/hop: the same physical frequency innovation has
    // the same confidence, up to single-precision evaluation roundoff.
    const float one=g::reliability(.04F,.039F,256.F,513,true);
    const float two=g::reliability(.02F,.0195F,512.F,1025,true);
    require(std::abs(one-two)<1e-6F,"physical rate scaling");
    std::cout<<cases<<" confidence/phase comparisons plus initialization, aliases and rate scaling passed\n";
}catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}}
