#include "ring_index.hpp"
#include <array>
#include <bit>
#include <iostream>
#include <limits>
#include <stdexcept>
#include <string_view>
#include <vector>
using boiled_egg::research::detail::ring_index;
static void require(bool b) { if(!b) throw std::runtime_error("ring property failed"); }
static std::uint64_t comparisons=0;
static void compare(std::uint64_t x, std::size_t c) {
    require(c!=0 && std::has_single_bit(c));
    require(ring_index(x,c)==x%c); ++comparisons;
}
static std::size_t capacity(std::size_t n) { std::size_t c=1;while(c<n)c<<=1;return c; }
int main(int argc,char**argv){try{
    require(argc==2);std::string_view name(argv[1]);
    if(name=="boundaries") {
        constexpr auto top=std::numeric_limits<std::uint64_t>::max();
        for(unsigned b=0;b<std::numeric_limits<std::size_t>::digits;++b) {
            const auto c=std::size_t(1)<<b;
            for(auto x:std::array<std::uint64_t,10>{0,1,c-1,c,c+1,top,top-1,top-c,top-c+1,(std::uint64_t(1)<<32)+c})compare(x,c);
        }
    } else if(name=="exhaustive") {
        for(std::size_t c=1;c<=4096;c*=2)for(std::uint64_t x=0;x<8*c;++x)compare(x,c);
    } else if(name=="random") {
        std::uint64_t x=20260923;
        for(unsigned i=0;i<1000000;++i) {
            x^=x<<13;x^=x>>7;x^=x<<17;
            compare(x,std::size_t(1)<<(i%std::numeric_limits<std::size_t>::digits));
        }
    } else if(name=="capacities") {
        // Exact four formulas used by engine construction, including private API limits.
        for(std::size_t n=64;n<=16384;n*=2)for(std::size_t b=1;b<=16384;++b) {
            const std::array<std::size_t,4> cs={capacity(n*8+b*4),capacity(n*16+b*16),
                capacity(std::max<std::size_t>(65536,b*64+n*32)),capacity(std::max<std::size_t>(65536,b*64+n*16))};
            for(auto c:cs)for(auto x:std::array<std::uint64_t,3>{c-1,c,c+1})compare(x,c);
        }
    } else if(name=="wrapped_storage") {
        for(std::size_t c: {1u,2u,64u,256u,65536u}) {
            std::vector<std::uint64_t> reference(c),candidate(c);
            const auto start=std::numeric_limits<std::uint64_t>::max()-c*2;
            for(std::uint64_t i=0;i<c*4;++i) {
                const auto x=start+i;reference[x%c]=i;candidate[ring_index(x,c)]=i;compare(x,c);
            }
            require(reference==candidate);
        }
    } else require(false);
    require(comparisons>0);std::cout<<name<<" comparisons="<<comparisons<<" passed\n";return 0;
}catch(const std::exception&e){std::cerr<<e.what()<<'\n';return 1;}}
