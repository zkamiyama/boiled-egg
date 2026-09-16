// Same-source executable built against each library in SEPARATE processes.
// Exact hashes compare a cached implementation against the verified full pooled
// predecessor, not against the original defective static phase path.
#define main inherited_spatial_main
#include "spatial_regression.cpp"
#undef main
#include <iomanip>

static std::uint64_t fingerprint(const Audio& x) {
    std::uint64_t h=1469598103934665603ULL;
    for(const auto& channel:x)for(float v:channel) {
        h^=std::bit_cast<std::uint32_t>(v);h*=1099511628211ULL;
    }
    return h;
}
static Audio diverse_input(unsigned rate,unsigned family) {
    auto x=input(8193,-.375f);unsigned random=26091637;
    if(!family)return x;
    for(unsigned i=0;i<x[0].size();++i) {
        random=1664525u*random+1013904223u;const double t=double(i)/rate;
        const bool silent=(i<503 || (i>2701 && i<3711));
        x[0][i]=silent?0.f:float(.09*std::sin(6.283185307179586*(61*t+700*t*t))
                       +.025*(double(random>>8)/16777216.-.5));
        random=1664525u*random+1013904223u;
        x[1][i]=silent?0.f:float(.07*std::cos(6.283185307179586*(271*t+2700*t*t))
                       +.03*(double(random>>8)/16777216.-.5));
        if(i==4019 || i==6803)x[i%2][i]+=.4f;
    }
    return x;
}
int main(){try{
    std::cout<<"rate,quality,policy,realtime,pitch,family,dynamic,frames,hash\n";
    for(unsigned rate:{48000u,96000u})for(unsigned quality:{0u,1u})
    for(unsigned policy:{0u,1u,2u})for(bool realtime:{false,true})
    for(float pitch:{.5f,1.f,2.f})for(unsigned family:{0u,1u}) {
        auto x=diverse_input(rate,family);
        auto a=render(x,rate,quality,policy,pitch,32,realtime,false);
        auto b=render(x,rate,quality,policy,pitch,257,realtime,false);
        require(a==b,"cached static partition differs");
        if(family==0)require(error(a,-.375)<1e-5,"cached proportionality");
        std::cout<<rate<<','<<quality<<','<<policy<<','<<realtime<<','<<pitch<<','<<family
                 <<",0,"<<a[0].size()<<','<<fingerprint(a)<<'\n';
    }
    for(unsigned rate:{48000u,96000u})for(unsigned quality:{0u,1u})for(unsigned policy:{0u,1u,2u}) {
        auto x=diverse_input(rate,1);
        auto a=render(x,rate,quality,policy,1.f,32,true,true);
        auto b=render(x,rate,quality,policy,1.f,257,true,true);
        require(a==b,"dynamic partition differs");
        std::cout<<rate<<','<<quality<<','<<policy<<",1,1,1,1,"<<a[0].size()<<','<<fingerprint(a)<<'\n';
    }
}catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}}
