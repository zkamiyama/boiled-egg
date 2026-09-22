// Public ABI regression for #62. No assert-only checks, no output trimming.
#include <boiled_egg/boiled_egg.h>
#include <algorithm>
#include <array>
#include <atomic>
#include <bit>
#include <chrono>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <future>
#include <limits>
#include <new>
#include <stdexcept>
#include <string>
#include <vector>

static std::atomic<uint64_t> allocations{0};
void* operator new(std::size_t n) { ++allocations; if(auto p=std::malloc(n?n:1))return p; throw std::bad_alloc(); }
void* operator new[](std::size_t n) { return ::operator new(n); }
void operator delete(void* p) noexcept {std::free(p);}
void operator delete[](void* p) noexcept {std::free(p);}
void operator delete(void* p,std::size_t) noexcept {std::free(p);}
void operator delete[](void* p,std::size_t) noexcept {std::free(p);}
namespace {
void require(bool b,const char* why) {if(!b)throw std::runtime_error(why);}
constexpr unsigned max_frames=384000;
struct Step {unsigned end;float time,pitch;};
struct Case {unsigned rate,channels,quality,frames,block;float time,pitch;bool pressure=false;};
struct Result {
 uint64_t frames=0,hash=1469598103934665603ULL,violations=0,max_excess=0,allocs=0,partial=0;
 uint64_t target=0,source_hash=1469598103934665603ULL;
 double energy=0,proportional=0,seconds=0;
 bool finite=true,drained=false;
};
void hash_float(uint64_t& h,float f) {h=(h^std::bit_cast<uint32_t>(f))*1099511628211ULL;}
// FNV is a regression trace only; artifact identities use SHA256 externally.
struct Host {
 Case c;boiledegg_handle* h=nullptr;
 std::vector<float> input,pcm,scratch;
 std::vector<double> call_times;
 Host(Case cfg):c(cfg),input(c.channels*c.frames),pcm(c.channels*(4*c.frames+8192)),scratch(c.channels*4096) {
  auto config=boiledegg_default_config(c.rate,c.channels);config.max_block_size=257;
  if(c.pressure)config.fifo_frames=config.window_frames*8u+config.max_block_size*2u;
  auto profile=boiledegg_default_profile();profile.quality_mode=c.quality;
  boiledegg_result rc;h=boiledegg_create_ex(&config,&profile,&rc);require(h&&rc==BOILEDEGG_OK,"create");
  for(unsigned i=0;i<c.frames;++i) {
   float x=static_cast<float>(static_cast<int>((i*37u+19u)%509u)-254)/1024.f;
   for(unsigned ch=0;ch<c.channels;++ch)input[ch*c.frames+i]=ch?x*.5f:x;
  }
  call_times.reserve(4*c.frames+65536);
 }
 ~Host(){boiledegg_destroy(h);}
 void save(const std::string& root,unsigned id,const Result& r) const {
  require(std::endian::native==std::endian::little,"PCM artifact byte order");
  const std::string path=root+"/"+std::to_string(id)+".f32";
  auto fp=std::fopen(path.c_str(),"wb");require(fp,"PCM artifact open");
  const auto n=static_cast<size_t>(r.frames)*c.channels;
  const bool ok=std::fwrite(pcm.data(),sizeof(float),n,fp)==n;
  const auto close=std::fclose(fp);require(ok&&close==0,"PCM artifact write");
 }
 Result render(const std::vector<Step>& steps={},bool timing=false) {
  require(boiledegg_set_time_ratio(h,c.time)==BOILEDEGG_OK,"time");
  require(boiledegg_set_pitch_ratio(h,c.pitch)==BOILEDEGG_OK,"pitch");
  require(boiledegg_reset(h)==BOILEDEGG_OK,"reset");
  Result r;long double budget=0;unsigned pos=0,step=0;float time=c.time;
  uint64_t guard=0;bool stalled_pressure=false;
  call_times.clear();std::fill(pcm.begin(),pcm.end(),0.f);
  for(float v:input)hash_float(r.source_hash,v);
  const auto a0=allocations.load();const auto start=std::chrono::steady_clock::now();
  auto check_budget=[&] {
   const auto limit=static_cast<uint64_t>(budget);
   const auto released=r.frames+boiledegg_available(h);
   if(released>limit){++r.violations;r.max_excess=std::max(r.max_excess,released-limit);}
  };
  auto pull=[&](bool flushing) {
   std::array<float*,2> op{scratch.data(),scratch.data()+4096};uint32_t n=0;
   auto t0=std::chrono::steady_clock::now();
   require(boiledegg_pull(h,op.data(),c.block,&n)==BOILEDEGG_OK,"pull");
   if(timing)call_times.push_back(std::chrono::duration<double>(std::chrono::steady_clock::now()-t0).count());
   require(n<=c.block&&r.frames+n<=pcm.size()/c.channels,"output bound");
   for(unsigned i=0;i<n;++i)for(unsigned ch=0;ch<c.channels;++ch) {
    const float v=op[ch][i];r.finite=r.finite&&std::isfinite(v);r.energy+=double(v)*v;
    if(ch)r.proportional=std::max(r.proportional,std::abs(double(v)-.5*op[0][i]));
    pcm[(r.frames+i)*c.channels+ch]=v;hash_float(r.hash,v);
   }
   r.frames+=n;if(!flushing)check_budget();return n;
  };
  while(pos<c.frames) {
   if(!steps.empty()&&step<steps.size()) {
    require(pos<steps[step].end,"step schedule");time=steps[step].time;
    require(boiledegg_set_time_ratio(h,time)==BOILEDEGG_OK,"step time");
    require(boiledegg_set_pitch_ratio(h,steps[step].pitch)==BOILEDEGG_OK,"step pitch");
   }
   unsigned n=std::min(c.block,c.frames-pos);
   if(!steps.empty())n=std::min(n,steps[step].end-pos);
   std::array<const float*,2> ip{input.data()+pos,input.data()+(c.channels>1?c.frames:0)+pos};uint32_t accepted=0;
   auto t0=std::chrono::steady_clock::now();auto rc=boiledegg_push(h,ip.data(),n,&accepted);
   if(timing)call_times.push_back(std::chrono::duration<double>(std::chrono::steady_clock::now()-t0).count());
   require((rc==BOILEDEGG_OK||rc==BOILEDEGG_BUFFER_FULL)&&accepted<=n,"push");
   pos+=accepted;budget+=static_cast<long double>(accepted)*time;check_budget();
   if(accepted<n){++r.partial;stalled_pressure=true;}
   uint32_t made=0;
   if(!c.pressure||stalled_pressure||pos==c.frames) {
    do {made+=pull(false);require(++guard<8*max_frames,"stream progress");}while(boiledegg_available(h));
   }
   require(accepted||made,"no progress");
   if(!steps.empty()&&pos==steps[step].end)++step;
  }
  r.target=static_cast<uint64_t>(std::llround(budget));
  auto frc=boiledegg_flush(h);require(frc==BOILEDEGG_OK||frc==BOILEDEGG_BUFFER_FULL,"flush");
  unsigned idle=0;
  while(!boiledegg_is_drained(h)) {auto n=pull(true);idle=n?0:idle+1;require(idle<32&&++guard<8*max_frames,"EOF progress");}
  require(boiledegg_flush(h)==BOILEDEGG_OK,"repeat flush");require(pull(true)==0,"extra EOF output");
  r.drained=boiledegg_is_drained(h)!=0;
  r.seconds=std::chrono::duration<double>(std::chrono::steady_clock::now()-start).count();
  r.allocs=allocations.load()-a0;return r;
 }
};
void row(const char* mode,const Case& c,const Result& r,const char* error="") {
 std::printf("%s,%u,%u,%u,%u,%u,%.9g,%.9g,%llu,%llu,%llu,%llu,%llu,%llu,%llu,%llu,%.17g,%.17g,%.9g,%s\n",
 mode,c.rate,c.channels,c.quality,c.frames,c.block,c.time,c.pitch,
 (unsigned long long)r.frames,(unsigned long long)r.target,(unsigned long long)r.hash,
 (unsigned long long)r.source_hash,(unsigned long long)r.violations,(unsigned long long)r.max_excess,
 (unsigned long long)r.allocs,(unsigned long long)r.partial,r.energy,r.proportional,r.seconds,error);
}
bool valid(const Result& r) {return r.frames==r.target&&!r.violations&&!r.allocs&&r.finite&&r.drained&&r.proportional<1e-6&&(!r.frames||r.energy>0);}
}
int main(int argc,char**argv){try {
 require(argc>=2,"mode required");std::string mode=argv[1];unsigned failures=0,cases=0;
 std::puts("mode,rate,channels,quality,input,block,time,pitch,output,target,pcm_hash,input_hash,violations,max_excess,allocations,partial_pushes,energy,proportional_error,seconds,error");
 auto test=[&](Case c,const std::vector<Step>& steps=std::vector<Step>{}) {
  ++cases;
  try {Host h(c);auto r=h.render(steps);if(argc>2)h.save(argv[2],cases,r);row(mode.c_str(),c,r);if(!valid(r))++failures;return r;}
  catch(const std::exception& e){++failures;Result r;r.hash=0;row(mode.c_str(),c,r,e.what());return r;}
 };
 if(mode=="repro") {
  for(unsigned sr:{48000u,96000u})for(unsigned ch:{1u,2u})for(unsigned b:{32u,64u,257u})
   for(auto op:std::array<std::array<float,2>,3>{{{.25f,1},{1,.25f},{.5f,.5f}}})test({sr,ch,0,2*sr,b,op[0],op[1]});
 }else if(mode=="corners") {
  unsigned j=0;
  for(unsigned sr:{48000u,96000u})for(unsigned ch:{1u,2u})for(unsigned q:{0u,1u,2u})
   for(unsigned n:{0u,1u,2u,3u,17u,255u,1153u,8193u})for(float t:{.25f,.5f,1.f,2.f,4.f})for(float p:{.25f,.5f,1.f,2.f,4.f})
    test({sr,ch,q,n,std::array<unsigned,3>{32,64,257}[j++%3],t,p});
  for(unsigned sr:{48000u,96000u})for(float t:{.3f,.8f,1.37f,3.99f})for(float p:{.37f,1.19f,2.73f})test({sr,2,0,8193,64,t,p});
 }else if(mode=="partition") {
  for(unsigned sr:{48000u,96000u})for(unsigned q:{0u,1u,2u})
   for(auto op:std::array<std::array<float,2>,5>{{{.25f,1},{1,.25f},{.5f,.5f},{1.25f,1.3348398f},{4,4}}}) {
    uint64_t hash=0;
    for(unsigned b:{32u,64u,257u}) {auto r=test({sr,2,q,2*sr+37,b,op[0],op[1]});if(hash&&hash!=r.hash)++failures;hash=r.hash;}
   }
 }else if(mode=="dynamic") {
  const std::vector<Step> steps{{3073,.25f,1},{6151,4,.25f},{10001,.5f,.5f},{17371,1.25f,2},{24017,.25f,4},{32771,2,1}};
  for(unsigned sr:{48000u,96000u})for(unsigned ch:{1u,2u})for(unsigned q:{0u,1u,2u})for(unsigned b:{32u,64u,257u}) {
   Case c{sr,ch,q,steps.back().end,b,1,1};Host h(c);auto a=h.render(steps);if(argc>2)h.save(argv[2],cases+1,a);auto z=h.render(steps);if(argc>2)h.save(argv[2],cases+2,z);
   row("dynamic",c,a);row("reset",c,z);cases+=2;if(!valid(a)||!valid(z)||a.hash!=z.hash)++failures;
  }
 }else if(mode=="pressure") {
  unsigned saturated=0;
  for(unsigned sr:{48000u,96000u})for(float t:{.25f,1.f,4.f})for(float p:{.25f,1.f,4.f}) {
   auto r=test({sr,2,0,131071,257,t,p,true});if(r.partial)++saturated;
  }
  // Compression can fit in combined input/intermediate/output storage without
  // a partial push. Require actual saturation in the group, not in every cell.
  if(saturated<2)++failures;
 }else if(mode=="invalid") {
  Case c{48000,2,0,8193,64,.25f,.25f};Host h(c);auto a=h.render();
  require(boiledegg_reset(h.h)==BOILEDEGG_OK,"reset invalid");
  uint32_t accepted=99;require(boiledegg_push(h.h,nullptr,7,&accepted)==BOILEDEGG_INVALID_ARGUMENT&&accepted==0,"invalid push");
  require(boiledegg_set_time_ratio(h.h,0)==BOILEDEGG_INVALID_ARGUMENT,"invalid time");
  require(boiledegg_set_pitch_ratio(h.h,std::numeric_limits<float>::quiet_NaN())==BOILEDEGG_INVALID_ARGUMENT,"invalid pitch");
  require(boiledegg_push(h.h,nullptr,0,&accepted)==BOILEDEGG_OK&&accepted==0,"zero push");
  require(boiledegg_flush(h.h)==BOILEDEGG_OK&&boiledegg_is_drained(h.h),"empty flush");
  auto z=h.render();if(argc>2)h.save(argv[2],1,z);row("invalid-reset",c,z);cases=1;if(!valid(z)||a.hash!=z.hash)++failures;
 }else if(mode=="noalloc") {
  for(float t:{.25f,1.f,4.f})for(float p:{.25f,1.f,4.f})test({48000,2,0,48000,32,t,p});
 }else if(mode=="bench") {
  for(unsigned sr:{48000u,96000u})for(unsigned b:{32u,64u})for(unsigned ch:{1u,2u})
   for(auto op:std::array<std::array<float,2>,4>{{{1,1},{.25f,1},{1,.25f},{1.25f,1.3348398f}}}) {
    Case c{sr,ch,0,2*sr,b,op[0],op[1]};Host h(c);
    for(unsigned rep=0;rep<3;++rep){auto r=h.render({},true);row("bench",c,r);++cases;
     if(argc>2){std::string name=std::string(argv[2])+"/"+std::to_string(cases)+".f64";auto fp=std::fopen(name.c_str(),"wb");require(fp,"timing file");require(std::fwrite(h.call_times.data(),sizeof(double),h.call_times.size(),fp)==h.call_times.size(),"timing write");std::fclose(fp);}
    }
   }
 }else throw std::runtime_error("unknown mode");
 std::fprintf(stderr,"cases=%u failures=%u\n",cases,failures);return failures?1:0;
}catch(const std::exception&e){std::fprintf(stderr,"ERROR %s\n",e.what());return 2;}}
