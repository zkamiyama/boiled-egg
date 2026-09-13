// Diagnostic executable only: OS counters never enter the SDK's hot path.
#include "boiled_egg_research_host.hpp"
#include <array>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <iostream>
#include <stdexcept>
#include <string>
#include <vector>
#include <sys/resource.h>
#include <sched.h>
#include <time.h>
#if defined(__SSE2__)
#include <xmmintrin.h>
#endif
using namespace boiled_egg::research;
static std::int64_t ns(clockid_t id){timespec t{};if(clock_gettime(id,&t))throw std::runtime_error("clock unavailable");return std::int64_t(t.tv_sec)*1000000000LL+t.tv_nsec;}
struct Row{std::int64_t cpu{},wall{};long minor{},major{},voluntary{},involuntary{};int core0{},core1{};std::uint64_t completed{},frame_steps{};double energy{};};
int main(int argc,char** argv){try{
    if(argc!=10)throw std::runtime_error("profile rate block pitch callbacks repeat input(normal|tiny|decay|silence|noop) ftz(0|1) instrument(0|1)");
    unsigned profile=std::stoul(argv[1]),rate=std::stoul(argv[2]),block=std::stoul(argv[3]),count=std::stoul(argv[5]);
    float pitch=std::stof(argv[4]);int repeat=std::stoi(argv[6]),ftz=std::stoi(argv[8]),instrument=std::stoi(argv[9]);std::string input=argv[7];
    if(profile>4||block<1||block>16384||count<1||count>1000000||repeat<1||(ftz!=0&&ftz!=1)||(instrument!=0&&instrument!=1)||
       (input!="normal"&&input!="tiny"&&input!="decay"&&input!="silence"&&input!="noop"&&input!="control"))throw std::runtime_error("invalid arguments");
    unsigned old_mxcsr=0;
#if defined(__SSE2__)
    old_mxcsr=_mm_getcsr();_mm_setcsr(ftz?(old_mxcsr|0x8040U):(old_mxcsr&~0x8040U));
#else
    if(ftz)throw std::runtime_error("FTZ experiment requires SSE2");
#endif
    auto c=boiledegg_research_host_default_config(rate,2,block);c.profile=profile;c.pitch_ratio=pitch;c.formant_ratio=.75F;
    fixed_latency_engine engine(c);
    std::vector<Row> rows(count); // Fault/pre-touch all measurement storage before timing.
    std::array<std::vector<float>,2> x{std::vector<float>(block),std::vector<float>(block)},y=x;
    const float* in[]={x[0].data(),x[1].data()};float* out[]={y[0].data(),y[1].data()};
    std::uint32_t rng=701;std::uint64_t previous_completed=0;
    for(unsigned n=0;n<count;++n){
        for(unsigned i=0;i<block;++i){rng=1664525U*rng+1013904223U;double t=double(std::uint64_t(n)*block+i)/rate;
            float value=float(.2*std::sin(2*3.141592653589793*123*t)+.05*(double(rng>>8U)/16777216.-.5));
            if(input=="tiny")value*=1e-38F;else if(input=="silence"||input=="noop")value=0;
            else if(input=="decay")value*=float(std::exp(-16*t));
            x[0][i]=value;x[1][i]=-.5F*value;}
        std::array<boiledegg_research_host_event,4> ev{};
        for(unsigned i=0;i<4;++i)ev[i]={sizeof(ev[0]),i*block/4,(n+i)%2?.65F:1.7F,0};
        rusage a{},b{};if(instrument&&getrusage(RUSAGE_THREAD,&a))throw std::runtime_error("rusage before");
        int ca=instrument?sched_getcpu():-1;
        auto cb=ns(CLOCK_THREAD_CPUTIME_ID),wb=ns(CLOCK_MONOTONIC_RAW);
        if(input=="control"){
            std::uint64_t work=771;
            for(unsigned k=0;k<80000;++k){work=work*6364136223846793005ULL+1442695040888963407ULL;asm volatile("" : "+r"(work));}
        }
        auto status=(input=="noop"||input=="control")?BOILEDEGG_RESEARCH_PV_RT_OK:engine.process(in,out,block,ev.data(),4);
        auto we=ns(CLOCK_MONOTONIC_RAW),ce=ns(CLOCK_THREAD_CPUTIME_ID);
        int cz=instrument?sched_getcpu():-1;
        if(instrument&&getrusage(RUSAGE_THREAD,&b))throw std::runtime_error("rusage after");
        if(status)throw std::runtime_error("process failed");
        boiledegg_research_host_stats s{};s.struct_size=sizeof(s);
        if(boiledegg_research_host_get_stats(engine.native_handle(),&s)||s.underruns||s.execution.frame_overruns)throw std::runtime_error("algorithmic underrun");
        double energy=0;for(auto& ch:y)for(float v:ch){if(!std::isfinite(v))throw std::runtime_error("nonfinite");energy+=double(v)*v;}
        rows[n]={ce-cb,we-wb,b.ru_minflt-a.ru_minflt,b.ru_majflt-a.ru_majflt,b.ru_nvcsw-a.ru_nvcsw,b.ru_nivcsw-a.ru_nivcsw,ca,cz,
            s.execution.completed_frames-previous_completed,s.execution.max_frame_steps,energy};previous_completed=s.execution.completed_frames;
    }
#if defined(__SSE2__)
    _mm_setcsr(old_mxcsr);
#endif
    std::cout<<"repeat,profile,rate,block,pitch,input,ftz,instrument,index,cpu_ns,wall_ns,minor_faults,major_faults,voluntary,involuntary,cpu_before,cpu_after,completed_frames,max_frame_steps,output_energy\n";
    for(unsigned i=0;i<count;++i){auto& r=rows[i];std::printf("%d,%u,%u,%u,%.9g,%s,%d,%d,%u,%lld,%lld,%ld,%ld,%ld,%ld,%d,%d,%llu,%llu,%.17g\n",repeat,profile,rate,block,pitch,input.c_str(),ftz,instrument,i,(long long)r.cpu,(long long)r.wall,r.minor,r.major,r.voluntary,r.involuntary,r.core0,r.core1,(unsigned long long)r.completed,(unsigned long long)r.frame_steps,r.energy);}
}catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}}
