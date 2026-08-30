#include "boiled_egg_pv_rt.h"
#include "fft.hpp"

#include <algorithm>
#include <cmath>
#include <complex>
#include <cstddef>
#include <cstdint>
#include <limits>
#include <new>
#include <numbers>
#include <vector>

namespace boiled_egg::research::detail {
namespace {
constexpr float k_min_ratio = 0.25F;
constexpr float k_max_ratio = 4.0F;
constexpr float k_epsilon = 1.0e-12F;

bool finite_ratio(float value) noexcept { return std::isfinite(value) && value >= k_min_ratio && value <= k_max_ratio; }
bool power_of_two(std::uint32_t value) noexcept { return value >= 64U && (value & (value - 1U)) == 0U; }
float wrap_phase(float value) noexcept {
    constexpr float two_pi = 2.0F * std::numbers::pi_v<float>;
    value = std::fmod(value + std::numbers::pi_v<float>, two_pi);
    if (value < 0.0F) value += two_pi;
    return value - std::numbers::pi_v<float>;
}
std::uint64_t round_u64(double value) noexcept {
    if (!(value > 0.0)) return 0;
    const double cap = static_cast<double>(std::numeric_limits<std::uint64_t>::max());
    return static_cast<std::uint64_t>(std::llround(std::min(value, cap)));
}
}

class engine {
public:
    explicit engine(const boiledegg_research_pv_rt_config& config)
        : sample_rate_(config.sample_rate), channels_(config.channels), max_block_(config.max_block_frames),
          n_fft_(config.fft_size), bins_(n_fft_ / 2U + 1U), analysis_hop_(config.analysis_hop),
          mode_(static_cast<boiledegg_research_pv_rt_mode>(config.mode)), ratio_(config.initial_time_ratio),
          transient_floor_(config.transient_floor), transient_sigma_(config.transient_sigma), fft_(n_fft_),
          input_capacity_(next_capacity(static_cast<std::size_t>(n_fft_) * 8U + static_cast<std::size_t>(max_block_) * 4U)),
          ola_capacity_(next_capacity(static_cast<std::size_t>(n_fft_) * 16U + static_cast<std::size_t>(max_block_) * 16U)),
          fifo_capacity_(next_capacity(std::max<std::size_t>(65536U, static_cast<std::size_t>(max_block_) * 64U + static_cast<std::size_t>(n_fft_) * 16U))),
          input_(static_cast<std::size_t>(channels_) * input_capacity_, 0.0F),
          ola_(static_cast<std::size_t>(channels_) * ola_capacity_, 0.0F), weight_(ola_capacity_, 0.0F),
          fifo_(static_cast<std::size_t>(channels_) * fifo_capacity_, 0.0F), window_(n_fft_), omega_(bins_),
          fft_work_(static_cast<std::size_t>(channels_) * n_fft_), magnitude_(static_cast<std::size_t>(channels_) * bins_),
          phase_(static_cast<std::size_t>(channels_) * bins_), previous_phase_(static_cast<std::size_t>(channels_) * bins_),
          previous_output_phase_(static_cast<std::size_t>(channels_) * bins_), output_phase_(static_cast<std::size_t>(channels_) * bins_),
          linked_magnitude_(bins_), previous_linked_magnitude_(bins_), peaks_(bins_), owners_(bins_) {
        const float scale = 2.0F * std::numbers::pi_v<float> / static_cast<float>(n_fft_);
        for (std::uint32_t i = 0; i < n_fft_; ++i) window_[i] = std::sqrt(0.5F - 0.5F * std::cos(scale * static_cast<float>(i)));
        for (std::uint32_t k = 0; k < bins_; ++k) omega_[k] = scale * static_cast<float>(k);
        reset();
    }

    static bool valid(const boiledegg_research_pv_rt_config& c) noexcept {
        return c.struct_size >= sizeof(boiledegg_research_pv_rt_config) && c.abi_version == BOILEDEGG_RESEARCH_PV_RT_ABI_VERSION &&
               c.sample_rate >= 8000U && c.sample_rate <= 384000U && c.channels >= 1U && c.channels <= 8U &&
               c.max_block_frames >= 1U && c.max_block_frames <= 16384U && power_of_two(c.fft_size) &&
               c.fft_size <= 16384U && c.analysis_hop >= 1U && c.analysis_hop <= c.fft_size / 2U &&
               c.mode <= BOILEDEGG_RESEARCH_PV_RT_TRANSIENT && finite_ratio(c.initial_time_ratio) &&
               std::isfinite(c.transient_floor) && c.transient_floor >= 0.0F &&
               std::isfinite(c.transient_sigma) && c.transient_sigma >= 0.0F;
    }

