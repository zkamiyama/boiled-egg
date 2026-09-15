#ifndef BOILED_EGG_RESEARCH_EVENT_FUSION_HPP
#define BOILED_EGG_RESEARCH_EVENT_FUSION_HPP
#include <algorithm>
#include <cmath>
#include <cstddef>
#include <limits>
#include <vector>
namespace boiled_egg::research {
// Offline detector candidate fusion. The kernel itself allocates only at construction.
// A cluster spans <= tolerance from its FIRST candidate, not a transitive chain.
class event_fusion {
    struct event { double time, strength; };
    std::vector<event> work_;
public:
    explicit event_fusion(std::size_t capacity):work_(capacity) {}
    static constexpr std::size_t invalid=std::numeric_limits<std::size_t>::max();
    std::size_t process(const double* time,const double* strength,std::size_t count,
                        double tolerance,double* output,std::size_t capacity) noexcept {
        if(count>work_.size() || capacity<count || !std::isfinite(tolerance) || tolerance<0 ||
           (count && (!time || !strength || !output)))return invalid;
        for(std::size_t i=0;i<count;++i)
            if(!std::isfinite(time[i]) || time[i]<0 || !std::isfinite(strength[i]) || strength[i]<0)
                return invalid;
        for(std::size_t i=0;i<count;++i)work_[i]={time[i],strength[i]};
        std::sort(work_.begin(),work_.begin()+static_cast<std::ptrdiff_t>(count),
            [](const event& a,const event& b){return a.time<b.time || (a.time==b.time && a.strength>b.strength);});
        std::size_t written=0;
        for(std::size_t i=0;i<count;){
            auto best=work_[i];std::size_t j=i+1;
            while(j<count && work_[j].time-work_[i].time<=tolerance){
                if(work_[j].strength>best.strength)best=work_[j];
                ++j;
            }
            output[written++]=best.time;i=j;
        }
        return written;
    }
};
}
#endif
