#include "anchor_map.hpp"
#include <array>
#include <atomic>
#include <cstdlib>
#include <iostream>
#include <limits>
#include <new>
#include <random>
#include <stdexcept>
#include <vector>
static bool watching=false;
static unsigned allocations=0;
void* operator new(std::size_t n){if(watching)++allocations;if(auto* p=std::malloc(n?n:1))return p;throw std::bad_alloc();}
void* operator new[](std::size_t n){return ::operator new(n);}
void operator delete(void* p)noexcept{std::free(p);}
void operator delete[](void* p)noexcept{std::free(p);}
void operator delete(void* p,std::size_t)noexcept{std::free(p);}
void operator delete[](void* p,std::size_t)noexcept{std::free(p);}
static void require(bool v,const char* s){if(!v)throw std::runtime_error(s);}
int main(){try{
    std::mt19937 gen(260915);unsigned checks=0;
    for(unsigned knots:{2U,3U,17U,99U})for(unsigned repeat=0;repeat<100;++repeat){
        std::vector<double> t(knots),u(knots),q(257),out(257);
        double a=0,b=0;
        for(unsigned k=0;k<knots;++k){a+=.01+double(gen()%10000)/100.;b+=.01+double(gen()%10000)/100.;t[k]=a;u[k]=b;}
        for(auto& v:q)v=-10+double(gen()%100000)/100000.*(a+20);
        watching=true;const auto ok=boiled_egg::research::map_anchors(t.data(),u.data(),knots,q.data(),out.data(),q.size());watching=false;
        require(ok,"valid map rejected");
        for(unsigned i=0;i<q.size();++i){unsigned k=0;while(k+1<knots && q[i]>=t[k+1])++k;k=std::min(k,knots-2);
            const long double expected=static_cast<long double>(u[k])+(static_cast<long double>(q[i])-t[k])*(static_cast<long double>(u[k+1])-u[k])/(static_cast<long double>(t[k+1])-t[k]);
            require(std::abs(static_cast<long double>(out[i])-expected)<1e-10L*(1+std::abs(expected)),"independent linear oracle mismatch");++checks;}
    }
    double t[2]={0,1},u[2]={0,2},q[2]={0,std::numeric_limits<double>::quiet_NaN()},out[2]={123,123};
    require(!boiled_egg::research::map_anchors(t,u,2,q,out,2),"NaN accepted");require(out[0]==123 && out[1]==123,"invalid input mutated output");
    t[1]=0;q[1]=1;require(!boiled_egg::research::map_anchors(t,u,2,q,out,2),"duplicate knot accepted");
    t[1]=1;require(boiled_egg::research::map_anchors(t,u,2,nullptr,nullptr,0),"empty query rejected");
    require(!allocations,"map allocated");std::cout<<checks<<" independent linear checks; transactional invalid/empty; zero allocations\n";
}catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}}