    void reset() noexcept {
        std::fill(input_.begin(), input_.end(), 0.0F); std::fill(ola_.begin(), ola_.end(), 0.0F);
        std::fill(weight_.begin(), weight_.end(), 0.0F); std::fill(fifo_.begin(), fifo_.end(), 0.0F);
        std::fill(previous_phase_.begin(), previous_phase_.end(), 0.0F);
        std::fill(previous_output_phase_.begin(), previous_output_phase_.end(), 0.0F);
        std::fill(previous_linked_magnitude_.begin(), previous_linked_magnitude_.end(), 0.0F);
        input_write_ = n_fft_ / 2U; analysis_start_ = 0; synthesis_position_ = 0.0; latest_safe_position_ = 0;
        cleanup_position_ = 0; startup_crop_ = round_u64(static_cast<double>(n_fft_ / 2U) * static_cast<double>(ratio_));
        real_input_frames_ = 0; expected_output_frames_ = 0.0; emitted_frames_ = 0;
        fifo_read_ = 0; fifo_write_ = 0; fifo_count_ = 0; initialized_ = false; flushed_ = false;
        flux_mean_ = 0.0F; flux_variance_ = 0.0F;
    }

    boiledegg_research_pv_rt_result set_ratio(float value) noexcept {
        if (!finite_ratio(value) || flushed_) return flushed_ ? BOILEDEGG_RESEARCH_PV_RT_ALREADY_FLUSHED : BOILEDEGG_RESEARCH_PV_RT_INVALID_ARGUMENT;
        ratio_ = value;
        if (real_input_frames_ == 0 && !initialized_) startup_crop_ = round_u64(static_cast<double>(n_fft_ / 2U) * static_cast<double>(ratio_));
        drain_safe(false);
        return BOILEDEGG_RESEARCH_PV_RT_OK;
    }

    boiledegg_research_pv_rt_result push(const float* const* input, std::uint32_t frames) noexcept {
        if (flushed_) return BOILEDEGG_RESEARCH_PV_RT_ALREADY_FLUSHED;
        if (frames > max_block_ || (frames != 0U && input == nullptr)) return BOILEDEGG_RESEARCH_PV_RT_INVALID_ARGUMENT;
        for (std::uint32_t ch = 0; ch < channels_; ++ch) if (frames != 0U && input[ch] == nullptr) return BOILEDEGG_RESEARCH_PV_RT_INVALID_ARGUMENT;
        for (std::uint32_t i = 0; i < frames; ++i) {
            if (!ensure_input_space()) return BOILEDEGG_RESEARCH_PV_RT_INTERNAL_ERROR;
            const std::size_t slot = static_cast<std::size_t>(input_write_ % input_capacity_);
            for (std::uint32_t ch = 0; ch < channels_; ++ch) input_[static_cast<std::size_t>(ch) * input_capacity_ + slot] = input[ch][i];
            ++input_write_; ++real_input_frames_; expected_output_frames_ += static_cast<double>(ratio_);
            process_available(); drain_safe(false);
            if (fifo_count_ >= fifo_capacity_) return BOILEDEGG_RESEARCH_PV_RT_FIFO_OVERFLOW;
        }
        process_available(); drain_safe(false);
        return BOILEDEGG_RESEARCH_PV_RT_OK;
    }

    boiledegg_research_pv_rt_result flush() noexcept {
        if (flushed_) return BOILEDEGG_RESEARCH_PV_RT_ALREADY_FLUSHED;
        flushed_ = true;
        const std::uint64_t wanted = round_u64(expected_output_frames_);
        const std::uint64_t timeline_target = startup_crop_ + wanted;
        std::uint64_t guard = 0;
        while ((latest_safe_position_ < timeline_target || emitted_frames_ < wanted) && guard < static_cast<std::uint64_t>(n_fft_) * 64U + wanted * 2U + 65536U) {
            if (!ensure_input_space()) return BOILEDEGG_RESEARCH_PV_RT_INTERNAL_ERROR;
            const std::size_t slot = static_cast<std::size_t>(input_write_ % input_capacity_);
            for (std::uint32_t ch = 0; ch < channels_; ++ch) input_[static_cast<std::size_t>(ch) * input_capacity_ + slot] = 0.0F;
            ++input_write_; process_available(); drain_safe(true); ++guard;
            if (fifo_count_ >= fifo_capacity_ && emitted_frames_ < wanted) return BOILEDEGG_RESEARCH_PV_RT_FIFO_OVERFLOW;
        }
        drain_safe(true);
        return emitted_frames_ == wanted ? BOILEDEGG_RESEARCH_PV_RT_OK : BOILEDEGG_RESEARCH_PV_RT_INTERNAL_ERROR;
    }

