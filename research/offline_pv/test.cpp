#include "offline.hpp"
#include <algorithm>
#include <cmath>
#include <iostream>
#include <limits>
#include <numbers>
#include <stdexcept>
#include <string>
using namespace boiled_egg::offline_research;
void check(bool x,const char* message) {if(!x)throw std::runtime_error(message);}
std::vector<float> fixture(unsigned rate) {
    std::vector<float> x(rate/5);
    for(std::size_t i=0;i<x.size();++i) {const double t=double(i)/rate; x[i]=float(.2*std::sin(2*std::numbers::pi*223*t)+.06*std::cos(2*std::numbers::pi*997*t));}
    return x;
}
int main(int argc,char**argv) {try {
    check(argc==2,"test name required");const std::string name=argv[1];
    Config c;auto x=fixture(c.sample_rate);
    if(name=="identity") {
        for(auto rate:{48000u,96000u})for(auto iterations:{0u,8u,32u}) {
            c.sample_rate=rate;c.iterations=iterations;x=fixture(rate);auto y=render(x,c);
            double e=0,s=0;for(std::size_t i=0;i<x.size();++i){e+=std::pow(double(x[i])-y.audio[i],2);s+=double(x[i])*x[i];}
            check(std::sqrt(e/s)<2e-5,"identity numerical reconstruction");
        }
    } else if(name=="length") {
        for(auto rate:{48000u,96000u})for(auto t:{.5,1.,2.})for(auto p:{.5,1.,2.}) {
            c.sample_rate=rate;c.time_ratio=t;c.pitch_ratio=p; x=fixture(rate);auto y=render(x,c);
            check(y.audio.size()==std::size_t(std::floor(x.size()*t+.5)),"exact output length");
            check(std::all_of(y.audio.begin(),y.audio.end(),[](float v){return std::isfinite(v);}),"finite output");
        }
    } else if(name=="projection") {
        c.time_ratio=1.25;c.iterations=32;auto y=render(x,c);
        check(y.magnitude_residual.size()==33,"all objective iterations retained");
        for(std::size_t i=1;i<y.magnitude_residual.size();++i)check(y.magnitude_residual[i]<=y.magnitude_residual[i-1]+1e-5,"projection residual increase");
        check(y.magnitude_residual.back()<y.magnitude_residual.front(),"no projection progress");
    } else if(name=="deterministic") {
        c.pitch_ratio=.5;c.iterations=8;auto a=render(x,c),b=render(x,c);
        check(a.audio==b.audio && a.magnitude_residual==b.magnitude_residual,"deterministic render");
    } else if(name=="invalid") {
        auto rejects=[&](const std::vector<float>&v,const Config&cfg){try{(void)render(v,cfg);return false;}catch(const std::invalid_argument&){return true;}};
        check(rejects({},c),"empty accepted");check(rejects(std::vector<float>(1000),c),"zero accepted");
        auto z=x;z[3]=std::numeric_limits<float>::quiet_NaN();check(rejects(z,c),"NaN accepted");
        for(auto v:{0.,-1.,std::numeric_limits<double>::infinity()}){auto bad=c;bad.time_ratio=v;check(rejects(x,bad),"bad time accepted");}
        for(auto v:{.49,2.01,std::numeric_limits<double>::quiet_NaN()}){auto bad=c;bad.pitch_ratio=v;check(rejects(x,bad),"bad pitch accepted");}
        auto bad=c;bad.sample_rate=44100;check(rejects(x,bad),"bad rate accepted");bad=c;bad.iterations=1;check(rejects(x,bad),"bad iterations accepted");
        bad=c;bad.memory_limit_bytes=1;check(rejects(x,bad),"work budget accepted");
    } else throw std::runtime_error("unknown test name");
    std::cout<<name<<" passed\n";
}catch(const std::exception&e){std::cerr<<e.what()<<'\n';return 1;}}
