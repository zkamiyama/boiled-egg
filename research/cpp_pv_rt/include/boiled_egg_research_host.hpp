#ifndef BOILED_EGG_RESEARCH_HOST_HPP
#define BOILED_EGG_RESEARCH_HOST_HPP
#include "boiled_egg_research_host.h"
#include <stdexcept>
#include <utility>
namespace boiled_egg::research {
// Construction may throw; the realtime entry points return C status codes.
class fixed_latency_engine {
public:
    explicit fixed_latency_engine(const boiledegg_research_host_config& c) {
        boiledegg_research_pv_rt_result status{};h_=boiledegg_research_host_create(&c,&status);
        if(!h_)throw std::runtime_error(boiledegg_research_pv_rt_result_string(status));
    }
    ~fixed_latency_engine(){boiledegg_research_host_destroy(h_);}
    fixed_latency_engine(const fixed_latency_engine&)=delete;
    fixed_latency_engine& operator=(const fixed_latency_engine&)=delete;
    fixed_latency_engine(fixed_latency_engine&& x)noexcept:h_(std::exchange(x.h_,nullptr)){}
    fixed_latency_engine& operator=(fixed_latency_engine&& x)noexcept{
        if(this!=&x){boiledegg_research_host_destroy(h_);h_=std::exchange(x.h_,nullptr);}return *this;
    }
    boiledegg_research_pv_rt_result process(const float* const* in,float* const* out,uint32_t n,
        const boiledegg_research_host_event* events=nullptr,uint32_t count=0)noexcept{
        return boiledegg_research_host_process(h_,in,out,n,events,count);
    }
    boiledegg_research_pv_rt_result request_formant(float ratio)noexcept{return boiledegg_research_host_request_formant(h_,ratio);}
    boiledegg_research_pv_rt_result reset()noexcept{return boiledegg_research_host_reset(h_);}
    [[nodiscard]] float target_formant()const noexcept{return boiledegg_research_host_get_target(h_);}
    [[nodiscard]] uint32_t latency_frames()const noexcept{return boiledegg_research_host_latency_frames(h_);}
    [[nodiscard]] boiledegg_research_host_handle* native_handle()const noexcept{return h_;}
private:
    boiledegg_research_host_handle* h_{};
};
}
#endif
