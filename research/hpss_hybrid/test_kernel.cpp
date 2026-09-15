#include "kernels.hpp"
#include <array>
#include <atomic>
#include <cstdlib>
#include <iostream>
#include <new>
#include <numbers>
#include <stdexcept>
#include <vector>
static bool measure=false;
static unsigned allocations=0;
void* operator new(std::size_t n){if(measure)++allocations;if(void* p=std::malloc(n?n:1))return p;throw std::bad_alloc();}
void* operator new[](std::size_t n){return ::operator new(n);}
void operator delete(void* p)noexcept{std::free(p);}void operator delete[](void* p)noexcept{std::free(p);}
void operator delete(void* p,std::size_t)noexcept{std::free(p);}void operator delete[](void* p,std::size_t)noexcept{std::free(p);}
static void check(bool condition,const char* reason){if(!condition)throw std::runtime_error(reason);}
namespace hp=boiled_egg::research::hpss;
int main(){try{
    unsigned mask_checks=0,sample_checks=0;
    std::vector<double> h(5001),p(h.size()),m(h.size());
    for(unsigned i=0;i<h.size();++i){h[i]=std::pow(10.,-300.+600.*i/5000.);p[i]=std::pow(10.,300.-600.*i/5000.);}
    measure=true;bool good=hp::masks(h.data(),p.data(),m.data(),m.size());measure=false;check(good,"mask valid");
    for(unsigned i=0;i<m.size();++i){const long double a=h[i],b=p[i];auto ideal=static_cast<double>(a*a/(a*a+b*b));
        check(std::abs(m[i]-ideal)<3e-16,"independent long-double soft-mask formula");check(m[i]>=0&&m[i]<=1,"mask bounds");++mask_checks;}
    const std::array<double,3> hh{0.,1.,4.},pp{0.,4.,1.};std::array<double,3> mm{};
    check(hp::masks(hh.data(),pp.data(),mm.data(),3),"fixed mask");check(mm[0]==.5&&mm[1]+mm[2]==1,"silence symmetry complement");
    auto saved=m;p[300]=-1;check(!hp::masks(h.data(),p.data(),m.data(),m.size())&&saved==m,"negative mask transactional");
    p[300]=std::numeric_limits<double>::infinity();check(!hp::masks(h.data(),p.data(),m.data(),m.size())&&saved==m,"nonfinite mask transactional");
    check(hp::masks(nullptr,nullptr,nullptr,0),"empty mask");
    for(unsigned frames:{0U,1U,31U,129U,1025U})for(unsigned channels:{1U,2U,8U})for(unsigned length:{31U,64U,256U})for(double alpha:{.25,.5,1.,1.5,2.,4.}){
        std::vector<double>x(std::size_t(frames)*channels),window(length);
        for(unsigned i=0;i<x.size();++i)x[i]=std::sin(.071*i)*.2;
        for(unsigned k=0;k<length;++k)window[k]=.5-.5*std::cos(2*std::numbers::pi*k/length);
        const unsigned target=static_cast<unsigned>(std::floor(frames*alpha+.5));
        std::vector<std::int64_t> source,dest;
        for(unsigned t=0;t<frames+length;t+=7){source.push_back(t);dest.push_back(static_cast<std::int64_t>(std::floor(t*alpha+.5)));}
        std::vector<double> out(std::size_t(target)*channels),den(target);auto before=x;
        measure=true;good=hp::overlap_add(x.data(),frames,channels,source.data(),dest.data(),source.size(),window.data(),length,out.data(),target,den.data());measure=false;
        check(good,"OLA accepted valid bounds");check(before==x,"OLA input purity");
        // Independent gather reference, instead of the kernel's scatter.
        for(unsigned j=0;j<target;++j){double weight=0;
            for(unsigned ch=0;ch<channels;++ch){double sum=0;
                for(unsigned g=0;g<source.size();++g){auto k=static_cast<std::int64_t>(j)-dest[g]+length/2;
                    if(k<0||k>=length)continue;if(!ch)weight+=window[static_cast<std::size_t>(k)];
                    auto idx=source[g]+static_cast<std::int64_t>(j)-dest[g];
                    if(idx>=0&&idx<frames)sum+=x[static_cast<std::size_t>(idx)*channels+ch]*window[static_cast<std::size_t>(k)];}
                check(sum==out[std::size_t(j)*channels+ch],"OLA independent gather mismatch");++sample_checks;}
            check(weight==den[j],"OLA denominator padding/edge mismatch");}
    }
    std::array<double,2>x{1,2},out{11,12},den{13,14},win{1,1};std::int64_t s=0,t=-1;
    check(!hp::overlap_add(x.data(),2,1,&s,&t,1,win.data(),2,out.data(),2,den.data()),"invalid centers");
    check(out[0]==11&&den[1]==14,"invalid OLA is transactional");
    check(allocations==0,"kernel allocation");
    std::cout<<mask_checks<<" scale-stable mask comparisons; "<<sample_checks<<" exact OLA/gather samples; zero kernel allocations; invalid inputs passed\n";
}catch(const std::exception& error){std::cerr<<error.what()<<'\n';return 1;}}
