// Same executable with different SDK libraries. Timing never includes file IO or hashing.
#include <boiled_egg/boiled_egg.h>
#include <algorithm>
#include <array>
#include <bit>
#include <chrono>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <stdexcept>
#include <string>
#include <vector>
using Clock=std::chrono::steady_clock;
static double seconds(Clock::time_point a){return std::chrono::duration<double>(Clock::now()-a).count();}
static void require(bool b,const char* m){if(!b)throw std::runtime_error(m);}
template<class T> void save(const std::string& p,const std::vector<T>& v){
 auto f=std::fopen(p.c_str(),"wb");require(f,"open evidence");auto n=std::fwrite(v.data(),sizeof(T),v.size(),f);auto rc=std::fclose(f);require(n==v.size()&&!rc,"write evidence");
}
int main(int argc,char** argv){try{
 require(argc==8,"rate channels block time pitch stream|rt output-prefix");
 const unsigned rate=std::stoul(argv[1]),channels=std::stoul(argv[2]),block=std::stoul(argv[3]);
 const float time=std::stof(argv[4]),pitch=std::stof(argv[5]);const bool rt=std::string(argv[6])=="rt";const std::string out=argv[7];
 require((rate==48000||rate==96000)&&(channels==1||channels==2)&&(block==32||block==64),"scope");
 require(std::isfinite(time)&&time>=.25f&&time<=4&&std::isfinite(pitch)&&pitch>=.25f&&pitch<=4,"ratios");
 require(std::string(argv[6])=="stream"||rt,"mode");require(!rt||time==1,"RT time");
 require(std::endian::native==std::endian::little,"evidence endian");
 const unsigned frames=2*rate;auto cfg=boiledegg_default_config(rate,channels);cfg.max_block_size=block;
 boiledegg_result result{};auto t=Clock::now();auto cold=boiledegg_create(&cfg,&result);double cold_seconds=seconds(t);require(cold&&result==BOILEDEGG_OK,"cold create");boiledegg_destroy(cold);
 t=Clock::now();auto h=boiledegg_create(&cfg,&result);double warm_seconds=seconds(t);require(h&&result==BOILEDEGG_OK,"warm create");
 require(boiledegg_set_time_ratio(h,time)==BOILEDEGG_OK&&boiledegg_set_pitch_ratio(h,pitch)==BOILEDEGG_OK,"set params");
 boiledegg_runtime_info info{};info.struct_size=sizeof(info);require(boiledegg_get_runtime_info(h,&info)==BOILEDEGG_OK,"runtime info");
 std::vector<float> input(frames*channels),pcm;pcm.reserve((frames*4+8192)*channels);
 for(unsigned i=0;i<frames;++i)for(unsigned ch=0;ch<channels;++ch)input[ch*frames+i]=float(int((i*37u+19u)%509u)-254)/1024.f*(ch?.5f:1.f);
 std::vector<double> calls,services;calls.reserve(frames*12/block+1024);services.reserve(frames/block+1);
 std::array<float,128> scratch{};std::array<float*,2> output{scratch.data(),scratch.data()+64};
 double native_seconds=0;unsigned accepted_total=0,pulls=0,underruns=0;const auto start=Clock::now();
 auto drain=[&]{
  uint32_t n=0;const auto b=Clock::now();auto rc=boiledegg_pull(h,output.data(),block,&n);const auto dt=seconds(b);native_seconds+=dt;calls.push_back(dt);++pulls;
  require(rc==BOILEDEGG_OK&&n<=block,"pull");
  for(unsigned i=0;i<n;++i)for(unsigned ch=0;ch<channels;++ch)pcm.push_back(output[ch][i]);
  return n;
 };
 for(unsigned pos=0;pos<frames;pos+=block){
  const float* source[2]={input.data()+pos,input.data()+(channels>1?frames:0)+pos};const auto b=Clock::now();
  if(rt){
   auto rc=boiledegg_process_realtime(h,source,output.data(),block,nullptr,0);auto dt=seconds(b);native_seconds+=dt;calls.push_back(dt);services.push_back(dt);
   require(rc==BOILEDEGG_OK||rc==BOILEDEGG_REALTIME_UNDERRUN,"RT call");underruns+=rc==BOILEDEGG_REALTIME_UNDERRUN;accepted_total+=block;
   for(unsigned i=0;i<block;++i)for(unsigned ch=0;ch<channels;++ch)pcm.push_back(output[ch][i]);
  }else{
   uint32_t n=0;auto rc=boiledegg_push(h,source,block,&n);auto dt=seconds(b);native_seconds+=dt;calls.push_back(dt);
   require(rc==BOILEDEGG_OK&&n==block,"push");accepted_total+=n;
   unsigned guard=0;while(boiledegg_available(h)){require(drain()>0&&++guard<16*frames/block,"service progress");}
   services.push_back(seconds(b));
  }
 }
 const double streaming_native=native_seconds;const auto before_eof=Clock::now();
 if(!rt){auto b=Clock::now();auto rc=boiledegg_flush(h);auto dt=seconds(b);native_seconds+=dt;calls.push_back(dt);require(rc==BOILEDEGG_OK||rc==BOILEDEGG_BUFFER_FULL,"flush");unsigned idle=0;while(!boiledegg_is_drained(h)){auto n=drain();idle=n?0:idle+1;require(idle<32,"EOF progress");}}
 const double eof_seconds=seconds(before_eof),wall_seconds=seconds(start);
 const auto expected=rt?frames:static_cast<unsigned>(std::llround(double(frames)*double(time)));
 require(pcm.size()==static_cast<size_t>(expected)*channels&&accepted_total==frames,"duration");
 double energy=0,peak=0;for(float v:pcm){require(std::isfinite(v),"finite");energy+=double(v)*v;peak=std::max(peak,std::abs(double(v)));}require(energy>0,"nonzero");
 boiledegg_destroy(h);save(out+".f32",pcm);save(out+".calls.f64",calls);save(out+".services.f64",services);
 std::printf("{\"rate\":%u,\"channels\":%u,\"block\":%u,\"time\":%.9g,\"pitch\":%.9g,\"rt\":%s,\"input_frames\":%u,\"output_frames\":%u,\"input_blocks\":%u,\"api_calls\":%zu,\"pulls\":%u,\"underruns\":%u,\"native_seconds\":%.17g,\"pre_eof_native_seconds\":%.17g,\"wall_seconds\":%.17g,\"eof_seconds\":%.17g,\"cold_create_seconds\":%.17g,\"warm_create_seconds\":%.17g,\"peak\":%.17g,\"energy\":%.17g,\"window\":%u,\"latency\":%u,\"tail\":%u}\n",rate,channels,block,time,pitch,rt?"true":"false",frames,expected,frames/block,calls.size(),pulls,underruns,native_seconds,streaming_native,wall_seconds,eof_seconds,cold_seconds,warm_seconds,peak,energy,cfg.window_frames,info.realtime_latency_frames,info.realtime_tail_frames);
 return 0;
}catch(const std::exception& e){std::fprintf(stderr,"%s\n",e.what());return 2;}}
