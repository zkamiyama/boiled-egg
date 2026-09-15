#include "event_fusion.hpp"
#include <array>
#include <cstdlib>
#include <iostream>
#include <new>
#include <random>
#include <stdexcept>
#include <vector>
static bool count_allocations=false;static unsigned allocations=0;
void* operator new(std::size_t n){if(count_allocations)++allocations;if(void*p=std::malloc(n?n:1))return p;throw std::bad_alloc();}
void* operator new[](std::size_t n){return ::operator new(n);}
void operator delete(void*p)noexcept{std::free(p);}void operator delete[](void*p)noexcept{std::free(p);}
void operator delete(void*p,std::size_t)noexcept{std::free(p);}void operator delete[](void*p,std::size_t)noexcept{std::free(p);}
using fusion=boiled_egg::research::event_fusion;
static void require(bool x,const char*s){if(!x)throw std::runtime_error(s);}
static std::vector<double> oracle(const std::vector<double>&t,const std::vector<double>&s,double gap){
    std::vector<bool> used(t.size(),false);std::vector<double> out;
    for(;;){double first=1e100;for(std::size_t i=0;i<t.size();++i)if(!used[i])first=std::min(first,t[i]);
        if(first==1e100)break;double score=-1,best=0;
        for(std::size_t i=0;i<t.size();++i)if(!used[i] && t[i]-first<=gap){used[i]=true;
            if(s[i]>score || (s[i]==score && t[i]<best)){score=s[i];best=t[i];}}
        out.push_back(best);
    }return out;
}
int main(){try{
    fusion f(512);std::array<double,512> out{};std::mt19937 rng(260916);unsigned checks=0;
    for(unsigned n:{0U,1U,2U,9U,127U,512U})for(unsigned rep=0;rep<80;++rep){
        std::vector<double> t(n),s(n);for(unsigned i=0;i<n;++i){t[i]=double(rng()%2000U)/4.;s[i]=double(rng()%17U)/16.;}
        double gap=double(rep%9)/2;auto expected=oracle(t,s,gap);auto original=t;
        count_allocations=true;auto k=f.process(t.data(),s.data(),n,gap,out.data(),out.size());count_allocations=false;
        require(k==expected.size(),"cluster count");for(unsigned i=0;i<k;++i){require(out[i]==expected[i],"exhaustive oracle mismatch");++checks;}
        require(t==original,"input mutation");
    }
    double t[]={0,.75,1.5},s[]={1,2,3};auto k=f.process(t,s,3,1,out.data(),out.size());
    require(k==2 && out[0]==.75 && out[1]==1.5,"no transitive bridge merge");
    out.fill(7);double bad[]={0,std::numeric_limits<double>::quiet_NaN()};
    require(f.process(bad,s,2,1,out.data(),out.size())==fusion::invalid,"nonfinite reject");
    require(std::all_of(out.begin(),out.end(),[](double v){return v==7;}),"invalid batch changed output");
    require(f.process(nullptr,nullptr,0,1,nullptr,0)==0,"empty batch");
    require(f.process(t,s,3,1,out.data(),2)==fusion::invalid,"capacity rejected");
    require(!allocations,"kernel allocated");
    std::cout<<checks<<" exhaustive fused event times; empty/invalid/chain/capacity/purity; zero processing allocations\n";
}catch(const std::exception&e){std::cerr<<e.what()<<'\n';return 1;}}
