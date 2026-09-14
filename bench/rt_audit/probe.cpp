// Linux diagnostic, not a plugin/SDK hot-path dependency.
#include "protocol.hpp"
#ifdef BOILED_EGG_AUDIT_RESEARCH
#include "boiled_egg_research_host.h"
#else
#include <boiled_egg/boiled_egg.h>
#endif
#include <array>
#include <bit>
#include <cerrno>
#include <charconv>
#include <cmath>
#include <cstdio>
#include <iomanip>
#include <iostream>
#include <memory>
#include <stdexcept>
#include <string>
#include <vector>
#include <sched.h>
#include <sys/resource.h>
#include <time.h>
using namespace boiled_egg::bench;
static ns read_clock(clockid_t id) {
    timespec t{};if(clock_gettime(id,&t)) throw std::runtime_error("clock_gettime failed");
    return ns(t.tv_sec)*1000000000LL+t.tv_nsec;
}
struct clock_source {
    ns cpu(){return read_clock(CLOCK_THREAD_CPUTIME_ID);}
    ns wall(){return read_clock(CLOCK_MONOTONIC_RAW);}
};
static unsigned number(const char* text) {
    unsigned v{};const auto size=std::string_view(text).size();
    const auto result=std::from_chars(text,text+size,v);
    if(result.ec!=std::errc{}||result.ptr!=text+size)throw std::invalid_argument("invalid integer");
    return v;
}
struct backend {
#ifdef BOILED_EGG_AUDIT_RESEARCH
    using handle=std::unique_ptr<boiledegg_research_host_handle,decltype(&boiledegg_research_host_destroy)>;
    handle h{nullptr,boiledegg_research_host_destroy};
#else
    using handle=std::unique_ptr<boiledegg_handle,decltype(&boiledegg_destroy)>;
    handle h{nullptr,boiledegg_destroy};
#endif
    unsigned latency{};
    backend(unsigned rate,unsigned block,int shift) {
#ifdef BOILED_EGG_AUDIT_RESEARCH
        auto c=boiledegg_research_host_default_config(rate,2,block);
        c.pitch_ratio=std::exp2(float(shift)/12.F);c.formant_ratio=.75F;
        boiledegg_research_pv_rt_result result{};
        h.reset(boiledegg_research_host_create(&c,&result));
        if(!h||result)throw std::runtime_error("research backend creation failed");
        latency=boiledegg_research_host_latency_frames(h.get());
#else
        auto c=boiledegg_default_config(rate,2);c.max_block_size=block;
        boiledegg_result result{};h.reset(boiledegg_create(&c,&result));
        if(!h||result||boiledegg_set_pitch_semitones(h.get(),float(shift)))throw std::runtime_error("product backend creation failed");
        boiledegg_runtime_info info{};info.struct_size=sizeof(info);
        if(boiledegg_get_runtime_info(h.get(),&info))throw std::runtime_error("runtime info failed");
        latency=info.realtime_latency_frames;
#endif
    }
    int process(const float* const* in,float* const* out,unsigned block,unsigned n) {
#ifdef BOILED_EGG_AUDIT_RESEARCH
        std::array<boiledegg_research_host_event,4> events{};
        for(unsigned i=0;i<4;++i)events[i]={sizeof(events[0]),i*block/4,(n+i)%2?.65F:1.7F,0};
        return boiledegg_research_host_process(h.get(),in,out,block,events.data(),4);
#else
        (void)n;return boiledegg_process_realtime(h.get(),in,out,block,nullptr,0);
#endif
    }
};
struct row {interval time;ns outer{},period{},wake{-1},response{-1},slack{};unsigned missed{},status{};std::uint64_t hash{};};
int main(int argc,char** argv) {try {
    if(argc!=10)throw std::invalid_argument("probe COUNT WARMUP REPEAT dsp|control|noop saturated|periodic legacy|cpu|wall RATE BLOCK SHIFT");
    const auto count=number(argv[1]),requested=number(argv[2]),repeat=number(argv[3]);
    const std::string workload=argv[4],schedule=argv[5],bracket_name=argv[6];
    const auto kind=parse_bracket(bracket_name);const auto rate=number(argv[7]),block=number(argv[8]);
    int shift{};const auto parse=std::from_chars(argv[9],argv[9]+std::string_view(argv[9]).size(),shift);
    if(parse.ec!=std::errc{}||parse.ptr!=argv[9]+std::string_view(argv[9]).size()||shift < -12||shift>12 ||
       count<1||count>100000||requested>100000||!repeat||repeat>100||
       (rate!=44100&&rate!=48000&&rate!=96000)||(block!=32&&block!=64)||
       (workload!="dsp"&&workload!="control"&&workload!="noop")||
       (schedule!="saturated"&&schedule!="periodic"))throw std::invalid_argument("invalid configuration");
    cpu_set_t allowed;CPU_ZERO(&allowed);
    if(sched_getaffinity(0,sizeof(allowed),&allowed))throw std::runtime_error("get affinity failed");
    int cpu=-1;for(int i=0;i<CPU_SETSIZE;++i)if(CPU_ISSET(i,&allowed)){cpu=i;break;}
    if(cpu<0)throw std::runtime_error("no allowed CPU");
    CPU_ZERO(&allowed);CPU_SET(cpu,&allowed);
    if(sched_setaffinity(0,sizeof(allowed),&allowed))throw std::runtime_error("pin CPU failed");
    backend engine(rate,block,shift);
    const auto warmup=warmup_calls(requested,engine.latency,rate,block),total=warmup+count;
    std::vector<row> rows(total); // Value initialize / pre-fault before timed loop.
    std::array<std::vector<float>,2> input{std::vector<float>(std::size_t(total)*block),std::vector<float>(std::size_t(total)*block)};
    std::array<std::vector<float>,2> output{std::vector<float>(block),std::vector<float>(block)};
    unsigned random=701;
    for(std::size_t i=0;i<input[0].size();++i){random=1664525U*random+1013904223U;
        input[0][i]=float(.2*std::sin(6.283185307179586*123*double(i)/rate)+.05*(double(random>>8U)/16777216.-.5));
        input[1][i]=-.5F*input[0][i];}
    float* out[]={output[0].data(),output[1].data()};clock_source clock;
    rusage before{},after{};if(getrusage(RUSAGE_THREAD,&before))throw std::runtime_error("rusage failed");
    const ns epoch=read_clock(CLOCK_MONOTONIC)+2000000;unsigned sleep_interrupts=0,errors=0;
    std::uint64_t hash=1469598103934665603ULL; // Diagnostic same-binary fingerprint, not cryptographic provenance.
    for(unsigned n=0;n<total;++n){
        const ns release=release_at(epoch,n,block,rate),next=release_at(epoch,n+1,block,rate);
        if(schedule=="periodic"){
            const timespec target{time_t(release/1000000000),long(release%1000000000)};
            int error{};do {error=clock_nanosleep(CLOCK_MONOTONIC,TIMER_ABSTIME,&target,nullptr);if(error==EINTR)++sleep_interrupts;}while(error==EINTR);
            if(error)throw std::runtime_error("absolute sleep failed");
        }
        // End-to-end outer bracket includes pointer/event setup and timing calls;
        // the selected inner bracket surrounds only the declared work+observer.
        const ns start=read_clock(CLOCK_MONOTONIC);
        const float* in[]={input[0].data()+std::size_t(n)*block,input[1].data()+std::size_t(n)*block};
        int status=0;std::uint64_t integer=771;
        const auto duration=measure(clock,[&]{
            if(workload=="dsp")status=engine.process(in,out,block,n);
            else if(workload=="control")for(unsigned k=0;k<80000;++k){integer=integer*6364136223846793005ULL+1442695040888963407ULL;asm volatile("":"+r"(integer));}
            else asm volatile("":::"memory");
        },kind);
        const ns end=read_clock(CLOCK_MONOTONIC);
        auto& record=rows[n];record.time=duration;record.outer=end-start;record.period=next-release;record.status=static_cast<unsigned>(status);
        if(schedule=="periodic"){
            const auto p=classify(release,next,start,end);
            record.wake=p.wake_late;record.response=p.response;record.slack=p.slack;record.missed=p.missed;
        }
        if(status)++errors;
        if(workload=="dsp")for(auto& ch:output)for(float v:ch){
            if(!std::isfinite(v))throw std::runtime_error("nonfinite output");
            hash=(hash^std::bit_cast<std::uint32_t>(v))*1099511628211ULL;
        }
        else hash=(hash^integer)*1099511628211ULL;
        record.hash=hash;
    }
    if(getrusage(RUSAGE_THREAD,&after))throw std::runtime_error("rusage failed");
    std::cerr<<"{\"schema\":\"boiled-egg.rt-audit.v1\",\"rate\":"<<rate<<",\"block\":"<<block<<",\"shift\":"<<shift
        <<",\"count\":"<<count<<",\"warmup\":"<<warmup<<",\"requested_warmup\":"<<requested<<",\"repeat\":"<<repeat
        <<",\"workload\":"<<std::quoted(workload)<<",\"schedule\":"<<std::quoted(schedule)<<",\"bracket\":"<<std::quoted(bracket_name)
        <<",\"latency_frames\":"<<engine.latency<<",\"pinned_cpu\":"<<cpu<<",\"policy\":"<<sched_getscheduler(0)
        <<",\"sleep_interrupts\":"<<sleep_interrupts<<",\"errors\":"<<errors
        <<",\"minor_faults\":"<<(after.ru_minflt-before.ru_minflt)<<",\"major_faults\":"<<(after.ru_majflt-before.ru_majflt)
        <<",\"voluntary_switches\":"<<(after.ru_nvcsw-before.ru_nvcsw)<<",\"involuntary_switches\":"<<(after.ru_nivcsw-before.ru_nivcsw)
        <<",\"output_fingerprint\":\""<<std::hex<<hash<<std::dec<<"\"}\n";
    std::cout<<"index,cold,cpu_ns,wall_ns,outer_ns,period_ns,wake_late_ns,response_ns,slack_ns,release_miss,status,output_hash\n";
    for(unsigned n=0;n<total;++n){const auto& r=rows[n];
        std::cout<<n<<','<<(n<warmup)<<','<<r.time.cpu<<','<<r.time.wall<<','<<r.outer<<','<<r.period<<','<<r.wake<<','<<r.response<<','<<r.slack<<','<<r.missed<<','<<r.status<<','<<std::hex<<r.hash<<std::dec<<'\n';}
    return errors?3:0;
}catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}}
