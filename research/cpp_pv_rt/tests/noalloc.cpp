#include "boiled_egg_pv_rt.h"
#include <atomic>
#include <cmath>
#include <cstdlib>
#include <new>
#include <vector>
static std::atomic<bool> count_enabled{false};static std::atomic<std::uint64_t> allocations{0};
void* operator new(std::size_t n){if(count_enabled.load(std::memory_order_relaxed))allocations.fetch_add(1,std::memory_order_relaxed);if(void*p=std::malloc(n))return p;throw std::bad_alloc();}
void operator delete(void*p)noexcept{std::free(p);}void operator delete(void*p,std::size_t)noexcept{std::free(p);}
void* operator new[](std::size_t n){return ::operator new(n);}void operator delete[](void*p)noexcept{::operator delete(p);}void operator delete[](void*p,std::size_t)noexcept{::operator delete(p);}
int main(){constexpr std::uint32_t block=128;auto c=boiledegg_research_pv_rt_default_config(48000,2,block);c.initial_time_ratio=1.0F;c.initial_pitch_ratio=1.35F;c.formant_mode=BOILEDEGG_RESEARCH_PV_RT_FORMANT_HARMONIC;boiledegg_research_pv_rt_result result{};auto*h=boiledegg_research_pv_rt_create(&c,&result);if(!h)return 1;std::vector<float>a(block),b(block),oa(block*8U),ob(block*8U);const float*in[2]={a.data(),b.data()};float*out[2]={oa.data(),ob.data()};for(std::uint32_t i=0;i<block;++i){a[i]=std::sin(0.03F*i);b[i]=std::sin(0.031F*i);}for(int warm=0;warm<32;++warm){if(boiledegg_research_pv_rt_push(h,in,block)!=BOILEDEGG_RESEARCH_PV_RT_OK)return 2;while(boiledegg_research_pv_rt_available(h))boiledegg_research_pv_rt_pull(h,out,static_cast<std::uint32_t>(oa.size()));}allocations.store(0);count_enabled.store(true);for(int n=0;n<128;++n){if(n%17==0&&boiledegg_research_pv_rt_set_time_ratio(h,0.75F+0.01F*(n%50))!=BOILEDEGG_RESEARCH_PV_RT_OK)return 3;if(n%23==0&&boiledegg_research_pv_rt_set_pitch_ratio(h,0.8F+0.02F*(n%30))!=BOILEDEGG_RESEARCH_PV_RT_OK)return 6;if(boiledegg_research_pv_rt_push(h,in,block)!=BOILEDEGG_RESEARCH_PV_RT_OK)return 4;while(boiledegg_research_pv_rt_available(h))boiledegg_research_pv_rt_pull(h,out,static_cast<std::uint32_t>(oa.size()));}count_enabled.store(false);const auto count=allocations.load();boiledegg_research_pv_rt_destroy(h);return count==0?0:5;}
