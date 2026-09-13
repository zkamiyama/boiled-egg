// Linux x86_64 diagnostic only. TSC ticks are NOT retired cycles or CPU frequency.
// Even an invariant TSC can be virtualized. Never linked into the SDK hot path.
#include "boiled_egg_research_host.hpp"
#include <array>
#include <cerrno>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <iostream>
#include <stdexcept>
#include <string>
#include <vector>
#include <cpuid.h>
#include <x86intrin.h>
#include <linux/perf_event.h>
#include <sched.h>
#include <sys/resource.h>
#include <sys/syscall.h>
#include <time.h>
#include <unistd.h>
static std::int64_t ns(clockid_t id){timespec t{};if(clock_gettime(id,&t))throw std::runtime_error("clock");return std::int64_t(t.tv_sec)*1000000000LL+t.tv_nsec;}
static std::uint64_t tsc(unsigned& aux){_mm_lfence();auto t=__rdtscp(&aux);_mm_lfence();return t;}
struct Row {std::int64_t cpu,wall;std::uint64_t ticks,completed;long switches,minor,major;unsigned a,b;};
int main(int argc,char** argv){try{
    if(argc!=4)throw std::runtime_error("usage: rt_tsc_probe fuzzy|control|noop count repeat");
    const std::string mode=argv[1];unsigned count=std::stoul(argv[2]),repeat=std::stoul(argv[3]);
    if((mode!="fuzzy"&&mode!="control"&&mode!="noop")||count<1||count>1000000||!repeat)throw std::runtime_error("arguments");
    unsigned a,b,c,d;const unsigned max=__get_cpuid_max(0x80000000U,nullptr);
    if(max<0x80000001U)throw std::runtime_error("extended CPUID unavailable");
    __cpuid(0x80000001U,a,b,c,d);if(!(d&(1U<<27)))throw std::runtime_error("RDTSCP unavailable");
    __cpuid(1U,a,b,c,d);const bool hv=(c&(1U<<31))!=0;
    bool invariant=false;if(max>=0x80000007U){__cpuid(0x80000007U,a,b,c,d);invariant=(d&(1U<<8))!=0;}
    cpu_set_t allowed;CPU_ZERO(&allowed);if(sched_getaffinity(0,sizeof(allowed),&allowed))throw std::runtime_error("get affinity");
    int chosen=-1;for(int i=0;i<CPU_SETSIZE;++i)if(CPU_ISSET(i,&allowed)){chosen=i;break;}
    if(chosen<0)throw std::runtime_error("no allowed cpu");cpu_set_t mask;CPU_ZERO(&mask);CPU_SET(chosen,&mask);
    if(sched_setaffinity(0,sizeof(mask),&mask))throw std::runtime_error("set affinity");
    perf_event_attr pa{};pa.type=PERF_TYPE_HARDWARE;pa.config=PERF_COUNT_HW_INSTRUCTIONS;pa.size=sizeof(pa);pa.exclude_kernel=1;pa.exclude_hv=1;
    int fd=int(syscall(__NR_perf_event_open,&pa,0,-1,-1,0)),error=fd<0?errno:0;if(fd>=0)close(fd);
    std::cerr<<"cpu="<<chosen<<" hypervisor="<<hv<<" invariant_tsc="<<invariant<<" instructions_perf_errno="<<error<<" ("<<std::strerror(error)<<")\n";
    auto cfg=boiledegg_research_host_default_config(96000,2,32);cfg.pitch_ratio=std::exp2(7.F/12);cfg.formant_ratio=.75F;
    boiled_egg::research::fixed_latency_engine h(cfg);
    std::vector<Row> rows(count);std::array<float,32> l{},r{},ol{},orr{};
    const float* input[]={l.data(),r.data()};float* output[]={ol.data(),orr.data()};unsigned random=791;
    for(unsigned n=0;n<count;++n){
        for(unsigned k=0;k<32;++k){random=1664525U*random+1013904223U;double t=double(std::uint64_t(n)*32+k)/96000;
            l[k]=float(.2*std::sin(6.283185307179586*123*t)+.05*(double(random>>8U)/16777216.-.5));r[k]=-.5F*l[k];}
        std::array<boiledegg_research_host_event,4> events{};
        for(unsigned k=0;k<4;++k)events[k]={sizeof(events[k]),k*8,(n+k)%2?.65F:1.7F,0};
        rusage before{},after{};if(getrusage(RUSAGE_THREAD,&before))throw std::runtime_error("rusage");unsigned aux0=0,aux1=0;
        // Nested brackets: TSC includes the adjacent CPU/wall clock calls.
        auto t0=tsc(aux0);auto c0=ns(CLOCK_THREAD_CPUTIME_ID);auto w0=ns(CLOCK_MONOTONIC_RAW);
        if(mode=="control") {std::uint64_t v=771;for(unsigned k=0;k<80000;++k){v=v*6364136223846793005ULL+1442695040888963407ULL;asm volatile("":"+r"(v));}}
        else if(mode=="fuzzy"&&h.process(input,output,32,events.data(),4))throw std::runtime_error("audio failure");
        auto w1=ns(CLOCK_MONOTONIC_RAW);auto c1=ns(CLOCK_THREAD_CPUTIME_ID);auto t1=tsc(aux1);
        if(getrusage(RUSAGE_THREAD,&after))throw std::runtime_error("rusage");
        boiledegg_research_host_stats st{};st.struct_size=sizeof(st);
        if(boiledegg_research_host_get_stats(h.native_handle(),&st)||st.underruns||st.execution.frame_overruns)throw std::runtime_error("algorithmic underrun");
        rows[n]={c1-c0,w1-w0,t1-t0,st.execution.completed_frames,
            after.ru_nvcsw+after.ru_nivcsw-before.ru_nvcsw-before.ru_nivcsw,
            after.ru_minflt-before.ru_minflt,after.ru_majflt-before.ru_majflt,aux0,aux1};
    }
    std::puts("mode,repeat,index,cpu_ns,wall_ns,tsc_ticks,completed_frames,guest_switches,minor_faults,major_faults,tsc_aux_before,tsc_aux_after");
    for(unsigned n=0;n<count;++n){auto&r=rows[n];std::printf("%s,%u,%u,%lld,%lld,%llu,%llu,%ld,%ld,%ld,%u,%u\n",mode.c_str(),repeat,n,(long long)r.cpu,(long long)r.wall,(unsigned long long)r.ticks,(unsigned long long)r.completed,r.switches,r.minor,r.major,r.a,r.b);}
}catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}}
