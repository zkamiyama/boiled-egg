#include "transport.h"
#include "fft.hpp"
#include <algorithm>
#include <array>
#include <cmath>
#include <complex>
#include <cstddef>
#include <cstdint>
#include <limits>
#include <new>
#include <numbers>
#include <vector>

namespace {
using complex = std::complex<float>;
using FFT = boiled_egg::research::detail::fft_plan;
constexpr double pi = std::numbers::pi_v<double>;
constexpr unsigned taps = 32, phases = 512, bands = 48;
constexpr double min_cutoff = 1.0/32.0;
float wrap(double x) noexcept { return static_cast<float>(std::remainder(x,2*pi)); }
// Immutable fractional-delay/anti-alias bank, initialized before create returns.
// This prototype uses a finite 32-tap kernel, not ideal bandlimited interpolation.
struct Interpolator {
    std::vector<float> table;
    Interpolator():table(bands*phases*taps) {
        for(unsigned b=0;b<bands;++b) {
            const double cutoff = min_cutoff*std::pow(1/min_cutoff,double(b)/(bands-1));
            for(unsigned p=0;p<phases;++p) {
                double sum=0; auto* dst=table.data()+(b*phases+p)*taps;
                for(unsigned j=0;j<taps;++j) {
                    double d=double(j)-15-double(p)/phases;
                    double z=pi*d*cutoff;
                    double w=std::abs(d)<16 ? .42+.5*std::cos(pi*d/16)+.08*std::cos(2*pi*d/16):0;
                    dst[j]=float(cutoff*(std::abs(z)<1e-14?1:std::sin(z)/z)*w);sum+=dst[j];
                }
                for(unsigned j=0;j<taps;++j)dst[j]=float(dst[j]/sum);
            }
        }
    }
    unsigned band(double step) const noexcept {
        const double cutoff=std::clamp(.94/std::max(1.,step),min_cutoff,1.);
        return unsigned(std::clamp(int(std::floor(std::log(cutoff/min_cutoff)/std::log(1/min_cutoff)*(bands-1))),0,int(bands-1)));
    }
};
const Interpolator& interpolator(){static const Interpolator bank;return bank;}
struct Ramp {
    double value{},start{},target{};
    uint32_t length{},elapsed{};
    void set(double x,uint32_t n) noexcept {start=value;target=x;length=n;elapsed=0;if(!n)value=x;}
    void tick() noexcept {if(elapsed<length){++elapsed;value=elapsed==length?target:start+(target-start)*(double(elapsed)/length);}}
    void reset() noexcept {value=target;start=target;length=elapsed=0;}
};
unsigned window_size(const be_transport_config& c) {
    const unsigned base=(c.mode==BE_T_WSOLA_TRANSIENT?512U:
        c.mode==BE_T_PV_TRANSIENT?2048U:c.mode>=BE_T_WSOLA?1024U:4096U);
    return base*(c.output_rate>48000U?2U:1U);
}
}

struct be_transport {
    be_transport_config cfg;
    uint64_t frames{},clock{},synth_count{},analysis_count{},frame_clock{},pv_ready{};
    double source_error{}, resample_error{}, resample_position{}, output_pitch_value{100}, output_pitch_ratio{1};
    unsigned output_pitch_band{};
    unsigned n,hop,bins,capacity;
    std::vector<float> source,window,ola,weights,mag,prior_mag,frequency,rotation,prediction,gain,logs,pv;
    std::vector<complex> spec,old_spec,probe,work,cepstrum;
    std::vector<unsigned> owners,peaks;
    std::vector<float> previous_grain;
    FFT fft;
    std::array<Ramp,3> control{};
    double position{},anchor{-1},last_pitch{-1},last_formant{100},selected_center{};
    bool initialized{},spectrum_ready{};
    unsigned tail{},kernel_band{};
    const Interpolator& bank;

