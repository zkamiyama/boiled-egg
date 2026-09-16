// Static spectral stereo path. Timing and input/output hashing are separate.
// Run each fixed pitch three times; use the existing dynamic-capacity summarizer.
// This is measured work capacity, not WCET or a continuous run stitched from minima.
#include <boiled_egg/boiled_egg.hpp>
#include <array>
#include <bit>
#include <cmath>
#include <cstdint>
#include <ctime>
#include <iostream>
#include <stdexcept>
#include <vector>
static std::uint64_t wall(){timespec t{};if(clock_gettime(CLOCK_MONOTONIC_RAW,&t))throw std::runtime_error("clock failed");return std::uint64_t(t.tv_sec)*1000000000ULL+std::uint64_t(t.tv_nsec);}
struct Row {unsigned rate,quality,policy,block,index,warm;std::uint64_t elapsed,fingerprint;};
int main(int argc,char** argv){try{
 if(argc!=3)throw std::runtime_error("usage: static_capacity REPEAT1..3 PITCH(.5|1|2)");
 unsigned repeat=std::stoul(argv[1]);float pitch=std::stof(argv[2]);
 if(repeat<1||repeat>3||(pitch!=.5f&&pitch!=1.f&&pitch!=2.f))throw std::runtime_error("arguments");
 std::vector<Row> rows;rows.reserve(110000);
 for(unsigned rate:{48000u,96000u})for(unsigned quality:{0u,1u})for(unsigned policy:{0u,1u,2u})for(unsigned block:{32u,64u}){
  auto c=boiledegg_default_config(rate,2);c.max_block_size=block;
  auto b=boiledegg_default_backend_config();b.backend_id=BOILEDEGG_BACKEND_PHASE_VOCODER;
  b.quality_mode=quality;b.formant_policy=policy;b.io_contract=BOILEDEGG_IO_REALTIME;
  b.flags=BOILEDEGG_BACKEND_ALLOW_EXPERIMENTAL;b.initial_pitch_ratio=pitch;
  boiled_egg::engine h(c,b);const auto latency=h.runtime_info().realtime_latency_frames;
  const unsigned warm=(latency+rate/2+block-1)/block,iterations=warm+1200;
  std::array<std::vector<float>,2> x{std::vector<float>(block),std::vector<float>(block)},y=x;
  const float* in[]={x[0].data(),x[1].data()};float* out[]={y[0].data(),y[1].data()};std::uint32_t rng=7913;
  for(unsigned i=0;i<iterations;++i){
   for(unsigned n=0;n<block;++n){rng=1664525u*rng+1013904223u;const double t=double(i*block+n)/rate;
    x[0][n]=float(.2*std::sin(6.283185307179586*120*t)+.08*std::sin(6.283185307179586*3713*t)+.02*(double(rng>>8)/16777216.-.5));
    x[1][n]=-.5f*x[0][n]+float(.03*std::sin(6.283185307179586*917*t));}
   std::array<boiled_egg::parameter_event,2> events{
    boiled_egg::parameter_event::formant_ratio(block/4,policy?(i%2?.75f:1.5f):1.f),
    boiled_egg::parameter_event::formant_ratio(3*block/4,policy?(i%2?1.5f:.75f):1.f)};
   const auto start=wall();const auto status=h.process_realtime_nothrow(in,out,block,events);const auto stop=wall();
   if(status!=BOILEDEGG_OK)throw std::runtime_error("static process underrun/error");
   std::uint64_t hash=1469598103934665603ULL;
   for(auto& ch:y)for(float v:ch){if(!std::isfinite(v))throw std::runtime_error("nonfinite audio");hash^=std::bit_cast<std::uint32_t>(v);hash*=1099511628211ULL;}
   rows.push_back({rate,quality,policy,block,i,i<warm?1u:0u,stop-start,hash});
  }
 }
 std::cout<<"repeat,rate,quality,policy,block,index,warmup,wall_ns,fingerprint\n";
 for(const auto& r:rows)std::cout<<repeat<<','<<r.rate<<','<<r.quality<<','<<r.policy<<','<<r.block<<','<<r.index<<','<<r.warm<<','<<r.elapsed<<','<<r.fingerprint<<'\n';
}catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}}
