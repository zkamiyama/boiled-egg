// Reuse the reviewed public-ABI streaming host; no alternative timing path in DSP.
#define main budget_fixture_main
#include "../streaming_budget/test.cpp"
#undef main
#include <ctime>
static double thread_seconds() {
    timespec t{};
    if (clock_gettime(CLOCK_THREAD_CPUTIME_ID,&t)) throw std::runtime_error("thread clock");
    return double(t.tv_sec)+double(t.tv_nsec)*1e-9;
}
static void write_binary(const std::string& path,const void* data,size_t size) {
    auto f=std::fopen(path.c_str(),"wb");require(f,"binary output");
    const auto n=std::fwrite(data,1,size,f);auto close=std::fclose(f);require(n==size&&close==0,"binary write");
}
int main(int argc,char** argv) {try {
    require(argc==3,"case index and new directory required");
    const unsigned index=static_cast<unsigned>(std::stoul(argv[1])); require(index<56,"unknown case");
    const std::string dir=argv[2];
    Case c{};bool rt=index>=32;
    if(!rt) {
        unsigned k=0;
        for(unsigned sr:{48000u,96000u})for(unsigned b:{32u,64u})for(unsigned ch:{1u,2u})
        for(auto op:std::array<std::array<float,2>,4>{{{1,1},{.25f,1},{1,.25f},{1.25f,1.3348398f}}}) {
            if(k++==index)c={sr,ch,0,2*sr,b,op[0],op[1]};
        }
    } else {
        unsigned k=32;
        for(unsigned sr:{48000u,96000u})for(unsigned b:{32u,64u})for(unsigned q:{0u,1u,2u})for(float pitch:{1.f,2.f})
            if(k++==index)c={sr,2,q,2*sr,b,1,pitch};
    }
    const auto create_start=std::chrono::steady_clock::now();
    Host host(c); // Constructs source/buffers too; report as cold fixture+create, not create-only.
    const auto create_seconds=std::chrono::duration<double>(std::chrono::steady_clock::now()-create_start).count();
    double cpu=thread_seconds();Result r;std::vector<double> times;
    if(!rt) {
        r=host.render({},true);cpu=thread_seconds()-cpu;require(valid(r),"stream contract");times=host.call_times;
        host.save(dir,1,r);
    } else {
        require(boiledegg_set_pitch_ratio(host.h,c.pitch)==BOILEDEGG_OK,"rt pitch");
        boiledegg_runtime_info info{};info.struct_size=sizeof(info);
        require(boiledegg_get_runtime_info(host.h,&info)==BOILEDEGG_OK,"runtime info");
        const unsigned frames=c.frames+info.realtime_latency_frames+info.realtime_tail_frames;
        const unsigned total=(frames+c.block-1)/c.block*c.block;
        std::vector<float> input(size_t(c.channels)*total),output(size_t(c.channels)*total),pcm(size_t(c.channels)*total);
        for(unsigned ch=0;ch<c.channels;++ch)std::copy_n(host.input.data()+ch*c.frames,c.frames,input.data()+ch*total);
        times.reserve(total/c.block);const auto alloc_before=allocations.load();const auto start=std::chrono::steady_clock::now();cpu=thread_seconds();
        for(unsigned pos=0;pos<total;pos+=c.block) {
            const float* ip[]{input.data()+pos,input.data()+total+pos};float* op[]{output.data()+pos,output.data()+total+pos};
            auto t=std::chrono::steady_clock::now();const auto rc=boiledegg_process_realtime(host.h,ip,op,c.block,nullptr,0);
            times.push_back(std::chrono::duration<double>(std::chrono::steady_clock::now()-t).count());
            require(rc==BOILEDEGG_OK,"rt callback error");
        }
        cpu=thread_seconds()-cpu;r.seconds=std::chrono::duration<double>(std::chrono::steady_clock::now()-start).count();
        r.allocs=allocations.load()-alloc_before;require(r.allocs==0,"rt allocation");r.frames=total;
        for(unsigned i=0;i<total;++i)for(unsigned ch=0;ch<c.channels;++ch){float v=output[ch*total+i];require(std::isfinite(v),"rt finite");r.energy+=double(v)*v;hash_float(r.hash,v);pcm[i*c.channels+ch]=v;}
        require(r.energy>0,"silent realtime");write_binary(dir+"/1.f32",pcm.data(),pcm.size()*sizeof(float));
    }
    require(!times.empty(),"no timed calls");write_binary(dir+"/calls.f64",times.data(),times.size()*sizeof(double));
    double native=0;for(auto v:times)native+=v;auto sorted=times;std::sort(sorted.begin(),sorted.end());
    unsigned over80=0;for(auto t:times)if(t>.8*double(c.block)/c.rate)++over80;
    const unsigned blocks=(c.frames+c.block-1)/c.block;
    std::printf("{\"case\":%u,\"io\":\"%s\",\"rate\":%u,\"block\":%u,\"channels\":%u,\"quality\":%u,\"time\":%.9g,\"pitch\":%.9g,\"input_frames\":%u,\"output_frames\":%llu,\"pcm_fnv\":%llu,\"energy\":%.17g,\"allocations\":%llu,\"fixture_create_seconds\":%.17g,\"wall_seconds\":%.17g,\"thread_seconds\":%.17g,\"native_seconds\":%.17g,\"native_per_input_block\":%.17g,\"calls\":%zu,\"p99_seconds\":%.17g,\"max_seconds\":%.17g,\"over_80_percent\":%u}\n",
       index,rt?"realtime":"streaming",c.rate,c.block,c.channels,c.quality,c.time,c.pitch,c.frames,(unsigned long long)r.frames,(unsigned long long)r.hash,r.energy,(unsigned long long)r.allocs,create_seconds,r.seconds,cpu,native,native/blocks,times.size(),sorted[(sorted.size()-1)*99/100],sorted.back(),over80);
    return 0;
} catch(const std::exception& e){std::fprintf(stderr,"ERROR %s\n",e.what());return 2;}}
