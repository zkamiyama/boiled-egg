// Public-ABI duration regression. Builds once and runs against either SDK.
#include <boiled_egg/boiled_egg.h>
#include <algorithm>
#include <array>
#include <cmath>
#include <cstdint>
#include <cstring>
#include <fstream>
#include <iostream>
#include <stdexcept>
#include <string>
#include <vector>
namespace {
void require(bool b, const char* s) { if (!b) throw std::runtime_error(s); }
struct Case { unsigned rate, frames, block, channels, quality; float time, pitch; unsigned dynamic=0; bool backlog=false; };
struct Result { std::vector<float> pcm; uint64_t target=0, before_flush=0, premature=0; double energy=0, stereo=0; unsigned partial=0; };
struct Owner {
    boiledegg_handle* p;
    explicit Owner(const Case& c) {
        auto cfg=boiledegg_default_config(c.rate,c.channels); cfg.max_block_size=c.block;
        if(c.backlog)cfg.fifo_frames=cfg.window_frames*8+c.block*2;
        auto profile=boiledegg_default_profile();profile.quality_mode=c.quality;
        boiledegg_result rc{}; p=boiledegg_create_ex(&cfg,&profile,&rc);
        require(p && rc==BOILEDEGG_OK,"create");
    }
    ~Owner(){boiledegg_destroy(p);}
};
uint64_t hash(const std::vector<float>& v) {
    uint64_t h=14695981039346656037ULL;
    for(float x:v){uint32_t b=0;std::memcpy(&b,&x,4);for(int j=0;j<4;++j){h^=(b>>(j*8))&255u;h*=1099511628211ULL;}}
    return h;
}
Result render(boiledegg_handle* h,const Case& c) {
    std::array<std::vector<float>,2> in,buf;
    for(unsigned ch=0;ch<c.channels;++ch){in[ch].resize(c.frames);buf[ch].resize(257);}
    for(unsigned i=0;i<c.frames;++i){
        // Nonzero broadband signal, not a pitch-quality oracle.
        in[0][i]=float(int((i*73u+37u)%1021u)-510)/2048.f;
        if(c.channels==2)in[1][i]=.5f*in[0][i];
    }
    Result r;r.pcm.reserve((uint64_t(c.frames)*4+8192)*c.channels);
    double budget=0; uint64_t read=0; bool eof=false;
    auto drain=[&] {
        unsigned guard=0;
        do {
            float* op[2]={buf[0].data(),buf[1].data()};uint32_t made=0;
            require(boiledegg_pull(h,op,257,&made)==BOILEDEGG_OK && made<=257,"pull");
            require(++guard<100000 && read+made<=uint64_t(c.frames)*4+8192,"drain progress");
            for(unsigned i=0;i<made;++i){
                for(unsigned ch=0;ch<c.channels;++ch){require(std::isfinite(buf[ch][i]),"nonfinite");r.pcm.push_back(buf[ch][i]);}
                r.energy+=double(buf[0][i])*buf[0][i];
                if(c.channels==2)r.stereo=std::max(r.stereo,std::abs(double(buf[1][i])-.5*buf[0][i]));
            }
            read+=made;
            if(!eof){auto limit=uint64_t(std::floor(budget));r.premature=std::max(r.premature,read+boiledegg_available(h)>limit?read+boiledegg_available(h)-limit:0);}
            if(!made)break;
        } while(boiledegg_available(h));
    };
    unsigned pos=0, stalls=0;
    while(pos<c.frames){
        unsigned end=c.frames;float t=c.time,p=c.pitch;
        if(c.dynamic){
            unsigned first=c.frames/3,second=2*c.frames/3;
            unsigned segment=pos<first?0:(pos<second?1:2);
            end=segment==0?first:(segment==1?second:c.frames);
            const float ts[2][3]={{.25f,2.f,.5f},{4.f,.25f,1.25f}};
            const float ps[2][3]={{1.f,.5f,.25f},{.25f,2.f,1.f}};
            t=ts[c.dynamic-1][segment];p=ps[c.dynamic-1][segment];
        }
        require(boiledegg_set_time_ratio(h,t)==BOILEDEGG_OK && boiledegg_set_pitch_ratio(h,p)==BOILEDEGG_OK,"set");
        unsigned n=std::min(c.block,end-pos);uint32_t accepted=0;
        const float* ip[2]={in[0].data()+pos,c.channels==2?in[1].data()+pos:nullptr};
        auto rc=boiledegg_push(h,ip,n,&accepted);
        require((rc==BOILEDEGG_OK || rc==BOILEDEGG_BUFFER_FULL)&&accepted<=n,"push");
        if(accepted<n)++r.partial;
        pos+=accepted;budget+=double(accepted)*t;
        auto limit=uint64_t(std::floor(budget));r.premature=std::max(r.premature,read+boiledegg_available(h)>limit?read+boiledegg_available(h)-limit:0);
        if(!c.backlog || accepted<n || pos==c.frames)drain();
        stalls=accepted?0:stalls+1;require(stalls<4,"push stalled");
    }
    r.before_flush=read+boiledegg_available(h);r.target=uint64_t(std::llround(budget));eof=true;
    auto rc=boiledegg_flush(h);require(rc==BOILEDEGG_OK || rc==BOILEDEGG_BUFFER_FULL,"flush");
    for(unsigned i=0;!boiledegg_is_drained(h);++i){require(i<1000,"EOF stalled");drain();}
    require(boiledegg_flush(h)==BOILEDEGG_OK,"repeat flush");drain();
    uint32_t accepted=99;const float* ip[2]={in[0].data(),in[1].data()};
    require(boiledegg_push(h,ip,1,&accepted)==BOILEDEGG_END_OF_STREAM && accepted==0,"push after EOF");
    return r;
}
std::vector<Case> cases(const std::string& mode){
    std::vector<Case> out;
    const std::array<std::array<float,2>,7> ops={{{.25f,1.f},{1.f,.25f},{.5f,.5f},{1.f,1.f},{2.f,2.f},{4.f,4.f},{1.25f,1.334839854f}}};
    if(mode=="repro")for(unsigned r:{48000u,96000u})for(unsigned i=0;i<3;++i)out.push_back({r,2*r,64,1,0,ops[i][0],ops[i][1]});
    else if(mode=="edges")for(unsigned r:{48000u,96000u})for(unsigned n:{0u,1u,2u,3u,17u,511u,1152u,4097u})for(const auto& op:ops)out.push_back({r,n,64,2,0,op[0],op[1]});
    else if(mode=="partitions")for(unsigned r:{48000u,96000u})for(unsigned ch:{1u,2u})for(unsigned b:{32u,64u,257u})for(unsigned q:{0u,1u,2u})for(const auto& op:ops)out.push_back({r,8193,b,ch,q,op[0],op[1]});
    else if(mode=="dynamic")for(unsigned r:{48000u,96000u})for(unsigned b:{32u,64u,257u})for(unsigned d:{1u,2u})out.push_back({r,16385,b,2,0,1.f,1.f,d});
    else if(mode=="backpressure")for(unsigned r:{48000u,96000u})for(const auto& op:ops)out.push_back({r,2*r+17,64,2,0,op[0],op[1],0,true});
    else throw std::runtime_error("unknown test mode");
    return out;
}
}
int main(int argc,char** argv){try{
    require(argc>=2 && argc<=4,"usage: check MODE [observe [raw-prefix]]");bool observe=argc>=3 && std::string(argv[2])=="observe";
    auto grid=cases(argv[1]);
    const std::string mode=argv[1];
    const size_t expected=mode=="repro"?6:(mode=="edges"?112:(mode=="partitions"?252:(mode=="dynamic"?12:14)));
    require(grid.size()==expected,"incomplete test inventory");
    require(argc==2 || observe,"unknown execution option");unsigned failed=0;
    std::cout<<"index,rate,frames,block,channels,quality,time,pitch,dynamic,backlog,target,output,before_flush,premature,partial,energy,stereo,hash,repeat,status\n";
    for(size_t i=0;i<grid.size();++i){const auto& c=grid[i];try {Owner h(c);auto r=render(h.p,c);
        require(boiledegg_reset(h.p)==BOILEDEGG_OK,"reset");auto again=render(h.p,c);bool repeat=r.pcm==again.pcm && r.premature==again.premature;
        bool ok=r.pcm.size()/c.channels==r.target && !r.premature && repeat && r.stereo<=3e-6 && (!c.backlog||r.partial>0) && (!c.frames||!r.target||r.energy>1e-30);
        if(!ok)++failed;
        if(argc==4){std::ofstream f(std::string(argv[3])+"-"+std::to_string(i)+".f32",std::ios::binary);f.write(reinterpret_cast<const char*>(r.pcm.data()),std::streamsize(r.pcm.size()*4));require(bool(f),"raw write");}
        std::cout.precision(17);std::cout<<i<<','<<c.rate<<','<<c.frames<<','<<c.block<<','<<c.channels<<','<<c.quality<<','<<c.time<<','<<c.pitch<<','<<c.dynamic<<','<<c.backlog<<','<<r.target<<','<<r.pcm.size()/c.channels<<','<<r.before_flush<<','<<r.premature<<','<<r.partial<<','<<r.energy<<','<<r.stereo<<','<<hash(r.pcm)<<','<<repeat<<",complete\n";
    } catch(const std::exception& e){++failed;std::cerr<<"index="<<i<<" error="<<e.what()<<'\n';
      std::cout<<i<<','<<c.rate<<','<<c.frames<<','<<c.block<<','<<c.channels<<','<<c.quality<<','<<c.time<<','<<c.pitch<<','<<c.dynamic<<','<<c.backlog<<",,,,,,,,,,failed\n"; }
    }
    std::cerr<<"cases="<<grid.size()<<" failures="<<failed<<" observe="<<observe<<'\n';
    return failed&&!observe?2:0;
}catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}}
