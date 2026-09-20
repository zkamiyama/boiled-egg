#include "anchor.h"
#include <algorithm>
#include <cmath>
#include <cstddef>
#include <cstdint>
#include <limits>
#include <new>
#include <stdexcept>
#include <vector>

namespace {
constexpr double pi=3.1415926535897932384626433832795;
struct Error { int code; };
void require(bool ok,int code=2) {if(!ok) throw Error{code};}
double at(const float* x,int64_t n,int64_t i) {return i>=0 && i<n ? x[i] : 0.;}
struct Mark { int64_t input, output; };
bool permitted(int64_t src,int64_t dst,const std::vector<Mark>& marks,int64_t guard) {
    for(const auto& a:marks)
        if(std::abs(src-a.input)<=guard || std::abs(dst-a.output)<=guard)
            if(src-dst!=a.input-a.output) return false;
    return true;
}
double score(const float* x,int64_t n,int64_t reference,int64_t candidate,int64_t count,int64_t stride) {
    double dot=0,aa=1e-18,bb=1e-18;
    for(int64_t i=0;i<count;i+=stride) {
        const auto a=at(x,n,reference+i),b=at(x,n,candidate+i);
        dot+=a*b;aa+=a*a;bb+=b*b;
    }
    return dot/std::sqrt(aa*bb);
}
std::vector<float> resample(const std::vector<float>& x,int64_t frames,double pitch) {
    constexpr int phases=1024,taps=64,half=32;
    std::vector<double> table(static_cast<size_t>(phases*taps));
    std::vector<bool> ready(phases,false);
    const double cutoff=.94*std::min(1.,1./pitch);
    std::vector<float> result(static_cast<size_t>(frames));
    for(int64_t i=0;i<frames;++i) {
        const double pos=static_cast<double>(i)*pitch;
        const auto center=static_cast<int64_t>(std::floor(pos));
        const int phase=std::clamp(static_cast<int>((pos-static_cast<double>(center))*phases),0,phases-1);
        double* kernel=table.data()+phase*taps;
        if(!ready[static_cast<size_t>(phase)]) {
            const double frac=static_cast<double>(phase)/phases; double total=0;
            for(int j=0;j<taps;++j) {
                const double d=static_cast<double>(j-half+1)-frac;
                const double v=cutoff*d;
                const double sinc=std::abs(v)<1e-12 ? 1. : std::sin(pi*v)/(pi*v);
                const double w=std::abs(d)>=half ? 0. : .42+.5*std::cos(pi*d/half)+.08*std::cos(2*pi*d/half);
                kernel[j]=cutoff*sinc*w;total+=kernel[j];
            }
            for(int j=0;j<taps;++j) kernel[j]/=total;
            ready[static_cast<size_t>(phase)]=true;
        }
        double v=0;
        for(int j=0;j<taps;++j) v+=kernel[j]*at(x.data(),static_cast<int64_t>(x.size()),center+j-half+1);
        result[static_cast<size_t>(i)]=static_cast<float>(v);
    }
    return result;
}
}
extern "C" int be_anchor_render(const float* x,uint64_t frames,const int64_t* anchors,uint32_t count,
                                const be_anchor_config* cp,float* output,be_anchor_grain* trace,
                                uint64_t capacity,be_anchor_info* info) {
    try {
        require(x && output && cp && info && trace);
        require(cp->struct_size==sizeof(be_anchor_config) && cp->channels==1 && cp->mode<=2);
        require(cp->sample_rate==48000 || cp->sample_rate==96000);
        require(frames>0 && frames<=static_cast<uint64_t>(cp->sample_rate)*3 && count<=16);
        require(!count || anchors);
        require(std::isfinite(cp->pitch_ratio) && cp->pitch_ratio>=.5 && cp->pitch_ratio<=2.);
        require(cp->mode!=0 || count==0); // Never silently ignore supplied landmarks.
        const double pitch=cp->pitch_ratio;
        const auto n=static_cast<int64_t>(frames);
        const int64_t w=cp->sample_rate==48000 ? 4096 : 8192, half=w/2,hop=w/4;
        const int64_t radius=cp->sample_rate/50,guard=static_cast<int64_t>(std::llround(.006*cp->sample_rate));
        std::vector<Mark> marks;marks.reserve(count);
        for(uint32_t j=0;j<count;++j) {
            require(anchors[j]>guard && anchors[j]<n-guard);
            const auto dst=static_cast<int64_t>(std::llround(static_cast<double>(anchors[j])*pitch));
            if(j) require(anchors[j]-marks.back().input>2*guard && dst-marks.back().output>2*guard);
            marks.push_back({anchors[j],dst});
        }
        double energy=0;
        for(uint64_t i=0;i<frames;++i) {require(std::isfinite(x[i]) && std::abs(x[i])<=1);energy+=static_cast<double>(x[i])*x[i];}
        require(energy/static_cast<double>(frames)>1e-16);
        const auto m=static_cast<int64_t>(std::ceil(static_cast<double>(n-1)*pitch))+65;
        const auto estimate=static_cast<uint64_t>(m)*20+frames*4+static_cast<uint64_t>(w)*8+1024*64*8+65536;
        require(cp->memory_limit_bytes>=estimate,3);
        std::vector<int64_t> centers;
        for(int64_t center=0;center<m+half;center+=hop) centers.push_back(center);
        for(const auto& a:marks) centers.push_back(a.output);
        std::sort(centers.begin(),centers.end());
        centers.erase(std::unique(centers.begin(),centers.end()),centers.end());
        require(capacity>=centers.size());
        if(pitch==1.) {
            std::copy(x,x+frames,output);*info={frames,0,0,estimate,1,1};return 0;
        }
        std::vector<double> sum(static_cast<size_t>(m),0),weight(static_cast<size_t>(m),0),window(static_cast<size_t>(w));
        for(int64_t i=0;i<w;++i) {const double v=std::sin(pi*static_cast<double>(i)/static_cast<double>(w-1));window[static_cast<size_t>(i)]=v*v;}
        std::vector<be_anchor_grain> grains;grains.reserve(centers.size());
        int64_t prev_center=0,prev_src=0;uint64_t masked=0;
        for(const auto center:centers) {
            const auto expected=static_cast<int64_t>(std::llround(static_cast<double>(center)/pitch));
            int64_t selected=expected; int32_t owner=-1;double best=-2;
            int64_t nearest=std::numeric_limits<int64_t>::max();
            for(size_t j=0;j<marks.size();++j) {
                const auto d=std::abs(center-marks[j].output);
                if(d<=half+guard && d<nearest) {nearest=d;owner=static_cast<int32_t>(j);}
            }
            if(owner>=0) selected=marks[static_cast<size_t>(owner)].input+center-marks[static_cast<size_t>(owner)].output;
            else if(!grains.empty()) {
                const auto delta=center-prev_center;
                const auto overlap=std::max<int64_t>(1,w-delta);
                const auto reference=prev_src+delta-half;
                const int64_t coarse=cp->sample_rate==48000 ? 4 : 8,stride=cp->sample_rate==48000 ? 2 : 4;
                const int64_t lo=expected-radius,hi=expected+radius;
                for(int64_t c=lo;c<=hi;c+=coarse) {
                    const auto v=score(x,n,reference,c-half,overlap,stride);
                    if(v>best) {best=v;selected=c;}
                }
                const auto a=std::max(lo,selected-coarse+1),b=std::min(hi,selected+coarse-1);
                for(int64_t c=a;c<=b;++c) {
                    const auto v=score(x,n,reference,c-half,overlap,stride);
                    if(v>best) {best=v;selected=c;}
                }
            }
            if(best==-2) best=0;
            uint32_t masked_grain=0;
            for(int64_t i=0;i<w;++i) {
                const auto dst=center-half+i,src=selected-half+i;
                if(dst<0 || dst>=m) continue;
                if(cp->mode==2 && !permitted(src,dst,marks,guard)) {++masked_grain;continue;}
                const auto k=static_cast<size_t>(dst);const double v=window[static_cast<size_t>(i)];
                sum[k]+=v*at(x,n,src);weight[k]+=v;
            }
            masked+=masked_grain;grains.push_back({center,selected,expected,owner,masked_grain,best});
            prev_src=selected;prev_center=center;
        }
        double minimum=std::numeric_limits<double>::infinity(),maximum=0;
        std::vector<float> intermediate(static_cast<size_t>(m));
        for(size_t i=0;i<intermediate.size();++i) {
            require(weight[i]>1e-10,4);minimum=std::min(minimum,weight[i]);maximum=std::max(maximum,weight[i]);
            intermediate[i]=static_cast<float>(sum[i]/weight[i]);
        }
        auto y=resample(intermediate,n,pitch);double out_energy=0;
        for(const auto v:y) {require(std::isfinite(v),5);out_energy+=static_cast<double>(v)*v;}
        require(out_energy>1e-16*static_cast<double>(frames),5);
        std::copy(y.begin(),y.end(),output);std::copy(grains.begin(),grains.end(),trace);
        *info={frames,static_cast<uint64_t>(grains.size()),masked,estimate,minimum,maximum};return 0;
    } catch(const Error& e) {return e.code;} catch(const std::bad_alloc&) {return 3;} catch(...) {return 2;}
}