    std::uint32_t pull(float* const* output, std::uint32_t capacity) noexcept {
        if (capacity != 0U && output == nullptr) return 0U;
        for (std::uint32_t ch = 0; ch < channels_; ++ch) if (capacity != 0U && output[ch] == nullptr) return 0U;
        const std::uint32_t count = static_cast<std::uint32_t>(std::min<std::uint64_t>(capacity, fifo_count_));
        for (std::uint32_t i = 0; i < count; ++i) {
            const std::size_t slot = static_cast<std::size_t>((fifo_read_ + i) % fifo_capacity_);
            for (std::uint32_t ch = 0; ch < channels_; ++ch) output[ch][i] = fifo_[static_cast<std::size_t>(ch) * fifo_capacity_ + slot];
        }
        fifo_read_ = (fifo_read_ + count) % fifo_capacity_; fifo_count_ -= count;
        return count;
    }

    [[nodiscard]] std::uint32_t available() const noexcept { return static_cast<std::uint32_t>(std::min<std::uint64_t>(fifo_count_, std::numeric_limits<std::uint32_t>::max())); }
    [[nodiscard]] float ratio() const noexcept { return ratio_; }
    [[nodiscard]] std::uint32_t latency() const noexcept { return n_fft_ + max_block_; }
    [[nodiscard]] std::uint64_t input_frames() const noexcept { return real_input_frames_; }
    [[nodiscard]] std::uint64_t output_frames() const noexcept { return emitted_frames_; }

private:
    static std::size_t next_capacity(std::size_t value) noexcept { std::size_t result = 1; while (result < value) result <<= 1; return result; }
    [[nodiscard]] bool full_analysis_frame() const noexcept { return input_write_ >= analysis_start_ + n_fft_; }
    [[nodiscard]] bool ensure_input_space() noexcept {
        while (input_write_ - analysis_start_ >= input_capacity_ - 1U) {
            if (!full_analysis_frame()) return false;
            process_frame();
        }
        return true;
    }
    void process_available() noexcept { while (full_analysis_frame()) process_frame(); }

    void find_peaks() noexcept {
        peak_count_ = 0;
        float maximum = 0.0F; for (float value : linked_magnitude_) maximum = std::max(maximum, value);
        const float threshold = maximum * std::pow(10.0F, -55.0F / 20.0F);
        if (bins_ >= 2U && linked_magnitude_[0] > linked_magnitude_[1] && linked_magnitude_[0] >= threshold) peaks_[peak_count_++] = 0U;
        for (std::uint32_t k = 1; k + 1U < bins_; ++k) if (linked_magnitude_[k] >= linked_magnitude_[k-1U] && linked_magnitude_[k] > linked_magnitude_[k+1U] && linked_magnitude_[k] >= threshold) peaks_[peak_count_++] = k;
        if (bins_ >= 2U && linked_magnitude_[bins_-1U] >= linked_magnitude_[bins_-2U] && linked_magnitude_[bins_-1U] >= threshold) peaks_[peak_count_++] = bins_-1U;
        if (peak_count_ == 0U) peaks_[peak_count_++] = static_cast<std::uint32_t>(std::distance(linked_magnitude_.begin(), std::max_element(linked_magnitude_.begin(), linked_magnitude_.end())));
        std::uint32_t begin = 0;
        for (std::uint32_t i = 0; i < peak_count_; ++i) {
            const std::uint32_t end = (i + 1U < peak_count_) ? ((peaks_[i] + peaks_[i+1U]) / 2U + 1U) : bins_;
            for (std::uint32_t k = begin; k < end; ++k) owners_[k] = peaks_[i];
            begin = end;
        }
    }

