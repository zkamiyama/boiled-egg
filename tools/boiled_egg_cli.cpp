#include <boiled_egg/boiled_egg.hpp>
#include "wav_io.hpp"
#include <algorithm>
#include <cstdlib>
#include <cmath>
#include <iostream>
#include <string>
#include <vector>
static void usage(){std::cerr<<"usage: boiled_egg_cli INPUT.wav OUTPUT.wav [--time RATIO] [--pitch SEMITONES] [--block N]\n";}
int main(int argc,char** argv){
 if(argc<3){usage();return 2;} float time_ratio=1.0f,pitch_st=0.0f; uint32_t block=256;
 for(int i=3;i<argc;++i){std::string a=argv[i]; if(a=="--time"&&i+1<argc)time_ratio=std::strtof(argv[++i],nullptr); else if(a=="--pitch"&&i+1<argc)pitch_st=std::strtof(argv[++i],nullptr); else if(a=="--block"&&i+1<argc)block=static_cast<uint32_t>(std::strtoul(argv[++i],nullptr,10)); else {usage();return 2;}}
 WavData in; std::string err; if(!read_wav(argv[1],in,err)){std::cerr<<err<<"\n";return 1;} const uint64_t in_frames=in.interleaved.size()/in.channels;
 auto cfg=boiledegg_default_config(in.sample_rate,in.channels); cfg.max_block_size=std::max<uint32_t>(block,64u); boiled_egg::engine e(cfg); e.set_time_ratio(time_ratio); e.set_pitch_semitones(pitch_st);
 std::vector<std::vector<float>> pin(in.channels,std::vector<float>(block)),pout(in.channels,std::vector<float>(block*4u)); std::vector<float*> out_ptr(in.channels); for(uint16_t ch=0;ch<in.channels;++ch)out_ptr[ch]=pout[ch].data();
 WavData out; out.sample_rate=in.sample_rate; out.channels=in.channels; out.interleaved.reserve(static_cast<size_t>(in_frames*time_ratio+4096)*in.channels);
 auto drain=[&](){while(e.available()){uint32_t n=e.pull(out_ptr.data(),static_cast<uint32_t>(pout[0].size()));for(uint32_t i=0;i<n;++i)for(uint16_t ch=0;ch<in.channels;++ch)out.interleaved.push_back(pout[ch][i]);}};
 uint64_t pos=0; while(pos<in_frames){uint32_t n=static_cast<uint32_t>(std::min<uint64_t>(block,in_frames-pos));for(uint16_t ch=0;ch<in.channels;++ch)for(uint32_t i=0;i<n;++i)pin[ch][i]=in.interleaved[static_cast<size_t>(pos+i)*in.channels+ch];uint32_t offset=0;while(offset<n){std::vector<const float*> ptr(in.channels);for(uint16_t ch=0;ch<in.channels;++ch)ptr[ch]=pin[ch].data()+offset;uint32_t accepted=e.push(ptr.data(),n-offset);offset+=accepted;drain();if(!accepted)return 1;}pos+=n;drain();}
 e.flush(); for(int guard=0;guard<100000&&!e.drained();++guard){drain();if(!e.available()){uint32_t n=e.pull(out_ptr.data(),static_cast<uint32_t>(pout[0].size()));for(uint32_t i=0;i<n;++i)for(uint16_t ch=0;ch<in.channels;++ch)out.interleaved.push_back(pout[ch][i]);if(n==0&&e.drained())break;}} drain();
 uint64_t target=static_cast<uint64_t>(std::llround(static_cast<double>(in_frames)*time_ratio));if(out.interleaved.size()/in.channels>target)out.interleaved.resize(static_cast<size_t>(target)*in.channels);if(!write_wav_float32(argv[2],out,err)){std::cerr<<err<<"\n";return 1;}std::cout<<"input_frames="<<in_frames<<" output_frames="<<(out.interleaved.size()/in.channels)<<" target_frames="<<target<<" latency_in="<<e.input_latency_frames()<<"\n";return 0;}
