#include "offline.hpp"
#include "fft.hpp"
#include <algorithm>
#include <cmath>
#include <complex>
#include <limits>
#include <numbers>
#include <stdexcept>
#include <utility>

namespace boiled_egg::offline_research {
namespace {
using Complex = std::complex<float>;
constexpr double pi = std::numbers::pi_v<double>;
void require(bool value, const char* reason) { if (!value) throw std::invalid_argument(reason); }
double wrap(double value) { return std::remainder(value, 2.0 * pi); }
std::size_t rounded(double value) {
    require(std::isfinite(value) && value >= 1.0 && value <= 12000000.0, "invalid/excessive output length");
    return static_cast<std::size_t>(std::floor(value + 0.5));
}
std::size_t frame_count(std::size_t length, std::size_t hop) { return (length + hop - 1) / hop + 1; }
struct Transform {
    std::size_t n, h, bins;
    research::detail::fft_plan fft;
    std::vector<float> window;
    std::vector<Complex> buffer;
    Transform(std::size_t size, std::size_t hop) : n(size), h(hop), bins(n/2+1), fft(n), window(n), buffer(n) {
        for (std::size_t i=0; i<n; ++i)
            window[i]=static_cast<float>(std::sqrt(std::max(0.0, 0.5-0.5*std::cos(2*pi*static_cast<double>(i)/static_cast<double>(n)))));
    }
    std::vector<Complex> analysis(std::span<const float> x, std::size_t count) {
        std::vector<Complex> out(count*bins);
        for (std::size_t m=0; m<count; ++m) {
            const auto start=static_cast<std::int64_t>(m*h)-static_cast<std::int64_t>(n/2);
            for (std::size_t i=0; i<n; ++i) {
                const auto pos=start+static_cast<std::int64_t>(i);
                buffer[i]=(pos>=0 && pos<static_cast<std::int64_t>(x.size())) ? x[static_cast<std::size_t>(pos)]*window[i] : 0.f;
            }
            fft.forward(buffer.data());
            for (std::size_t k=0; k<bins; ++k) {
                require(std::isfinite(buffer[k].real()) && std::isfinite(buffer[k].imag()), "nonfinite spectrum");
                out[m*bins+k]=buffer[k];
            }
        }
        return out;
    }
    std::vector<float> synthesis(std::span<const Complex> z, std::size_t length) {
        std::vector<double> sum(length), weight(length);
        const auto count=z.size()/bins;
        for (std::size_t m=0; m<count; ++m) {
            for (std::size_t k=0; k<bins; ++k) buffer[k]=z[m*bins+k];
            // Real-valued waveform constraint includes real DC and Nyquist.
            buffer[0]=Complex(buffer[0].real(),0.f); buffer[n/2]=Complex(buffer[n/2].real(),0.f);
            for (std::size_t k=1; k<n/2; ++k) buffer[n-k]=std::conj(buffer[k]);
            fft.inverse(buffer.data());
            const auto start=static_cast<std::int64_t>(m*h)-static_cast<std::int64_t>(n/2);
            for (std::size_t i=0; i<n; ++i) {
                const auto pos=start+static_cast<std::int64_t>(i);
                if (pos<0 || pos>=static_cast<std::int64_t>(length)) continue;
                const auto j=static_cast<std::size_t>(pos);
                const double w=window[i]; sum[j]+=static_cast<double>(buffer[i].real())*w; weight[j]+=w*w;
            }
        }
        std::vector<float> out(length);
        for (std::size_t i=0; i<length; ++i) {
            require(weight[i]>1e-8, "uncovered synthesis sample");
            out[i]=static_cast<float>(sum[i]/weight[i]);
            require(std::isfinite(out[i]), "nonfinite synthesis");
        }
        return out;
    }
};
double residual(std::span<const Complex> z, std::span<const float> mag, std::size_t bins) {
    double error=0, total=0;
    for (std::size_t i=0; i<z.size(); ++i) {
        const auto k=i%bins;
        const double factor=(k==0 || k==bins-1)?1.0:2.0;
        const double target=mag[i], delta=static_cast<double>(std::abs(z[i]))-target;
        error+=factor*delta*delta; total+=factor*target*target;
    }
    require(total>0 && std::isfinite(error) && std::isfinite(total), "invalid magnitude objective");
    return std::sqrt(error/total);
}
std::vector<float> resample(std::span<const float> x, std::size_t wanted, double step) {
    if (step==1.0) { require(x.size()==wanted,"identity resampler length"); return {x.begin(),x.end()}; }
    // Explicit independent adaptation: centered 65-position Blackman-windowed
    // sinc, cutoff .95*min(1,1/step). Zero outside finite input. No fitted delay.
    constexpr int radius=32;
    const double cutoff=.95*std::min(1.0,1.0/step);
    std::vector<float> y(wanted);
    for (std::size_t i=0; i<wanted; ++i) {
        const double position=static_cast<double>(i)*step;
        const auto center=static_cast<std::int64_t>(std::floor(position));
        double value=0, norm=0;
        for (int j=-radius; j<=radius; ++j) {
            const auto index=center+j; const double d=static_cast<double>(index)-position;
            if (std::abs(d)>radius) continue;
            const double a=pi*d*cutoff;
            const double sinc=std::abs(a)<1e-12 ? 1.0 : std::sin(a)/a;
            const double win=.42+.5*std::cos(pi*d/radius)+.08*std::cos(2*pi*d/radius);
            const double coefficient=cutoff*sinc*win;
            norm+=coefficient;
            if (index>=0 && index<static_cast<std::int64_t>(x.size())) value+=coefficient*x[static_cast<std::size_t>(index)];
        }
        require(std::abs(norm)>1e-8,"resampler normalization");
        y[i]=static_cast<float>(value/norm); require(std::isfinite(y[i]),"nonfinite resampling");
    }
    return y;
}
}
Result render(std::span<const float> input, const Config& c) {
    require(c.sample_rate==48000 || c.sample_rate==96000,"offline profile requires 48/96kHz mono");
    require(!input.empty() && input.size()<=static_cast<std::size_t>(c.sample_rate)*30,"input must be nonempty and at most30s");
    require(std::isfinite(c.time_ratio) && c.time_ratio>=.5 && c.time_ratio<=2,"time ratio must be .5..2; no freeze");
    require(std::isfinite(c.pitch_ratio) && c.pitch_ratio>=.5 && c.pitch_ratio<=2,"pitch ratio must be .5..2");
    require(c.iterations==0 || c.iterations==8 || c.iterations==32,"iterations must be explicitly0,8,32");
    double energy=0;
    for (float x:input) { require(std::isfinite(x),"nonfinite input"); energy+=static_cast<double>(x)*x; }
    require(energy/static_cast<double>(input.size())>1e-16,"silent/near-silent input");
    const std::size_t scale=c.sample_rate/48000, n=4096*scale, h=256*scale, bins=n/2+1;
    const double stretch=c.time_ratio*c.pitch_ratio;
    const auto intermediate=rounded(static_cast<double>(input.size())*stretch);
    const auto wanted=rounded(static_cast<double>(input.size())*c.time_ratio);
    const auto source_count=frame_count(input.size(),h)+1, out_count=frame_count(intermediate,h);
    // Conservative bound for simultaneously owned vectors and FFT tables;
    // excludes allocator/process/shared-library overhead, not a process-RSS cap.
    const std::size_t estimated=source_count*bins*sizeof(Complex)+out_count*bins*(2*sizeof(Complex)+sizeof(float))
        +(input.size()+wanted+4*intermediate)*sizeof(float)+2*intermediate*sizeof(double)+n*128+4096;
    require(estimated<=c.memory_limit_bytes,"estimated work memory exceeds limit");
    Transform stft(n,h);
    auto source=stft.analysis(input,source_count);
    std::vector<float> magnitude(out_count*bins);
    std::vector<Complex> spectrum(out_count*bins);
    std::vector<double> phase(bins);
    for (std::size_t k=0; k<bins; ++k) phase[k]=std::arg(source[k]);
    for (std::size_t m=0; m<out_count; ++m) {
        const double t=static_cast<double>(m)/stretch;
        const auto a=std::min(static_cast<std::size_t>(std::floor(t)),source_count-2);
        const double alpha=std::clamp(t-static_cast<double>(a),0.0,1.0);
        for (std::size_t k=0; k<bins; ++k) {
            const auto first=source[a*bins+k], next=source[(a+1)*bins+k];
            const auto i=m*bins+k;
            magnitude[i]=static_cast<float>((1-alpha)*std::abs(first)+alpha*std::abs(next));
            spectrum[i]=std::polar(magnitude[i],static_cast<float>(phase[k]));
            if (k==0 || k==bins-1) spectrum[i]=Complex(std::copysign(magnitude[i],spectrum[i].real()),0.f);
            const double advance=2*pi*static_cast<double>(k)*static_cast<double>(h)/static_cast<double>(n);
            phase[k]=wrap(phase[k]+advance+wrap(static_cast<double>(std::arg(next))-std::arg(first)-advance));
        }
    }
    source.clear(); source.shrink_to_fit();
    Result result; result.estimated_work_bytes=estimated; result.fft_size=n; result.hop=h; result.intermediate_frames=intermediate;
    for (unsigned iteration=0; ; ++iteration) {
        auto y=stft.synthesis(spectrum,intermediate);
        auto projected=stft.analysis(y,out_count);
        result.magnitude_residual.push_back(residual(projected,magnitude,bins));
        if (iteration==c.iterations) { result.audio=resample(y,wanted,c.pitch_ratio); break; }
        for (std::size_t i=0; i<spectrum.size(); ++i) {
            const float absolute=std::abs(projected[i]);
            // Preserve previous phase at zero; do not invent a random phase.
            if (absolute>0) spectrum[i]=projected[i]*(magnitude[i]/absolute);
        }
    }
    double output_energy=0;
    for (float x:result.audio) { require(std::isfinite(x),"nonfinite output"); output_energy+=static_cast<double>(x)*x; }
    require(output_energy/static_cast<double>(result.audio.size())>1e-16,"silent output");
    return result;
}
}