    void process_frame() noexcept {
        const std::uint64_t synth_start = round_u64(synthesis_position_);
        for (std::uint32_t ch = 0; ch < channels_; ++ch) {
            auto* work = fft_work_.data() + static_cast<std::size_t>(ch) * n_fft_;
            for (std::uint32_t n = 0; n < n_fft_; ++n) {
                const std::size_t slot = static_cast<std::size_t>((analysis_start_ + n) % input_capacity_);
                work[n] = {input_[static_cast<std::size_t>(ch) * input_capacity_ + slot] * window_[n], 0.0F};
            }
            fft_.forward(work);
            for (std::uint32_t k = 0; k < bins_; ++k) {
                const std::size_t idx = static_cast<std::size_t>(ch) * bins_ + k;
                magnitude_[idx] = std::abs(work[k]); phase_[idx] = std::arg(work[k]);
            }
        }
        for (std::uint32_t k = 0; k < bins_; ++k) {
            double sum = 0.0; for (std::uint32_t ch = 0; ch < channels_; ++ch) { const float m = magnitude_[static_cast<std::size_t>(ch)*bins_+k]; sum += static_cast<double>(m)*m; }
            linked_magnitude_[k] = static_cast<float>(std::sqrt(sum / static_cast<double>(channels_) + k_epsilon));
        }
        float flux_numerator = 0.0F, flux_denominator = k_epsilon;
        for (std::uint32_t k = 0; k < bins_; ++k) { flux_numerator += std::max(0.0F, linked_magnitude_[k] - previous_linked_magnitude_[k]); flux_denominator += previous_linked_magnitude_[k]; }
        const float flux = initialized_ ? flux_numerator / flux_denominator : 0.0F;
        const float sigma = std::sqrt(std::max(flux_variance_, 0.0F));
        const bool transient = mode_ == BOILEDEGG_RESEARCH_PV_RT_TRANSIENT && initialized_ && flux > transient_floor_ && flux > flux_mean_ + transient_sigma_ * sigma;
        if (mode_ != BOILEDEGG_RESEARCH_PV_RT_CLASSIC) find_peaks();
        const std::uint64_t previous_synth = previous_synth_start_;
        const float synthesis_hop = initialized_ ? static_cast<float>(synth_start - previous_synth) : 0.0F;
        for (std::uint32_t ch = 0; ch < channels_; ++ch) {
            for (std::uint32_t k = 0; k < bins_; ++k) {
                const std::size_t idx = static_cast<std::size_t>(ch) * bins_ + k;
                if (!initialized_ || transient) output_phase_[idx] = phase_[idx];
                else {
                    const float delta = wrap_phase(phase_[idx] - previous_phase_[idx] - omega_[k] * static_cast<float>(analysis_hop_));
                    const float instantaneous = omega_[k] + delta / static_cast<float>(analysis_hop_);
                    output_phase_[idx] = previous_output_phase_[idx] + instantaneous * synthesis_hop;
                }
            }
            if (initialized_ && !transient && mode_ != BOILEDEGG_RESEARCH_PV_RT_CLASSIC) {
                for (std::uint32_t k = 0; k < bins_; ++k) {
                    const std::uint32_t owner = owners_[k];
                    const std::size_t idx = static_cast<std::size_t>(ch) * bins_ + k;
                    const std::size_t owner_idx = static_cast<std::size_t>(ch) * bins_ + owner;
                    output_phase_[idx] = output_phase_[owner_idx] + wrap_phase(phase_[idx] - phase_[owner_idx]);
                }
            }
            auto* work = fft_work_.data() + static_cast<std::size_t>(ch) * n_fft_;
            for (std::uint32_t k = 0; k < bins_; ++k) {
                const std::size_t idx = static_cast<std::size_t>(ch) * bins_ + k;
                work[k] = std::polar(magnitude_[idx], output_phase_[idx]);
            }
            for (std::uint32_t k = bins_; k < n_fft_; ++k) work[k] = std::conj(work[n_fft_ - k]);
            fft_.inverse(work);
            for (std::uint32_t n = 0; n < n_fft_; ++n) {
                const std::uint64_t absolute = synth_start + n; const std::size_t slot = static_cast<std::size_t>(absolute % ola_capacity_);
                ola_[static_cast<std::size_t>(ch) * ola_capacity_ + slot] += work[n].real() * window_[n];
            }
        }
        for (std::uint32_t n = 0; n < n_fft_; ++n) { const std::size_t slot = static_cast<std::size_t>((synth_start+n)%ola_capacity_); weight_[slot] += window_[n]*window_[n]; }
        latest_safe_position_ = synth_start; drain_safe(flushed_);
        previous_phase_ = phase_; previous_output_phase_ = output_phase_; previous_linked_magnitude_ = linked_magnitude_;
        if (initialized_) { constexpr float alpha=0.04F; const float difference=flux-flux_mean_; flux_mean_ += alpha*difference; flux_variance_=(1.0F-alpha)*(flux_variance_+alpha*difference*difference); }
        else { flux_mean_=flux; flux_variance_=0.0F; initialized_=true; }
        previous_synth_start_ = synth_start; synthesis_position_ += static_cast<double>(analysis_hop_) * static_cast<double>(ratio_); analysis_start_ += analysis_hop_;
    }

