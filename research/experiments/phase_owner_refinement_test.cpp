#include "../cpp_pv_rt/src/phase_owner_refinement.hpp"
#include <array>
#include <iostream>
#include <numeric>
#include <random>
#include <stdexcept>
#include <vector>
namespace p=boiled_egg::research::detail::phase_owner_refinement;
void require(bool v,const char* s){if(!v)throw std::runtime_error(s);}
std::uint32_t oracle(std::uint32_t k,std::uint32_t bins,float hop,const float* f,const std::uint32_t* owners){
    auto result=k;float best=std::numbers::pi_v<float>/static_cast<float>(2U*(bins-1U));
    for(int offset=-4;offset<=4;++offset){
        auto n=static_cast<std::uint32_t>(std::clamp(int(k)+offset,0,int(bins)-1));auto candidate=owners[n];
        float d=std::abs(p::wrap((f[k]-f[candidate])*hop))/hop;
        if(d<best){best=d;result=candidate;}
    }
    return result;
}
int main(){try{
    std::array<float,17> f{};std::array<std::uint32_t,17> owners{};
    owners.fill(3);f.fill(.1F);f[3]=.9F;f[8]=.4F;
    require(p::select(8,17,4.F,f.data(),owners.data())==8,"no compatible peak uses own bin");
    owners[10]=12;f[12]=.401F;
    require(p::select(8,17,4.F,f.data(),owners.data())==12,"neighbor peak selected");
    f[12]=.4F+2.F*std::numbers::pi_v<float>/4.F;
    require(p::select(8,17,4.F,f.data(),owners.data())==12,"hop alias is compatible");
    owners.fill(3);f[3]=.1F;f[0]=.1F;
    require(p::select(0,17,4.F,f.data(),owners.data())==3,"left edge clamps safely");
    f[16]=.1F;require(p::select(16,17,4.F,f.data(),owners.data())==3,"right edge clamps safely");
    std::mt19937 rng(714041);unsigned checked=0;
    for(unsigned bins:{33U,513U,1025U})for(float hop:{64.F,256.F,512.F}){
        std::vector<float> frequencies(bins);std::vector<unsigned> own(bins);
        for(unsigned repeat=0;repeat<40;++repeat){
            for(unsigned k=0;k<bins;++k){frequencies[k]=float(rng()%10001U)*.0001F;own[k]=(k/7U)*7U;}
            auto before=frequencies;auto before_owners=own;
            for(unsigned k=0;k<bins;++k){require(p::select(k,bins,hop,frequencies.data(),own.data())==oracle(k,bins,hop,frequencies.data(),own.data()),"optimized selection differs from exhaustive oracle");++checked;}
            require(before==frequencies && before_owners==own,"helper mutated input");
        }
    }
    std::cout<<checked<<" exact owner selections; neighbor, alias, edges, fallback and input purity passed\n";
}catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}}
