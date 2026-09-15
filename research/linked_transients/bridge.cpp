#include "event_fusion.hpp"
#include <new>
#include <cstdint>
using fusion=boiled_egg::research::event_fusion;
extern "C" {
void* linked_events_create(std::uint32_t capacity) noexcept {
    if(capacity>1000000)return nullptr;
    try{return new fusion(capacity);}catch(...){return nullptr;}
}
void linked_events_destroy(void* p) noexcept {delete static_cast<fusion*>(p);}
std::int64_t linked_events_process(void* p,const double* t,const double* s,std::uint32_t count,
    double tolerance,double* out,std::uint32_t capacity) noexcept {
    if(!p)return -1;
    auto n=static_cast<fusion*>(p)->process(t,s,count,tolerance,out,capacity);
    return n==fusion::invalid?-1:static_cast<std::int64_t>(n);
}
}
