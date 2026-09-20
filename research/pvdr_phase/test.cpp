#include "phase.h"
#include <algorithm>
#include <cmath>
#include <complex>
#include <future>
#include <iostream>
#include <limits>
#include <stdexcept>
#include <string>
#include <vector>
namespace {
void check(bool v){if(!v)throw std::runtime_error("control failed");}
constexpr unsigned M=32,N=3,K=M/2+1;
using Z=std::complex<float>;
std::vector<Z> input(bool time_path=false){
    std::vector<Z> x(M*N);
    for(unsigned j=0;j<N;++j)for(unsigned k=1;k<M/2;++k){
        double amp=1e-8;
        if(k>=4&&k<=6)amp=(k==5?2.:1.)*(time_path?std::pow(.01,j):(j?2.:1.));
        const auto z=std::polar(static_cast<float>(amp),static_cast<float>(.2*j+.3*(static_cast<int>(k)-5)));
        x[j*M+k]=z;x[j*M+M-k]=std::conj(z);
    }
    return x;
}
struct Result {std::vector<Z> y;std::vector<int32_t> pred;std::vector<double> dt,df;be_phase_info info{};};
Result run(const std::vector<Z>& x,unsigned method=1,uint64_t seed=20260920){
    be_phase_config c{sizeof(c),M,N,method,2,1e-6,seed,1<<20};int64_t a[N]={0,1,2};
    Result r;r.y.resize(x.size());r.pred.resize(N*K);r.dt.resize(N*K);r.df.resize(N*K);
    check(be_phase_process(&c,a,N,reinterpret_cast<const float*>(x.data()),x.size(),reinterpret_cast<float*>(r.y.data()),r.y.size(),r.pred.data(),r.dt.data(),r.df.data(),r.pred.size(),&r.info)==0);return r;
}
double distance(double a,double b){return std::abs(std::remainder(a-b,2*3.141592653589793));}
}
int main(int argc,char**argv){try{
    check(argc==2);std::string name=argv[1];auto x=input();
    if(name=="magnitude"){
        for(unsigned method:{0u,1u}){auto r=run(x,method);for(size_t i=0;i<x.size();++i)check(std::abs(std::abs(x[i])-std::abs(r.y[i]))<1e-6);
        for(unsigned j=0;j<N;++j)for(unsigned k=1;k<M/2;++k)check(r.y[j*M+k]==std::conj(r.y[j*M+M-k]));}
    }else if(name=="zero"){auto r=run(std::vector<Z>(M*N));check(std::all_of(r.y.begin(),r.y.end(),[](Z z){return z==Z{};}));}
    else if(name=="gradients"){auto r=run(x);for(unsigned j=0;j<N;++j)for(unsigned k=4;k<=6;++k){check(std::abs(r.dt[j*K+k]-.2)<2e-7);check(std::abs(r.df[j*K+k]-.3)<2e-7);}}
    else if(name=="frequency_path"){auto r=run(x);check(r.info.frequency_edges>0);for(unsigned j=1;j<N;++j)for(unsigned k=4;k<=6;++k)check(distance(std::arg(r.y[j*M+k]),.4*j+.6*(static_cast<int>(k)-5))<2e-6);}
    else if(name=="temporal_path"){auto r=run(input(true));check(r.info.frequency_edges==0);for(unsigned k=4;k<=6;++k)check(distance(std::arg(r.y[M+k]),.4+.3*(static_cast<int>(k)-5))<2e-6);}
    else if(name=="seed"){auto r=run(x,1,1),s=run(x,1,2);check(r.y!=s.y);for(unsigned j=0;j<N;++j)for(unsigned k=4;k<=6;++k)check(r.y[j*M+k]==s.y[j*M+k]);}
    else if(name=="repeat"){auto r=run(x),s=run(x);check(r.y==s.y&&r.pred==s.pred&&r.dt==s.dt&&r.df==s.df);}
    else if(name=="threads"){auto f=std::async(std::launch::async,[&]{return run(x);});auto r=run(x),s=f.get();check(r.y==s.y&&r.pred==s.pred);}
    else if(name=="invalid"||name=="budget"){
        be_phase_config c{sizeof(c),M,N,1,2,1e-6,0,1<<20};int64_t a[N]={0,1,2};std::vector<float> out(2*M*N,-99);std::vector<int32_t> p(N*K,-99);std::vector<double> dt(N*K,-99),df(N*K,-99);be_phase_info info{};
        auto call=[&](){int rc=be_phase_process(&c,a,N,reinterpret_cast<float*>(x.data()),x.size(),out.data(),M*N,p.data(),dt.data(),df.data(),p.size(),&info);check(rc!=0);check(std::all_of(out.begin(),out.end(),[](float z){return z==-99;}));check(p[0]==-99&&dt[0]==-99&&df[0]==-99&&info.temporal_edges==0);};
        if(name=="budget"){c.memory_limit_bytes=1;call();}
        else{c.method=9;call();c.method=1;c.stretch=.5;call();c.stretch=2;a[1]=0;call();a[1]=1;c.relative_tolerance=0;call();c.relative_tolerance=1e-6;x[0]={0,1};call();x[0]={0,0};x[4]={1,1};call();x[4]={std::numeric_limits<float>::quiet_NaN(),0};call();}
    }else throw std::runtime_error("unknown test");
    std::cout<<name<<" passed\n";return 0;
}catch(const std::exception&e){std::cerr<<e.what()<<'\n';return 1;}}
