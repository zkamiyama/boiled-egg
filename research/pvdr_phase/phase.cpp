#include "phase.h"
#include <algorithm>
#include <cmath>
#include <complex>
#include <cstdint>
#include <limits>
#include <new>
#include <queue>
#include <vector>
namespace {
constexpr double pi=3.1415926535897932384626433832795,tau=2*pi;
struct Error {int code;};
void need(bool x,int code=2){if(!x)throw Error{code};}
double wrap(double x){return x-tau*std::floor(x/tau+.5);}
uint64_t mix(uint64_t x){x+=0x9e3779b97f4a7c15ULL;x=(x^(x>>30))*0xbf58476d1ce4e5b9ULL;x=(x^(x>>27))*0x94d049bb133111ebULL;return x^(x>>31);}
double seeded(uint64_t seed,uint64_t j,uint64_t k){return tau*static_cast<double>(mix(seed^(j<<32)^k)>>11)*0x1p-53-pi;}
struct Node {double magnitude;uint32_t bin;bool current;};
struct Less {
    bool operator()(const Node& x,const Node& y)const {
        if(x.magnitude!=y.magnitude)return x.magnitude<y.magnitude;
        if(x.current!=y.current)return x.current; // previous wins ties
        return x.bin>y.bin;
    }
};
}
extern "C" int be_phase_process(const be_phase_config* c,const int64_t* a,uint64_t ac,
 const float* input,uint64_t cn,float* output,uint64_t capacity,int32_t* predecessors,
 double* out_dt,double* out_df,uint64_t diagnostic_capacity,be_phase_info* info){
 try {
    need(c&&a&&input&&output&&predecessors&&out_dt&&out_df&&info);
    need(c->struct_size==sizeof(*c)&&c->method<=1);
    const uint32_t m=c->fft_size,n=c->frame_count,kcount=m/2+1;
    need(m>=16&&m<=16384&&!(m&(m-1))&&n>=2&&n<=4096);
    const uint64_t total=static_cast<uint64_t>(n)*m,q=static_cast<uint64_t>(n)*kcount;
    need(total<=8388608&&ac==n&&cn==total&&capacity>=total&&diagnostic_capacity>=q);
    need(std::isfinite(c->stretch)&&c->stretch>=1&&c->stretch<=4);
    need(std::isfinite(c->relative_tolerance)&&c->relative_tolerance>0&&c->relative_tolerance<1);
    const uint64_t memory=total*8+q*44+static_cast<uint64_t>(kcount)*128+65536;
    need(c->memory_limit_bytes>=memory,3);
    need(a[0]==0);
    for(uint32_t j=0;j<n;++j)need(a[j]>=0&&a[j]<288000&&(!j||a[j]>a[j-1]));
    for(uint64_t i=0;i<2*total;++i)need(std::isfinite(input[i]));
    std::vector<double> mag(q),phase(q),dt(q),df(q),sphase(q);
    std::vector<int32_t> pred(q,-3);
    std::vector<float> result(2*total);
    be_phase_info summary{};summary.workspace_estimate_bytes=memory;
    auto at=[&](uint32_t j,uint32_t k){const auto i=2*(static_cast<uint64_t>(j)*m+k);return std::complex<double>(input[i],input[i+1]);};
    for(uint32_t j=0;j<n;++j){
        double peak=0;
        for(uint32_t k=0;k<m;++k)peak=std::max(peak,std::abs(at(j,k)));
        const double tolerance=3e-6*std::max(1.,peak);
        need(std::abs(at(j,0).imag())<=tolerance&&std::abs(at(j,m/2).imag())<=tolerance);
        for(uint32_t k=1;k<m/2;++k)need(std::abs(at(j,k)-std::conj(at(j,m-k)))<=tolerance);
        for(uint32_t k=0;k<kcount;++k){
            const auto i=static_cast<uint64_t>(j)*kcount+k;
            const auto z=at(j,k);mag[i]=std::abs(z);phase[i]=std::arg(z);
        }
    }
    for(uint32_t j=0;j<n;++j)for(uint32_t k=0;k<kcount;++k){
        const auto i=static_cast<uint64_t>(j)*kcount+k;const double omega=tau*k/m;
        double back=0,front=0;
        if(j){const double hop=static_cast<double>(a[j]-a[j-1]);back=wrap(phase[i]-phase[i-kcount]-omega*hop)/hop+omega;}
        if(j+1<n){const double hop=static_cast<double>(a[j+1]-a[j]);front=wrap(phase[i+kcount]-phase[i]-omega*hop)/hop+omega;}
        dt[i]=j==0?front:(j+1==n?back:(back+front)/2);
        const double fb=k?wrap(phase[i]-phase[i-1]):0;
        const double ff=k+1<kcount?wrap(phase[i+1]-phase[i]):0;
        df[i]=k==0?ff:(k+1==kcount?fb:(fb+ff)/2);
    }
    for(uint32_t k=0;k<kcount;++k)sphase[k]=phase[k];
    for(uint32_t j=1;j<n;++j){
        const auto off=static_cast<uint64_t>(j)*kcount,old=off-kcount;
        const double hop=static_cast<double>(std::llround(c->stretch*static_cast<double>(a[j]))-std::llround(c->stretch*static_cast<double>(a[j-1])));
        if(c->method==0){
            const double ahop=static_cast<double>(a[j]-a[j-1]);
            for(uint32_t k=0;k<kcount;++k){
                const double omega=tau*k/m;
                const double derivative=wrap(phase[off+k]-phase[old+k]-omega*ahop)/ahop+omega;
                sphase[off+k]=wrap(sphase[old+k]+hop*derivative);pred[off+k]=-1;++summary.temporal_edges;
            }
        }else{
            double peak=0;for(uint32_t k=0;k<kcount;++k)peak=std::max({peak,mag[old+k],mag[off+k]});
            const double threshold=c->relative_tolerance*peak;
            std::vector<bool> todo(kcount,false);uint32_t remaining=0;
            std::priority_queue<Node,std::vector<Node>,Less> heap;
            for(uint32_t k=0;k<kcount;++k){
                if(mag[off+k]>threshold){todo[k]=true;++remaining;heap.push({mag[old+k],k,false});}
                else{sphase[off+k]=seeded(c->seed,j,k);pred[off+k]=-2;++summary.low_bins;}
            }
            while(remaining){
                need(!heap.empty(),4);const auto h=heap.top();heap.pop();const auto k=h.bin;
                if(!h.current){
                    if(!todo[k])continue;
                    sphase[off+k]=wrap(sphase[old+k]+hop*(dt[old+k]+dt[off+k])/2);
                    pred[off+k]=-1;todo[k]=false;--remaining;++summary.temporal_edges;
                    heap.push({mag[off+k],k,true});
                }else{
                    for(int direction:{1,-1}){
                        const int neighbour=static_cast<int>(k)+direction;
                        if(neighbour<0||neighbour>=static_cast<int>(kcount))continue;
                        const auto v=static_cast<uint32_t>(neighbour);if(!todo[v])continue;
                        sphase[off+v]=wrap(sphase[off+k]+direction*c->stretch*(df[off+k]+df[off+v])/2);
                        pred[off+v]=static_cast<int32_t>(k);todo[v]=false;--remaining;++summary.frequency_edges;
                        heap.push({mag[off+v],v,true});
                    }
                }
            }
        }
    }
    auto put=[&](uint32_t j,uint32_t k,std::complex<double> z){const auto i=2*(static_cast<uint64_t>(j)*m+k);result[i]=static_cast<float>(z.real());result[i+1]=static_cast<float>(z.imag());};
    for(uint32_t j=0;j<n;++j)for(uint32_t k=0;k<kcount;++k){
        const auto i=static_cast<uint64_t>(j)*kcount+k;
        std::complex<double> z=std::polar(mag[i],sphase[i]);
        if(k==0||k==m/2){z={std::copysign(mag[i],at(j,k).real()),0};summary.maximum_hermitian_correction=std::max(summary.maximum_hermitian_correction,std::abs(at(j,k)-z));}
        put(j,k,z);if(k>0&&k<m/2)put(j,m-k,std::conj(z));
        const auto pos=2*(static_cast<uint64_t>(j)*m+k);
        const double actual=std::hypot(static_cast<double>(result[pos]),static_cast<double>(result[pos+1]));
        summary.maximum_magnitude_error=std::max(summary.maximum_magnitude_error,std::abs(actual-mag[i])/std::max(1.,mag[i]));
    }
    for(const auto v:result)need(std::isfinite(v),4);
    std::copy(result.begin(),result.end(),output);std::copy(pred.begin(),pred.end(),predecessors);
    std::copy(dt.begin(),dt.end(),out_dt);std::copy(df.begin(),df.end(),out_df);*info=summary;return 0;
 }catch(const Error& e){return e.code;}catch(const std::bad_alloc&){return 3;}catch(...){return 2;}
}
