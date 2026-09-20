#include "nsdgt.h"
#include <algorithm>
#include <cmath>
#include <complex>
#include <future>
#include <iostream>
#include <limits>
#include <numbers>
#include <stdexcept>
#include <string>
#include <vector>
namespace {
using Z=std::complex<double>;
void check(bool b,const char* m="control failed") {if(!b)throw std::runtime_error(m);}
struct System {
    be_nsg_config config{sizeof(be_nsg_config),32,37,64*1024*1024};
    std::vector<be_nsg_frame> frames;
    std::vector<double> windows;
    System() {
        for(int center=0;center<=36;center+=4) {
            const unsigned len=center%8 ? 9u : 16u;
            frames.push_back({center,len,static_cast<uint32_t>(windows.size())});
            for(unsigned r=0;r<len;++r) {
                // Asymmetric signed windows test more than symmetric audio windows.
                const double a=.25+.5*static_cast<double>(r+1)/len;
                windows.push_back(center%8 && r%3==0 ? -a : a);
            }
        }
    }
    size_t bins()const{return frames.size()*config.fft_size;}
    std::vector<float> analyze(const std::vector<float>& x,be_nsg_info* metadata=nullptr) const {
        std::vector<float> c(2*bins(),-99);be_nsg_info info{};
        check(be_nsg_analyze(&config,frames.data(),static_cast<uint32_t>(frames.size()),windows.data(),windows.size(),x.data(),x.size()/2,c.data(),bins(),&info)==0,"analyze");
        check(info.minimum_diagonal>0 && info.condition_number<=1e6);
        if(metadata)*metadata=info;return c;
    }
    std::vector<float> synth(const std::vector<float>& c)const {
        std::vector<float> y(2*config.frames,-99);be_nsg_info info{};
        check(be_nsg_synthesize(&config,frames.data(),static_cast<uint32_t>(frames.size()),windows.data(),windows.size(),c.data(),c.size()/2,y.data(),config.frames,&info)==0,"synthesize");
        return y;
    }
    std::vector<Z> direct(const std::vector<float>& x)const {
        std::vector<Z> result(bins());
        for(size_t j=0;j<frames.size();++j)for(unsigned k=0;k<config.fft_size;++k) {
            const auto& f=frames[j];Z sum{};
            for(unsigned r=0;r<f.window_length;++r) {
                auto t=static_cast<int64_t>(r)-f.window_length/2,l=f.center+t;
                if(l<0 || l>=static_cast<int64_t>(config.frames))continue;
                const double angle=-2*std::numbers::pi*static_cast<double>(k*t)/config.fft_size;
                sum+=Z(x[2*static_cast<size_t>(l)],x[2*static_cast<size_t>(l)+1])*windows[f.window_offset+r]*std::exp(Z(0,angle));
            }
            result[j*config.fft_size+k]=sum;
        }
        return result;
    }
    std::vector<Z> inverse_direct(const std::vector<float>& c)const {
        std::vector<Z> y(config.frames);std::vector<double> diagonal(config.frames);
        for(size_t j=0;j<frames.size();++j)for(unsigned r=0;r<frames[j].window_length;++r) {
            auto t=static_cast<int64_t>(r)-frames[j].window_length/2,l=frames[j].center+t;
            if(l<0 || l>=static_cast<int64_t>(config.frames))continue;
            Z v{};
            for(unsigned k=0;k<config.fft_size;++k) {
                const size_t index=2*(j*config.fft_size+k);
                v+=Z(c[index],c[index+1])*std::exp(Z(0,2*std::numbers::pi*static_cast<double>(k*t)/config.fft_size));
            }
            const double g=windows[frames[j].window_offset+r];
            y[static_cast<size_t>(l)]+=v*g/static_cast<double>(config.fft_size);
            diagonal[static_cast<size_t>(l)]+=g*g;
        }
        for(size_t i=0;i<y.size();++i)y[i]/=diagonal[i];return y;
    }
};
std::vector<float> signal(size_t n) {
    std::vector<float> x(2*n);
    for(size_t i=0;i<n;++i){x[2*i]=static_cast<float>(.2*std::sin(.3*i));x[2*i+1]=static_cast<float>(.1*std::cos(.17*i));}return x;
}
double diff(const std::vector<float>& a,const std::vector<float>& b) {
    check(a.size()==b.size());double e=0;for(size_t i=0;i<a.size();++i)e=std::max(e,std::abs(static_cast<double>(a[i])-b[i]));return e;
}
double diff(const std::vector<float>& a,const std::vector<Z>& b) {
    check(a.size()==2*b.size());double e=0;for(size_t i=0;i<b.size();++i)e=std::max(e,std::abs(Z(a[2*i],a[2*i+1])-b[i]));return e;
}
Z dot(const std::vector<float>& a,const std::vector<float>& b) {
    Z result{};for(size_t i=0;i<a.size()/2;++i)result+=std::conj(Z(a[2*i],a[2*i+1]))*Z(b[2*i],b[2*i+1]);return result;
}
}
int main(int argc,char** argv) {
 try {
    check(argc==2);System s;auto x=signal(s.config.frames);std::string name=argv[1];
    if(name=="roundtrip") {
        for(unsigned m:{16u,32u,64u,4096u}){s.config.fft_size=m;check(diff(x,s.synth(s.analyze(x)))<3e-6);}
        auto real=x;for(size_t i=1;i<real.size();i+=2)real[i]=0;check(diff(real,s.synth(s.analyze(real)))<3e-6);
    } else if(name=="direct_dft") {
        for(unsigned m:{16u,32u,64u}){s.config.fft_size=m;const double e=diff(s.analyze(x),s.direct(x));std::cout<<"DFT "<<m<<" max_error "<<e<<'\n';check(e<3e-6);}
    } else if(name=="direct_synthesis") {
        for(unsigned m:{16u,32u,64u}){s.config.fft_size=m;auto c=signal(s.bins());const double e=diff(s.synth(c),s.inverse_direct(c));std::cout<<"inverse "<<m<<" max_error "<<e<<'\n';check(e<3e-6);}
    } else if(name=="basis") {
        for(size_t i=0;i<2*s.config.frames;++i){std::vector<float> unit(2*s.config.frames);unit[i]=.5f;check(diff(unit,s.synth(s.analyze(unit)))<3e-6);}
    } else if(name=="edits") {
        auto c=s.analyze(x);for(auto& v:c)v*=.25f;auto y=s.synth(c);auto target=x;for(auto& v:target)v*=.25f;check(diff(target,y)<3e-6);check(diff(x,y)>.05);
        std::fill(c.begin(),c.end(),0);y=s.synth(c);check(std::all_of(y.begin(),y.end(),[](float v){return v==0;}));
        std::vector<float> zero(x.size());check(s.synth(s.analyze(zero))==zero);
    } else if(name=="linearity") {
        auto a=signal(x.size()/2),b=a;std::reverse(b.begin(),b.end());auto sum=a;
        for(size_t i=0;i<sum.size();++i)sum[i]=a[i]+.5f*b[i];auto ca=s.analyze(a),cb=s.analyze(b),cs=s.analyze(sum);
        for(size_t i=0;i<ca.size();++i)ca[i]+=.5f*cb[i];check(diff(ca,cs)<3e-6);
    } else if(name=="projection") {
        auto c=signal(s.bins()),d=c;std::reverse(d.begin(),d.end());auto pc=s.analyze(s.synth(c)),pd=s.analyze(s.synth(d));
        check(diff(pc,s.analyze(s.synth(pc)))<3e-6);check(std::abs(dot(pc,d)-dot(c,pd))<3e-6);
        check(diff(c,pc)>.01,"projection must not be identity on inconsistent coefficients");
    } else if(name=="coverage" || name=="invalid" || name=="budget") {
        auto bad=[&](int expected){std::vector<float> out(2*std::min<size_t>(s.bins(),4096),-99);be_nsg_info info{123,123,123,123,123,123};
            int rc=be_nsg_analyze(&s.config,s.frames.data(),static_cast<uint32_t>(s.frames.size()),s.windows.data(),s.windows.size(),x.data(),x.size()/2,out.data(),out.size()/2,&info);
            check(rc==expected,"wrong rejection code");check(info.coefficient_count==123);check(std::all_of(out.begin(),out.end(),[](float v){return v==-99;}));};
        if(name=="coverage") {
            s.frames.resize(1);bad(4);s=System();for(auto& w:s.windows)w*=1e-6;bad(5);
            s=System();for(auto& w:s.windows)w=0;bad(4);
        } else if(name=="budget") {s.config.memory_limit_bytes=1;bad(3);s=System();s.config.fft_size=16384;s.frames.resize(4096,s.frames.back());bad(2);}
        else {
            s.frames[1].center=s.frames[0].center;bad(2);s=System();s.frames[0].window_length=33;bad(2);
            s=System();s.frames[0].window_offset=std::numeric_limits<uint32_t>::max();bad(2);
            s=System();s.windows[0]=std::numeric_limits<double>::quiet_NaN();bad(2);s=System();s.config.fft_size=31;bad(2);
            s=System();x[0]=std::numeric_limits<float>::infinity();bad(2);x=signal(s.config.frames);
            s=System();auto c=s.analyze(x);c[0]=std::numeric_limits<float>::quiet_NaN();std::vector<float> y(x.size(),-99);be_nsg_info info{};
            check(be_nsg_synthesize(&s.config,s.frames.data(),static_cast<uint32_t>(s.frames.size()),s.windows.data(),s.windows.size(),c.data(),s.bins(),y.data(),s.config.frames,&info)==2);
            check(std::all_of(y.begin(),y.end(),[](float v){return v==-99;}));
        }
    } else if(name=="threads") {
        auto call=[&]{return s.synth(s.analyze(x));};auto task=std::async(std::launch::async,call);check(task.get()==call());
    } else throw std::runtime_error("unknown test");
    std::cout<<name<<" passed\n";return 0;
 } catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}
}
