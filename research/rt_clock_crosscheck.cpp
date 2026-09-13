// Standalone Linux diagnostic: never linked into product callback code.
// perf TASK_CLOCK is a software clock, NOT retired-work/frequency evidence.
#include "boiled_egg_research_host.hpp"
#include <array>
#include <cerrno>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <iostream>
#include <linux/perf_event.h>
#include <sched.h>
#include <stdexcept>
#include <string>
#include <sys/ioctl.h>
#include <sys/resource.h>
#include <sys/syscall.h>
#include <time.h>
#include <unistd.h>
#include <vector>
static std::int64_t ns(clockid_t id){timespec t{};if(clock_gettime(id,&t))throw std::runtime_error("clock");return std::int64_t(t.tv_sec)*1000000000+t.tv_nsec;}
class Counter {
    int fd_{-1};
public:
    Counter(){perf_event_attr a{};a.type=PERF_TYPE_SOFTWARE;a.size=sizeof(a);a.config=PERF_COUNT_SW_TASK_CLOCK;a.disabled=1;a.exclude_kernel=1;a.exclude_hv=1;
        fd_=static_cast<int>(syscall(__NR_perf_event_open,&a,0,-1,-1,0));
        if(fd_<0)throw std::runtime_error(std::string("software TASK_CLOCK unavailable: ")+std::strerror(errno));
        if(ioctl(fd_,PERF_EVENT_IOC_RESET,0)||ioctl(fd_,PERF_EVENT_IOC_ENABLE,0)){close(fd_);fd_=-1;throw std::runtime_error("enable counter");}}
    ~Counter(){if(fd_>=0)close(fd_);}
    std::uint64_t value()const {std::uint64_t n=0;if(read(fd_,&n,sizeof(n))!=sizeof(n))throw std::runtime_error("read counter");return n;}
};
struct Row{std::int64_t cpu{},wall{};std::uint64_t software{};long switches{},minor{},major{};std::uint64_t frames{};};
int main(int argc,char**argv){try{
    if(argc!=4)throw std::runtime_error("usage: clock_crosscheck fuzzy|multires|control count repeat");
    const std::string mode=argv[1];const unsigned count=std::stoul(argv[2]),repeat=std::stoul(argv[3]);
    if((mode!="fuzzy"&&mode!="multires"&&mode!="control")||count<1||count>1000000||repeat<1)throw std::runtime_error("args");
    cpu_set_t mask;CPU_ZERO(&mask);CPU_SET(0,&mask);if(sched_setaffinity(0,sizeof(mask),&mask))throw std::runtime_error("affinity");
    auto cfg=boiledegg_research_host_default_config(96000,2,32);cfg.profile=mode=="multires"?3:2;cfg.pitch_ratio=std::exp2(7.F/12);cfg.formant_ratio=.75F;
    boiled_egg::research::fixed_latency_engine h(cfg);
    std::vector<Row> rows(count);std::array<float,32> l{},r{},ol{},orr{};
    const float* input[]={l.data(),r.data()};float* output[]={ol.data(),orr.data()};
    unsigned random=291;Counter counter;
    for(unsigned i=0;i<count;++i){
        for(unsigned k=0;k<32;++k){random=1664525U*random+1013904223U;double t=double(std::uint64_t(i)*32+k)/96000;
            l[k]=float(.2*std::sin(6.283185307179586*123*t)+.05*(double(random>>8)/16777216.-.5));r[k]=-.5F*l[k];}
        std::array<boiledegg_research_host_event,4> events{};
        for(unsigned k=0;k<4;++k)events[k]={sizeof(events[k]),k*8,(i+k)%2?.65F:1.7F,0};
        rusage a{},b{};getrusage(RUSAGE_THREAD,&a);
        auto p0=counter.value();auto c0=ns(CLOCK_THREAD_CPUTIME_ID),w0=ns(CLOCK_MONOTONIC_RAW);
        if(mode=="control") {std::uint64_t v=771;for(unsigned k=0;k<80000;++k){v=v*6364136223846793005ULL+1442695040888963407ULL;asm volatile("":"+r"(v));}}
        else if(h.process(input,output,32,events.data(),4))throw std::runtime_error("process failed");
        auto w1=ns(CLOCK_MONOTONIC_RAW),c1=ns(CLOCK_THREAD_CPUTIME_ID);auto p1=counter.value();getrusage(RUSAGE_THREAD,&b);
        boiledegg_research_host_stats st{};st.struct_size=sizeof(st);
        if(boiledegg_research_host_get_stats(h.native_handle(),&st)||st.underruns||st.execution.frame_overruns)throw std::runtime_error("algorithmic underrun");
        rows[i]={c1-c0,w1-w0,p1-p0,b.ru_nivcsw+b.ru_nvcsw-a.ru_nivcsw-a.ru_nvcsw,b.ru_minflt-a.ru_minflt,b.ru_majflt-a.ru_majflt,st.execution.completed_frames};
    }
    std::cout<<"mode,repeat,index,cpu_ns,wall_ns,task_clock_bracket_ns,context_switches,minor_faults,major_faults,completed_frames\n";
    for(unsigned i=0;i<count;++i){auto&r=rows[i];std::printf("%s,%u,%u,%lld,%lld,%llu,%ld,%ld,%ld,%llu\n",mode.c_str(),repeat,i,(long long)r.cpu,(long long)r.wall,(unsigned long long)r.software,r.switches,r.minor,r.major,(unsigned long long)r.frames);}
}catch(const std::exception&e){std::cerr<<e.what()<<'\n';return 1;}}