    void drain_safe(bool finalizing) noexcept {
        const std::uint64_t max_emit = finalizing ? round_u64(expected_output_frames_) : static_cast<std::uint64_t>(std::floor(std::max(0.0, expected_output_frames_)));
        const std::uint64_t timeline_limit = startup_crop_ + max_emit;
        const std::uint64_t target = std::min(latest_safe_position_, timeline_limit);
        while (cleanup_position_ < target) {
            const std::size_t slot = static_cast<std::size_t>(cleanup_position_ % ola_capacity_);
            if (cleanup_position_ >= startup_crop_) {
                if (fifo_count_ >= fifo_capacity_) return;
                const float norm = weight_[slot] > 1.0e-9F ? 1.0F / weight_[slot] : 0.0F;
                const std::size_t fifo_slot = static_cast<std::size_t>(fifo_write_ % fifo_capacity_);
                for (std::uint32_t ch = 0; ch < channels_; ++ch) fifo_[static_cast<std::size_t>(ch)*fifo_capacity_+fifo_slot] = ola_[static_cast<std::size_t>(ch)*ola_capacity_+slot] * norm;
                fifo_write_ = (fifo_write_ + 1U) % fifo_capacity_; ++fifo_count_; ++emitted_frames_;
            }
            for (std::uint32_t ch = 0; ch < channels_; ++ch) ola_[static_cast<std::size_t>(ch)*ola_capacity_+slot] = 0.0F;
            weight_[slot] = 0.0F; ++cleanup_position_;
        }
    }

    std::uint32_t sample_rate_{}, channels_{}, max_block_{}, n_fft_{}, bins_{}, analysis_hop_{};
    boiledegg_research_pv_rt_mode mode_{}; float ratio_{}, transient_floor_{}, transient_sigma_{};
    fft_plan fft_; std::size_t input_capacity_{}, ola_capacity_{}, fifo_capacity_{};
    std::vector<float> input_, ola_, weight_, fifo_, window_, omega_, magnitude_, phase_, previous_phase_, previous_output_phase_, output_phase_, linked_magnitude_, previous_linked_magnitude_;
    std::vector<std::complex<float>> fft_work_; std::vector<std::uint32_t> peaks_, owners_; std::uint32_t peak_count_{};
    std::uint64_t input_write_{}, analysis_start_{}, previous_synth_start_{}, latest_safe_position_{}, cleanup_position_{}, startup_crop_{}, real_input_frames_{}, emitted_frames_{};
    double synthesis_position_{}, expected_output_frames_{}; std::uint64_t fifo_read_{}, fifo_write_{}, fifo_count_{};
    bool initialized_{}, flushed_{}; float flux_mean_{}, flux_variance_{};
};
}

struct boiledegg_research_pv_rt_handle { boiled_egg::research::detail::engine* engine{}; };

