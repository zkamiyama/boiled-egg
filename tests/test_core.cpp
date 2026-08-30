#include <boiled_egg/boiled_egg.hpp>

#include <algorithm>
#include <cmath>
#include <cstdint>
#include <iostream>
#include <vector>

static constexpr double pi=3.14159265358979323846;

struct Rendered { std::vector<std::vector<float>> ch; };

static Rendered render(uint32_t sr, uint32_t channels, uint32_t frames, float time_ratio, float pitch_st) {
    boiled_egg::engine e(sr,channels);
    e.set_time_ratio(time_ratio); e.set_pitch_semitones(pitch_st);
    constexpr uint32_t B=256;
    std::vector<std::vector<float>> in(channels,std::vector<float>(B));
    std::vector<const float*> ip(channels);
    std::vector<std::vector<float>> out(channels,std::vector<float>(B*4));
    std::vector<float*> op(channels);
    for(uint32_t c=0;c<channels;++c){ip[c]=in[c].data();op[c]=out[c].data();}
    Rendered r; r.ch.resize(channels);
    auto drain=[&](){ while(e.available()){auto n=e.pull(op.data(),B*4);for(uint32_t c=0;c<channels;++c)r.ch[c].insert(r.ch[c].end(),out[c].begin(),out[c].begin()+n);} };
    for(uint32_t pos=0;pos<frames;){
        uint32_t n=std::min(B,frames-pos);
        for(uint32_t i=0;i<n;++i) for(uint32_t c=0;c<channels;++c) in[c][i]=0.5f*std::sin(2*pi*440.0*(pos+i)/sr + c*0.2);
        uint32_t off=0; while(off<n){std::vector<const float*> p(channels);for(uint32_t c=0;c<channels;++c)p[c]=in[c].data()+off; auto a=e.push(p.data(),n-off);off+=a;drain();if(!a) return r;}
        pos+=n; drain();
    }
    e.flush();
    for(int g=0;g<10000 && !e.drained();++g){drain(); if(!e.available()){auto n=e.pull(op.data(),B*4);for(uint32_t c=0;c<channels;++c)r.ch[c].insert(r.ch[c].end(),out[c].begin(),out[c].begin()+n);}}
    drain();
    return r;
}

static bool finite(const Rendered& r){for(auto& c:r.ch)for(float x:c)if(!std::isfinite(x))return false;return true;}

int main(){
    const uint32_t sr=48000, frames=sr*2;
    auto id=render(sr,2,frames,1.0f,0.0f);
    if(!finite(id)){std::cerr<<"non-finite identity\n";return 1;}
    if(std::llabs((long long)id.ch[0].size()-(long long)frames)>2){std::cerr<<"identity duration "<<id.ch[0].size()<<"\n";return 2;}
    auto slow=render(sr,1,frames,1.5f,0.0f);
    if(std::llabs((long long)slow.ch[0].size()-(long long)std::llround(frames*1.5))>2){std::cerr<<"stretch duration\n";return 3;}
    auto pitch=render(sr,1,frames,1.0f,12.0f);
    if(!finite(pitch) || std::llabs((long long)pitch.ch[0].size()-(long long)frames)>2){std::cerr<<"pitch render\n";return 4;}
    boiled_egg::engine e(48000,2);
    if(e.input_latency_frames()<512){std::cerr<<"latency unexpected\n";return 5;}
    std::cout<<"core tests ok\n";
    return 0;
}