    be_transport(const be_transport_config& c,const float* data,uint64_t count)
        :cfg(c),frames(count),n(window_size(c)),hop(n/4),bins(n/2+1),capacity(4*n),
         source(count*c.channels),window(n),ola(capacity*c.channels),weights(capacity),
         mag(bins),prior_mag(bins),frequency(bins),rotation(bins),prediction(bins),gain(bins,1),logs(bins),pv(capacity*c.channels),
         spec(n*c.channels),old_spec(n*c.channels),probe(n*c.channels),work(n),cepstrum(n),owners(bins),peaks(bins),
         previous_grain(n*c.channels),fft(n),bank(interpolator()) {
        if(count)std::copy_n(data,source.size(),source.data());
        for(unsigned i=0;i<n;++i)window[i]=float(.5-.5*std::cos(2*pi*i/n));
        control[0].value=control[0].target=1;
    }
    float read(double x,unsigned ch,double step) const noexcept {
        // Reject before converting double to signed integer. No wrapping at EOF.
        if(x < -double(taps) || x>=double(frames)+taps)return 0;
        const auto center=static_cast<int64_t>(std::floor(x));
        double fraction=x-double(center);
        // Exact integer sampling at unity needs no bandwidth reduction.
        if(step==1. && fraction==0.)return center<0 || uint64_t(center)>=frames?0:source[uint64_t(center)*cfg.channels+ch];
        auto phase=std::min(unsigned(fraction*phases),phases-1);
        const float* kernel=bank.table.data()+(kernel_band*phases+phase)*taps;
        double total=0;
        for(unsigned j=0;j<taps;++j){auto at=center+int(j)-15;
            if(at>=0 && uint64_t(at)<frames)total+=double(source[uint64_t(at)*cfg.channels+ch])*kernel[j];}
        return float(total);
    }
    void analyze(double at,double step,std::vector<complex>& result) noexcept {
        for(unsigned ch=0;ch<cfg.channels;++ch){auto* x=result.data()+ch*n;
            for(unsigned j=0;j<n;++j)x[j]={read(at+(double(j)-n/2)*step,ch,step)*window[j],0};
            fft.forward(x);
        }
    }
    void find_owners() noexcept {
        unsigned count=0;float top=0;
        for(float v:mag)top=std::max(top,v);
        for(unsigned k=0;k<bins;++k)
            if(mag[k]>=top*.00177828F && (k==0 || mag[k]>=mag[k-1]) && (k+1==bins || mag[k]>mag[k+1]))peaks[count++]=k;
        if(!count)peaks[count++]=unsigned(std::max_element(mag.begin(),mag.end())-mag.begin());
        unsigned begin=0;
        for(unsigned i=0;i<count;++i){unsigned end=i+1<count?(peaks[i]+peaks[i+1])/2+1:bins;
            for(unsigned k=begin;k<end;++k)owners[k]=peaks[i];
            begin=end;}
    }
    void formants(double pitch,double shift) noexcept {
        std::fill(gain.begin(),gain.end(),1.F);
        if(!cfg.formant_policy || std::abs(pitch/std::exp2(shift/12)-1)<1e-12)return;
        for(unsigned k=0;k<bins;++k)cepstrum[k]={std::log(std::max(mag[k],1e-7F)),0};
        for(unsigned k=bins;k<n;++k)cepstrum[k]=cepstrum[n-k];
        fft.inverse(cepstrum.data());
        double f0=0,confidence=0;
        if(cfg.formant_policy==2){
            unsigned lo=std::max(2U,cfg.output_rate/1600),hi=std::min(n/2-1,cfg.output_rate/40),best=lo;
            double sum=1e-20;float peak=0;
            for(unsigned q=lo;q<=hi;++q){float v=std::max(0.F,cepstrum[q].real());sum+=v*v;
                if(v>peak){peak=v;best=q;}}
            f0=double(cfg.output_rate)/best;
            confidence=std::clamp((peak/std::sqrt(sum/(hi-lo+1))-1.4)/3.,0.,1.);
        }
        unsigned order=40*(cfg.output_rate>48000?2:1);
        for(unsigned q=1;q<n;++q){unsigned folded=std::min(q,n-q);
            if(folded>order)cepstrum[q]=0.F;
            else if(folded>order-8)cepstrum[q]*=float(.5*(1+std::cos(pi*(folded-order+8)/8)));}
        fft.forward(cepstrum.data());for(unsigned k=0;k<bins;++k)logs[k]=cepstrum[k].real();
        double warp=pitch/std::exp2(shift/12),energy=1e-20,weighted=0;
        for(unsigned k=0;k<bins;++k){double to=std::min(double(bins-1),k*warp);auto k0=unsigned(to);auto k1=std::min(k0+1,bins-1);
            double loggain=std::clamp(double(logs[k0])+(to-k0)*(logs[k1]-logs[k0])-logs[k],-15*std::log(10.)/20,15*std::log(10.)/20);
            if(cfg.formant_policy==2 && loggain>0){double w=0;
                if(f0>0 && k){double f=double(k)*cfg.output_rate/n;double distance=std::abs(f-std::max(1.,std::round(f/f0))*f0);
                    double radius=std::max(2.*cfg.output_rate/n,.46*f0);
                    if(distance<radius){double v=std::cos(.5*pi*distance/radius);w=confidence*v*v;}}
                loggain*=w;}
            gain[k]=float(std::exp(loggain));double e=double(mag[k])*mag[k]*(k && k+1<bins?2:1);
            energy+=e;weighted+=e*loggain;
        }
        double center=std::exp(-weighted/energy),corrected=1e-20;
        for(unsigned k=0;k<bins;++k){gain[k]=float(gain[k]*center);double v=mag[k]*double(gain[k]);corrected+=v*v*(k && k+1<bins?2:1);}
        double scale=std::min(1.,std::sqrt(energy/corrected));for(float& v:gain)v=float(v*scale);
    }
    void spectral_frame(double pitch,double step) noexcept {
        bool moved=position!=anchor;
        bool refresh=!spectrum_ready || moved;
        bool reset=false;
        if(refresh){
            old_spec.swap(spec);
            analyze(position,step,spec);
            // D is nonzero even while speed=0. Frequency is estimated from
            // adjacent SOURCE windows, never by dividing by source advancement.
            analyze(position-hop*step,step,probe);analysis_count+=2;
            double positive=0,previous=1e-20;
            for(unsigned k=0;k<bins;++k){double power=0;std::complex<double> difference{};
                for(unsigned ch=0;ch<cfg.channels;++ch){auto a=spec[ch*n+k],b=probe[ch*n+k];
                    power+=std::norm(a);difference+=std::complex<double>(a)*std::conj(std::complex<double>(b));}
                mag[k]=float(std::sqrt(power/cfg.channels));
                const double omega=2*pi*k/n;
                frequency[k]=float(omega+wrap(std::arg(difference)-omega*hop)/hop);
                positive+=std::max(0.F,mag[k]-prior_mag[k]);previous+=prior_mag[k];
            }
            frequency[0]=0;frequency[bins-1]=float(pi);
            reset=initialized && moved && cfg.mode==BE_T_PV_TRANSIENT && positive/previous>1.0;
            find_owners();
            // Account for changed original frame phase while preserving a common
            // rotation across channels. At freeze, difference is identically0.
            for(unsigned k=0;k<bins;++k){std::complex<double> difference{};
                for(unsigned ch=0;ch<cfg.channels;++ch)difference+=std::complex<double>(spec[ch*n+k])*std::conj(std::complex<double>(old_spec[ch*n+k]));
                prediction[k]=(!initialized || reset)?0.F:wrap(rotation[k]+hop*frequency[k]-std::arg(difference));}
            anchor=position;spectrum_ready=true;prior_mag=mag;
        } else {
            for(unsigned k=0;k<bins;++k)prediction[k]=wrap(rotation[k]+hop*frequency[k]);
        }
        if(refresh || last_formant!=control[2].value || last_pitch!=pitch){formants(pitch,control[2].value);last_formant=control[2].value;last_pitch=pitch;}
        // End bins remain real, including DC. Other bins use linked rotation.
        for(unsigned k=0;k<bins;++k)rotation[k]=prediction[cfg.mode==BE_T_PV_CLASSIC?k:owners[k]];
        rotation[0]=0;rotation[bins-1]=0;
        for(unsigned ch=0;ch<cfg.channels;++ch){
            for(unsigned k=0;k<bins;++k)work[k]=spec[ch*n+k]*std::polar(gain[k],rotation[k]);
            work[0]={work[0].real(),0};work[bins-1]={work[bins-1].real(),0};
            for(unsigned k=bins;k<n;++k)work[k]=std::conj(work[n-k]);
            fft.inverse(work.data());
            for(unsigned j=0;j<n;++j)ola[((frame_clock+j)%capacity)*cfg.channels+ch]+=work[j].real()*window[j];
        }
    }
    void time_frame(double step) noexcept {
        double selected=position;
        if(initialized){
            // Bounded WSOLA search against the prior grain's overlap. Search is
            // channel-linked. Output time advances while the source anchor stays.
            double best=-2;const int radius=int(n),stride=cfg.mode==BE_T_WSOLA_EFFICIENT?32:16;
            const unsigned sample_stride=cfg.mode==BE_T_WSOLA_EFFICIENT?32U:16U;
            const double expected=selected_center+hop*step;
            auto score=[&](double center){double cross=0,a2=1e-20,b2=1e-20;
                for(unsigned j=0;j<n-hop;j+=sample_stride)for(unsigned ch=0;ch<cfg.channels;++ch){
                    double a=previous_grain[(j+hop)*cfg.channels+ch],b=read(center+(double(j)-n/2)*step,ch,step);
                    cross+=a*b;a2+=a*a;b2+=b*b;}
                return cross/std::sqrt(a2*b2);
            };
            if(std::abs(expected-position)<=radius*step){best=score(expected);selected=expected;}
            for(int offset=-radius;offset<=radius;offset+=stride){double at=position+offset*step,s=score(at);
                if(s>best+1e-10){best=s;selected=at;}}
            const double coarse=selected;
            for(int offset=-stride+1;offset<stride;++offset){double at=coarse+offset*step;
                if(std::abs(at-position)>radius*step)continue;
                double s=score(at);if(s>best+1e-10){best=s;selected=at;}}
        }
        // Subsample correlation peak avoids pitch quantization to an integer
        // repetition period (e.g. 997Hz becoming1000Hz in a short frozen grain).
        if(initialized){
            auto local_score=[&](double center){double cross=0,a2=1e-20,b2=1e-20;
                for(unsigned j=0;j<n-hop;j+=8)for(unsigned ch=0;ch<cfg.channels;++ch){
                    double a=previous_grain[(j+hop)*cfg.channels+ch],b=read(center+(double(j)-n/2)*step,ch,step);
                    cross+=a*b;a2+=a*a;b2+=b*b;}
                return cross/std::sqrt(a2*b2);
            };
            double a=local_score(selected-step),b=local_score(selected),c=local_score(selected+step);
            double denominator=a-2*b+c;
            if(denominator < -1e-12){double offset=std::clamp(.5*(a-c)/denominator,-1.,1.);
                double refined=std::clamp(selected+offset*step,position-n*step,position+n*step);
                if(local_score(refined)>b)selected=refined;}
        }
        for(unsigned j=0;j<n;++j)for(unsigned ch=0;ch<cfg.channels;++ch){
            float sample=read(selected+(double(j)-n/2)*step,ch,step);
            previous_grain[j*cfg.channels+ch]=sample;
            ola[((frame_clock+j)%capacity)*cfg.channels+ch]+=sample*window[j]*window[j];
        }
        selected_center=selected;anchor=position;++analysis_count;
    }
    void frame() noexcept {
        double pitch=std::exp2(control[1].value/12),step=double(cfg.source_rate)/cfg.output_rate;
        kernel_band=bank.band(step);
        if(position<double(frames)){
            if(cfg.mode<=BE_T_PV_TRANSIENT)spectral_frame(pitch,step);else time_frame(step);
        }
        for(unsigned j=0;j<n;++j)weights[(frame_clock+j)%capacity]+=window[j]*window[j];
        initialized=true;++synth_count;
        for(unsigned j=0;j<hop;++j){const auto slot=(frame_clock+j)%capacity;
            const double startup=std::min(1.,double(frame_clock+j)/n);
            const float norm=weights[slot]>1e-8F?float(startup/weights[slot]):0.F;
            for(unsigned ch=0;ch<cfg.channels;++ch){auto at=slot*cfg.channels+ch;pv[at]=ola[at]*norm;ola[at]=0;}
            weights[slot]=0;
        }
        frame_clock+=hop;pv_ready=frame_clock;
    }
    void seek(double pos) noexcept {
        position=pos;clock=synth_count=analysis_count=frame_clock=pv_ready=0;resample_position=source_error=resample_error=0;anchor=-1;last_pitch=-1;last_formant=100;tail=0;
        initialized=spectrum_ready=false;
        for(auto& p:control)p.reset();
        std::fill(pv.begin(),pv.end(),0);std::fill(ola.begin(),ola.end(),0);std::fill(weights.begin(),weights.end(),0);
        std::fill(rotation.begin(),rotation.end(),0);std::fill(prior_mag.begin(),prior_mag.end(),0);
    }
    uint64_t bytes() const noexcept {
        return sizeof(*this)+sizeof(float)*(source.capacity()+window.capacity()+ola.capacity()+weights.capacity()+mag.capacity()+prior_mag.capacity()+frequency.capacity()+rotation.capacity()+prediction.capacity()+gain.capacity()+logs.capacity()+previous_grain.capacity()+pv.capacity())+
            sizeof(complex)*(spec.capacity()+old_spec.capacity()+probe.capacity()+work.capacity()+cepstrum.capacity())+sizeof(unsigned)*(owners.capacity()+peaks.capacity())+
            n*sizeof(size_t)+(n/2+n-1)*sizeof(complex); // FFT's fixed storage; shared sinc bank excluded.
    }
};

