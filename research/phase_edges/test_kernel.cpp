#include "edge_heap.hpp"
#include <atomic>
#include <cmath>
#include <cstdlib>
#include <iostream>
#include <new>
#include <stdexcept>
#include <vector>
static std::atomic<bool> counting{false};static std::atomic<unsigned> allocations{0};
void* operator new(std::size_t n){if(counting.load())++allocations;if(void* p=std::malloc(n?n:1))return p;throw std::bad_alloc();}
void* operator new[](std::size_t n){return ::operator new(n);}
void operator delete(void* p)noexcept{std::free(p);}void operator delete[](void* p)noexcept{std::free(p);}
void operator delete(void* p,std::size_t)noexcept{std::free(p);}void operator delete[](void* p,std::size_t)noexcept{std::free(p);}
static void require(bool c,const char* m){if(!c)throw std::runtime_error(m);}
int main(){try{
    std::uint64_t checks=0,pops=0;using boiled_egg::experiment::edge_heap;
    for(unsigned n:{2U,33U,513U,2049U}) {
        edge_heap k(n);std::vector<double> m(n),om(n),dt(n),df(n-1),old(n),phase(n),out(n);
        for(unsigned r=0;r<100;++r){
            // Arbitrary curved scalar field, not merely an affine gradient.
            for(unsigned b=0;b<n;++b){
                old[b]=.7*std::sin(.37*b)+.02*r+.0001*b*b;
                phase[b]=.9*std::cos(.17*b+.07*r)+.11*std::sin(.29*b*r)+.0002*b*b;
                dt[b]=phase[b]-old[b];m[b]=1.+double((b*719U+r*17U)%97U);om[b]=1.+double((b*23U+r*911U)%103U);
                if(b)df[b-1]=phase[b]-phase[b-1];
            }
            counting.store(true);auto s=k.integrate(m.data(),om.data(),dt.data(),df.data(),old.data(),phase.data(),1e-6,out.data());counting.store(false);
            require(s.pops<=2*n&&s.temporal+s.frequency==n,"finite work bound");pops+=s.pops;
            for(unsigned b=0;b<n;++b){require(std::abs(out[b]-phase[b])<1e-10,"curved conservative field not recovered");++checks;}
        }
        std::fill(m.begin(),m.end(),0);std::fill(om.begin(),om.end(),0);
        counting.store(true);auto s=k.integrate(m.data(),om.data(),dt.data(),df.data(),old.data(),phase.data(),1e-6,out.data());counting.store(false);
        require(out==phase&&s.pops==0,"silence fallback");
    }
    for(unsigned n:{0U,1U,16386U}){bool rejected=false;try{edge_heap k(n);}catch(const std::invalid_argument&){rejected=true;}require(rejected,"invalid shape");}
    require(!allocations.load(),"processing allocation");
    std::cout<<checks<<" curved field values; "<<pops<<" bounded removals; zero processing allocations\n";
}catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}}
