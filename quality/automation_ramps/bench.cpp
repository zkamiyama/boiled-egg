// Explicit-ramp input/control replay (steps, linear/logarithmic, interruptions). One wall clock only; output hashing
// and source generation are outside the measured bracket. No best-run pooling
// is called a successful uninterrupted run. Run three repeats before summary.
#include <boiled_egg/boiled_egg.hpp>
#include <algorithm>
#include <array>
#include <bit>
#include <cmath>
#include <cstdint>
#include <ctime>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <stdexcept>
#include <vector>
static std::uint64_t wall(){timespec t{};if(clock_gettime(CLOCK_MONOTONIC_RAW,&t))throw std::runtime_error("clock failed");return std::uint64_t(t.tv_sec)*1000000000ULL+std::uint64_t(t.tv_nsec);}
struct Row {unsigned rate,quality,policy,block,index,warm;std::uint64_t elapsed,fingerprint;};
int main(int argc,char** argv){try{
 if(argc!=2)throw std::runtime_error("usage: dynamic_bench REPEAT1..3");unsigned repeat=std::stoul(argv[1]);if(repeat<1||repeat>3)throw std::runtime_error("repeat range");
 std::vector<Row> rows;rows.reserve(110000);
 for(unsigned rate:{48000u,96000u})for(unsigned quality:{0u,1u})for(unsigned policy:{0u,1u,2u})for(unsigned block:{32u,64u}){
  auto c=boiledegg_default_config(rate,2);c.max_block_size=block;auto b=boiledegg_default_backend_config();b.backend_id=1;b.quality_mode=quality;b.formant_policy=policy;b.io_contract=2;b.flags=3;
  boiled_egg::engine h(c,b);const auto L=h.runtime_info().realtime_latency_frames;
  const unsigned warm=(L+rate/2+block-1)/block,iterations=warm+1200;
  std::array<std::vector<float>,2> x{std::vector<float>(block),std::vector<float>(block)},y=x;
  const float* in[]={x[0].data(),x[1].data()};float* out[]={y[0].data(),y[1].data()};std::uint32_t rng=7913;
  for(unsigned i=0;i<iterations;++i){for(unsigned n=0;n<block;++n){rng=1664525u*rng+1013904223u;const double t=double(i*block+n)/rate;
    x[0][n]=float(.2*std::sin(6.283185307179586*120*t)+.08*std::sin(6.283185307179586*3713*t)+.02*(double(rng>>8)/16777216.-.5));x[1][n]=-.5f*x[0][n];}
   // Cover alternating endpoints as well as intermediate target changes.
   const float ratios[]={.5f,.6674199f,.8408964f,1.f,1.1892071f,1.4983071f,2.f};
   std::array<boiledegg_ramp_event,2> events{{
       {sizeof(boiledegg_ramp_event),0,BOILEDEGG_PARAMETER_PITCH_RATIO,
        i%3==0?0u:i%3==1?1u:4800u,i%2,ratios[(i/17)%7],{0,0}},
       {sizeof(boiledegg_ramp_event),block/2,BOILEDEGG_PARAMETER_PITCH_RATIO,
        1001u,(i+1)%2,ratios[(i/19+2)%7],{0,0}}}};
   const auto start=wall();
   const auto formant=boiledegg_set_formant_ratio(h.native_handle(),policy?(i%2?.75f:1.5f):1.f);
   const auto status=h.process_realtime_ramps_nothrow(in,out,block,events);const auto stop=wall();
   if(formant!=BOILEDEGG_OK)throw std::runtime_error("formant update failed");
   if(status!=BOILEDEGG_OK)throw std::runtime_error("dynamic process underrun/error");
   std::uint64_t hash=1469598103934665603ULL;for(auto& ch:y)for(float v:ch){if(!std::isfinite(v))throw std::runtime_error("nonfinite audio");hash^=std::bit_cast<std::uint32_t>(v);hash*=1099511628211ULL;}
   rows.push_back({rate,quality,policy,block,i,i<warm?1u:0u,stop-start,hash});
  }
 }
 std::cout<<"repeat,rate,quality,policy,block,index,warmup,wall_ns,fingerprint\n";
 for(const auto& r:rows)std::cout<<repeat<<','<<r.rate<<','<<r.quality<<','<<r.policy<<','<<r.block<<','<<r.index<<','<<r.warm<<','<<r.elapsed<<','<<r.fingerprint<<'\n';
}catch(const std::exception& error){std::cerr<<error.what()<<'\n';return 1;}}