extern "C" {
be_transport_config be_transport_default_config(uint32_t rate,uint32_t channels){return {sizeof(be_transport_config),BE_TRANSPORT_VERSION,rate,rate,channels,BE_T_PV_LOCKED,0,4096};}
be_transport* be_transport_create(const be_transport_config* c,const float* data,uint64_t frames,int* result){
    auto fail=[&](int v)->be_transport*{if(result)*result=v;return nullptr;};
    if(!c || c->struct_size<sizeof(*c) || c->version!=BE_TRANSPORT_VERSION || c->source_rate<8000 || c->source_rate>192000 || c->output_rate<8000 || c->output_rate>192000 ||
        c->channels<1 || c->channels>8 || !c->max_block_frames || c->max_block_frames>8192 || c->formant_policy>2 || frames>(uint64_t(1)<<27)/c->channels || (frames&&!data))return fail(BE_T_INVALID);
    // Keep worst resampling ratio <=24: more extreme rate conversion is not
    // qualified by this interpolation bank and must not be silently accepted.
    if(c->mode>BE_T_WSOLA_EFFICIENT || (c->mode>=BE_T_WSOLA && c->formant_policy) || double(c->source_rate)/c->output_rate>6.)return fail(BE_T_UNSUPPORTED);
    for(uint64_t i=0;i<frames*c->channels;++i)if(!std::isfinite(data[i]) || std::abs(data[i])>16.F)return fail(BE_T_INVALID);
    try{auto* h=new be_transport(*c,data,frames);if(result)*result=BE_T_OK;return h;}
    catch(const std::bad_alloc&){return fail(BE_T_NO_MEMORY);}catch(...){return fail(BE_T_INTERNAL);}
}
void be_transport_destroy(be_transport* h){delete h;}
int be_transport_render(be_transport* h,float* output,uint32_t frames,const be_transport_event* events,uint32_t count){
    if(!h || frames>h->cfg.max_block_frames || (frames&&!output) || count>4096 || (count&&!events) || h->clock>std::numeric_limits<uint64_t>::max()-frames-4*h->n-32)return BE_T_INVALID;
    for(unsigned i=0;i<count;++i){const auto& e=events[i];
        if(e.offset>frames || (i&&e.offset<events[i-1].offset) || e.parameter>2 || e.reserved || !std::isfinite(e.value))return BE_T_INVALID;
        if((e.parameter==BE_T_SPEED && (e.value<0 || e.value>4)) || (e.parameter==BE_T_PITCH_SEMITONES && std::abs(e.value)>24) || (e.parameter==BE_T_FORMANT_SEMITONES && std::abs(e.value)>12))return BE_T_INVALID;
        if(e.parameter==BE_T_FORMANT_SEMITONES && !h->cfg.formant_policy && e.value!=0)return BE_T_UNSUPPORTED;
    }
    unsigned next=0;
    for(unsigned i=0;;++i){
        while(next<count && events[next].offset==i){const auto& e=events[next++];h->control[e.parameter].set(e.value,e.ramp_frames);}
        if(i==frames)break;
        for(auto& p:h->control)p.tick();
        if(h->output_pitch_value!=h->control[1].value){
            h->output_pitch_value=h->control[1].value;h->output_pitch_ratio=std::exp2(h->output_pitch_value/12);
            h->output_pitch_band=h->bank.band(h->output_pitch_ratio);
        }
        const double pitch=h->output_pitch_ratio;
        const auto center=static_cast<int64_t>(std::floor(h->resample_position));
        // At most two synthesis hops are requested per output sample; pitch<=4.
        while(h->pv_ready<=uint64_t(center+17))h->frame();
        const double frac=h->resample_position-double(center);
        const unsigned phase=std::min(unsigned(frac*phases),phases-1);
        const auto* kernel=h->bank.table.data()+(h->output_pitch_band*phases+phase)*taps;
        for(unsigned ch=0;ch<h->cfg.channels;++ch){double value=0;
            if(pitch==1. && frac==0.)value=h->pv[(uint64_t(center)%h->capacity)*h->cfg.channels+ch];
            else for(unsigned j=0;j<taps;++j){auto at=center+int(j)-15;
                if(at>=0)value+=double(h->pv[(uint64_t(at)%h->capacity)*h->cfg.channels+ch])*kernel[j];}
            output[size_t(i)*h->cfg.channels+ch]=float(value);
        }
        // Compensated summation keeps sub-ULP source steps over long holds /
        // very slow motion; speed0 must not consume a saved residual.
        double increment=pitch-h->resample_error,next_position=h->resample_position+increment;
        h->resample_error=(next_position-h->resample_position)-increment;h->resample_position=next_position;
        if(h->control[0].value>0){
            increment=h->control[0].value*double(h->cfg.source_rate)/h->cfg.output_rate-h->source_error;
            next_position=h->position+increment;h->source_error=(next_position-h->position)-increment;
            h->position=std::min(double(h->frames),next_position);
            if(h->position==double(h->frames))h->source_error=0;
        }
        if(h->position>=double(h->frames))h->tail=std::min(h->tail+1,4*h->n+32);else h->tail=0;
        ++h->clock;
    }
    return BE_T_OK;
}
int be_transport_seek(be_transport* h,double frame){if(!h || !std::isfinite(frame) || frame<0 || frame>double(h->frames))return BE_T_INVALID;h->seek(frame);return BE_T_OK;}
int be_transport_get_info(const be_transport* h,be_transport_info* out){
    if(!h || !out || out->struct_size<sizeof(*out))return BE_T_INVALID;
    *out={sizeof(*out),BE_TRANSPORT_VERSION,uint32_t(h->cfg.mode<=BE_T_PV_TRANSIENT?BE_T_SPECTRAL_FREEZE|BE_T_FORMANTS:BE_T_TIME_DOMAIN_FREEZE),uint32_t(h->tail==4*h->n+32),
        h->clock,h->frames,h->synth_count,h->analysis_count,h->position,h->anchor,h->control[0].value,h->control[1].value,h->control[2].value,h->n,h->hop,h->bytes()};return BE_T_OK;
}
}
