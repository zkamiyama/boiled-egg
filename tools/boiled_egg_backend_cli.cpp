#include <boiled_egg/boiled_egg.hpp>
#include "wav_io.hpp"
#include <algorithm>
#include <cmath>
#include <iostream>
#include <limits>
#include <memory>
#include <stdexcept>
#include <string>
#include <vector>
namespace {
float number(const std::string& s){size_t end=0;const float v=std::stof(s,&end);if(end!=s.size()||!std::isfinite(v))throw std::runtime_error("invalid finite number: "+s);return v;}
uint32_t integer(const std::string& s){size_t end=0;const auto v=std::stoull(s,&end);if(end!=s.size()||s[0]=='-'||v==0||v>1024)throw std::runtime_error("block must be1..1024");return static_cast<uint32_t>(v);}
}
int main(int argc,char** argv){try{
    if(argc<3)throw std::runtime_error("usage: boiled_egg_backend_cli INPUT OUTPUT [--backend wsola|pv] [--quality general|transient|efficient] [--formant off|harmonic|monophonic] [--time R] [--pitch-ratio R] [--formant-ratio R] [--block N] [--allow-experimental]");
    auto b=boiledegg_default_backend_config();b.io_contract=BOILEDEGG_IO_STREAMING;uint32_t block=64;
    for(int i=3;i<argc;++i){const std::string key=argv[i];if(key=="--allow-experimental"){b.flags|=BOILEDEGG_BACKEND_ALLOW_EXPERIMENTAL;continue;}
        if(i+1>=argc)throw std::runtime_error("missing value: "+key);const std::string value=argv[++i];
        if(key=="--backend"){if(value=="wsola")b.backend_id=0;else if(value=="pv")b.backend_id=1;else throw std::runtime_error("invalid backend");}
        else if(key=="--quality"){if(value=="general")b.quality_mode=0;else if(value=="transient")b.quality_mode=1;else if(value=="efficient")b.quality_mode=2;else throw std::runtime_error("invalid quality");}
        else if(key=="--formant"){if(value=="off")b.formant_policy=0;else if(value=="harmonic")b.formant_policy=1;else if(value=="monophonic")b.formant_policy=2;else throw std::runtime_error("invalid formant policy");}
        else if(key=="--time")b.initial_time_ratio=number(value);
        else if(key=="--pitch-ratio")b.initial_pitch_ratio=number(value);
        else if(key=="--formant-ratio")b.initial_formant_ratio=number(value);
        else if(key=="--block")block=integer(value);
        else throw std::runtime_error("unknown argument: "+key);
    }
    if(std::string(argv[1])==argv[2])throw std::runtime_error("input and output paths must differ");
    WavData input;std::string error;if(!read_wav(argv[1],input,error))throw std::runtime_error(error);
    const auto frames=input.interleaved.size()/input.channels;
    auto config=boiledegg_default_config(input.sample_rate,input.channels);config.max_block_size=block;
    boiled_egg::engine engine(config,b);
    std::vector<std::vector<float>> in(input.channels,std::vector<float>(block)),out(input.channels,std::vector<float>(4096));
    std::vector<const float*> ip(input.channels);std::vector<float*> op(input.channels);
    for(unsigned ch=0;ch<input.channels;++ch){ip[ch]=in[ch].data();op[ch]=out[ch].data();}
    WavData rendered;rendered.sample_rate=input.sample_rate;rendered.channels=input.channels;
    const auto target=static_cast<size_t>(std::llround(double(frames)*b.initial_time_ratio));
    rendered.interleaved.reserve(target*input.channels);
    auto drain=[&]{uint64_t sum=0;while(engine.available()){
        const auto n=engine.pull(op.data(),4096);if(!n)throw std::runtime_error("pull stalled");sum+=n;
        for(uint32_t i=0;i<n;++i)for(unsigned ch=0;ch<input.channels;++ch)rendered.interleaved.push_back(out[ch][i]);}return sum;};
    for(size_t pos=0;pos<frames;){const auto n=static_cast<uint32_t>(std::min<size_t>(block,frames-pos));
        for(unsigned ch=0;ch<input.channels;++ch)for(unsigned i=0;i<n;++i)in[ch][i]=input.interleaved[(pos+i)*input.channels+ch];
        uint32_t consumed=0;while(consumed<n){for(unsigned ch=0;ch<input.channels;++ch)ip[ch]=in[ch].data()+consumed;
            auto accepted=engine.push(ip.data(),n-consumed);consumed+=accepted;const auto pulled=drain();
            if(!accepted&&!pulled)throw std::runtime_error("stream made no progress");}pos+=n;
    }
    engine.flush();drain();
    for(unsigned idle=0;!engine.drained();){const auto n=engine.pull(op.data(),4096);
        for(uint32_t i=0;i<n;++i)for(unsigned ch=0;ch<input.channels;++ch)rendered.interleaved.push_back(out[ch][i]);
        if(!n){if(++idle>8)throw std::runtime_error("end-of-stream stalled");}else idle=0;}
    if(rendered.interleaved.size()!=target*input.channels)throw std::runtime_error("exact duration mismatch; output not published");
    for(float v:rendered.interleaved)if(!std::isfinite(v))throw std::runtime_error("nonfinite output");
    if(!write_wav_float32(argv[2],rendered,error))throw std::runtime_error(error);
    std::cout<<"backend="<<b.backend_id<<" formant_policy="<<b.formant_policy<<" input_frames="<<frames<<" output_frames="<<target<<"\n";
}catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}}