extern "C" {
boiledegg_research_pv_rt_config boiledegg_research_pv_rt_default_config(uint32_t sample_rate, uint32_t channels, uint32_t max_block_frames) {
    boiledegg_research_pv_rt_config c{}; c.struct_size=sizeof(c); c.abi_version=BOILEDEGG_RESEARCH_PV_RT_ABI_VERSION; c.sample_rate=sample_rate; c.channels=channels; c.max_block_frames=max_block_frames; c.fft_size=2048; c.analysis_hop=256; c.mode=BOILEDEGG_RESEARCH_PV_RT_TRANSIENT; c.initial_time_ratio=1.0F; c.transient_floor=0.12F; c.transient_sigma=2.5F; return c;
}
boiledegg_research_pv_rt_handle* boiledegg_research_pv_rt_create(const boiledegg_research_pv_rt_config* config, boiledegg_research_pv_rt_result* result) {
    if (result) *result=BOILEDEGG_RESEARCH_PV_RT_INVALID_ARGUMENT;
    if (!config || !boiled_egg::research::detail::engine::valid(*config)) { if (result) *result=BOILEDEGG_RESEARCH_PV_RT_INVALID_CONFIG; return nullptr; }
    try { auto* h=new boiledegg_research_pv_rt_handle; try { h->engine=new boiled_egg::research::detail::engine(*config); } catch (...) { delete h; throw; } if (result) *result=BOILEDEGG_RESEARCH_PV_RT_OK; return h; }
    catch (const std::bad_alloc&) { if (result) *result=BOILEDEGG_RESEARCH_PV_RT_OUT_OF_MEMORY; return nullptr; }
    catch (...) { if (result) *result=BOILEDEGG_RESEARCH_PV_RT_INTERNAL_ERROR; return nullptr; }
}
void boiledegg_research_pv_rt_destroy(boiledegg_research_pv_rt_handle* h) { if (h) { delete h->engine; delete h; } }
boiledegg_research_pv_rt_result boiledegg_research_pv_rt_reset(boiledegg_research_pv_rt_handle* h) { if (!h||!h->engine) return BOILEDEGG_RESEARCH_PV_RT_INVALID_ARGUMENT; h->engine->reset(); return BOILEDEGG_RESEARCH_PV_RT_OK; }
boiledegg_research_pv_rt_result boiledegg_research_pv_rt_set_time_ratio(boiledegg_research_pv_rt_handle* h,float ratio){ return (!h||!h->engine)?BOILEDEGG_RESEARCH_PV_RT_INVALID_ARGUMENT:h->engine->set_ratio(ratio); }
float boiledegg_research_pv_rt_get_time_ratio(const boiledegg_research_pv_rt_handle* h){ return (!h||!h->engine)?0.0F:h->engine->ratio(); }
boiledegg_research_pv_rt_result boiledegg_research_pv_rt_push(boiledegg_research_pv_rt_handle* h,const float* const* input,uint32_t frames){ return (!h||!h->engine)?BOILEDEGG_RESEARCH_PV_RT_INVALID_ARGUMENT:h->engine->push(input,frames); }
uint32_t boiledegg_research_pv_rt_available(const boiledegg_research_pv_rt_handle* h){ return (!h||!h->engine)?0U:h->engine->available(); }
uint32_t boiledegg_research_pv_rt_pull(boiledegg_research_pv_rt_handle* h,float* const* output,uint32_t capacity){ return (!h||!h->engine)?0U:h->engine->pull(output,capacity); }
boiledegg_research_pv_rt_result boiledegg_research_pv_rt_flush(boiledegg_research_pv_rt_handle* h){ return (!h||!h->engine)?BOILEDEGG_RESEARCH_PV_RT_INVALID_ARGUMENT:h->engine->flush(); }
uint32_t boiledegg_research_pv_rt_latency_frames(const boiledegg_research_pv_rt_handle* h){ return (!h||!h->engine)?0U:h->engine->latency(); }
uint64_t boiledegg_research_pv_rt_input_frames(const boiledegg_research_pv_rt_handle* h){ return (!h||!h->engine)?0U:h->engine->input_frames(); }
uint64_t boiledegg_research_pv_rt_output_frames(const boiledegg_research_pv_rt_handle* h){ return (!h||!h->engine)?0U:h->engine->output_frames(); }
const char* boiledegg_research_pv_rt_result_string(boiledegg_research_pv_rt_result r){ switch(r){case BOILEDEGG_RESEARCH_PV_RT_OK:return "ok";case BOILEDEGG_RESEARCH_PV_RT_INVALID_ARGUMENT:return "invalid argument";case BOILEDEGG_RESEARCH_PV_RT_INVALID_CONFIG:return "invalid config";case BOILEDEGG_RESEARCH_PV_RT_OUT_OF_MEMORY:return "out of memory";case BOILEDEGG_RESEARCH_PV_RT_FIFO_OVERFLOW:return "output FIFO overflow";case BOILEDEGG_RESEARCH_PV_RT_ALREADY_FLUSHED:return "already flushed";default:return "internal error";} }
}
