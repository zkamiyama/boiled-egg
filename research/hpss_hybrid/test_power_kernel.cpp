#include "power_weights.hpp"
#include <cstdlib>
#include <iostream>
#include <map>
#include <new>
#include <numbers>
#include <stdexcept>
#include <vector>
static bool active=false;static unsigned allocated=0;
void* operator new(std::size_t n){if(active)++allocated;if(auto p=std::malloc(n?n:1))return p;throw std::bad_alloc();}
void* operator new[](std::size_t n){return ::operator new(n);}void operator delete(void* p)noexcept{std::free(p);}void operator delete[](void* p)noexcept{std::free(p);}
void operator delete(void* p,std::size_t)noexcept{std::free(p);}void operator delete[](void* p,std::size_t)noexcept{std::free(p);}
static void check(bool value,const char* reason){if(!value)throw std::runtime_error(reason);}
int main(){try{
    unsigned tested=0;
    for(unsigned frames:{0U,1U,31U,129U,1025U})for(unsigned length:{31U,64U,256U})for(double alpha:{.5,.99,1.,1.01,1.5,2.}){
        const auto n=static_cast<unsigned>(std::floor(frames*alpha+.5));std::vector<double>w(length),out(n),scratch(n);std::vector<std::int64_t>keys(n),src,dst;
        for(unsigned i=0;i<length;++i)w[i]=.5-.5*std::cos(2*std::numbers::pi*i/length);
        for(unsigned i=0;i<frames+length;i+=7){src.push_back(i);dst.push_back(static_cast<std::int64_t>(std::floor(i*alpha+.5)));}
        active=true;bool ok=boiled_egg::research::hpss::grouped_power(frames,src.data(),dst.data(),src.size(),w.data(),length,n,out.data(),keys.data(),scratch.data());active=false;
        check(ok,"valid power input");
        for(unsigned j=0;j<n;++j){std::map<std::int64_t,double>groups;
            for(unsigned g=0;g<src.size();++g){auto k=static_cast<std::int64_t>(j)-dst[g]+length/2;auto input=src[g]+static_cast<std::int64_t>(j)-dst[g];
                if(k>=0&&k<length&&input>=0&&input<frames)groups[input]+=w[static_cast<std::size_t>(k)];}
            double expected=0;for(const auto& item:groups)expected+=item.second*item.second;
            check(std::abs(expected-out[j])<1e-12,"independent dictionary coefficient variance");++tested;}
    }
    std::int64_t s[]={0,2,4},t[]={0,3,4},keys[2]{};double w[]={1.,1.},out[]={9.,9.},scratch[2]{};
    check(!boiled_egg::research::hpss::grouped_power(4,s,t,3,w,2,2,out,keys,scratch),"nonmonotone groups rejected");
    check(out[0]==9&&out[1]==9,"invalid power input changed output");check(!allocated,"power processing allocated");
    std::cout<<tested<<" grouped coefficient-power comparisons; zero processing allocations; nonmonotone rejection passed\n";
}catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}}
