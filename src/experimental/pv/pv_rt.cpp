#include "boiled_egg_pv_rt.h"
#include "fft.hpp"
#include "fuzzy_phase.hpp"
#include "research_features.hpp"
#include "execution_helpers.hpp"
#include "work_sequence.hpp"

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
constexpr int k_resampler_taps = 40;
constexpr int k_resampler_half = k_resampler_taps / 2;

bool finite_ratio(float value) noexcept {
    return std::isfinite(value) && value >= k_min_ratio && value <= k_max_ratio;
}
bool power_of_two(std::uint32_t value) noexcept {
    return value >= 64U && (value & (value - 1U)) == 0U;
}
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
double sinc_pi(double x) noexcept {
    if (std::abs(x) < 1.0e-14) return 1.0;
    const double p = std::numbers::pi_v<double> * x;
    return std::sin(p) / p;
}

struct resampler_kernel_bank {
    static constexpr int phases = 1024;
    static constexpr int cutoffs = 32;
    static constexpr double cutoff_min = 0.94 / 4.0;
    static constexpr double cutoff_max = 0.94;
    std::vector<float> weights;

    resampler_kernel_bank() : weights(static_cast<std::size_t>(cutoffs) * phases * k_resampler_taps) {
        for (int ci = 0; ci < cutoffs; ++ci) {
            const double cutoff = cutoff_for_index(ci);
            for (int phase = 0; phase < phases; ++phase) {
                const double frac = static_cast<double>(phase) / phases;
                double sum = 0.0;
                float* dst = data(ci, phase);
                for (int tap = 0; tap < k_resampler_taps; ++tap) {
                    const int offset = tap - (k_resampler_half - 1);
                    const double distance = static_cast<double>(offset) - frac;
                    const double window = 0.42 + 0.5 * std::cos(std::numbers::pi_v<double> * distance / k_resampler_half)
                                          + 0.08 * std::cos(2.0 * std::numbers::pi_v<double> * distance / k_resampler_half);
                    const double value = std::abs(distance) <= k_resampler_half
                        ? cutoff * sinc_pi(cutoff * distance) * window : 0.0;
                    dst[tap] = static_cast<float>(value);
                    sum += value;
                }
                if (std::abs(sum) > 1.0e-14) {
                    const float inv = static_cast<float>(1.0 / sum);
                    for (int tap = 0; tap < k_resampler_taps; ++tap) dst[tap] *= inv;
                }
            }
        }
    }
    static constexpr double cutoff_for_index(int i) noexcept {
        return cutoff_min + (cutoff_max - cutoff_min) * static_cast<double>(i) / static_cast<double>(cutoffs - 1);
    }
    static int cutoff_index(double desired) noexcept {
        desired = std::clamp(desired, cutoff_min, cutoff_max);
        const double scaled = (desired - cutoff_min) * static_cast<double>(cutoffs - 1) / (cutoff_max - cutoff_min);
        return std::clamp(static_cast<int>(std::floor(scaled)), 0, cutoffs - 1);
    }
    float* data(int cutoff, int phase) noexcept {
        return weights.data() + (static_cast<std::size_t>(cutoff) * phases + phase) * k_resampler_taps;
    }
    const float* data(int cutoff, int phase) const noexcept {
        return weights.data() + (static_cast<std::size_t>(cutoff) * phases + phase) * k_resampler_taps;
    }
};

const resampler_kernel_bank& kernels() {
    static const resampler_kernel_bank bank;
    return bank;
}

} // namespace

class engine {
public:
    explicit engine(const boiledegg_research_pv_rt_config& config, const boiledegg_research_features& features,
                    const boiledegg_research_execution& execution)
        : sample_rate_(config.sample_rate), channels_(config.channels), max_block_(config.max_block_frames),
          n_fft_(config.fft_size), bins_(n_fft_ / 2U + 1U), analysis_hop_(config.analysis_hop),
          mode_(static_cast<boiledegg_research_pv_rt_mode>(config.mode)),
          formant_mode_(static_cast<boiledegg_research_pv_rt_formant_mode>(config.formant_mode)),
          time_ratio_(config.initial_time_ratio), pitch_ratio_(config.initial_pitch_ratio),
          timing_policy_(features.timing_policy), formant_ratio_(features.initial_formant_ratio),
          smoothed_formant_ratio_(features.initial_formant_ratio),
          formant_smoothing_(1.0F - std::exp(-static_cast<float>(analysis_hop_) / (0.010F * static_cast<float>(sample_rate_)))),
          transient_floor_(config.transient_floor), transient_sigma_(config.transient_sigma),
          formant_cepstral_order_(config.formant_cepstral_order),
          formant_gain_limit_db_(config.formant_gain_limit_db),
          monophonic_min_f0_hz_(config.monophonic_min_f0_hz), monophonic_max_f0_hz_(config.monophonic_max_f0_hz),
          fft_(n_fft_),
          input_capacity_(next_capacity(static_cast<std::size_t>(n_fft_) * 8U + static_cast<std::size_t>(max_block_) * 4U)),
          ola_capacity_(next_capacity(static_cast<std::size_t>(n_fft_) * 16U + static_cast<std::size_t>(max_block_) * 16U)),
          pv_capacity_(next_capacity(std::max<std::size_t>(65536U, static_cast<std::size_t>(max_block_) * 64U + static_cast<std::size_t>(n_fft_) * 32U))),
          fifo_capacity_(next_capacity(std::max<std::size_t>(65536U, static_cast<std::size_t>(max_block_) * 64U + static_cast<std::size_t>(n_fft_) * 16U))),
          input_(static_cast<std::size_t>(channels_) * input_capacity_, 0.0F),
          ola_(static_cast<std::size_t>(channels_) * ola_capacity_, 0.0F), weight_(ola_capacity_, 0.0F),
          pv_fifo_(static_cast<std::size_t>(channels_) * pv_capacity_, 0.0F),
          fifo_(static_cast<std::size_t>(channels_) * fifo_capacity_, 0.0F), window_(n_fft_), omega_(bins_),
          magnitude_(static_cast<std::size_t>(channels_) * bins_), phase_(static_cast<std::size_t>(channels_) * bins_),
          previous_phase_(static_cast<std::size_t>(channels_) * bins_),
          previous_output_phase_(static_cast<std::size_t>(channels_) * bins_), output_phase_(static_cast<std::size_t>(channels_) * bins_),
          linked_magnitude_(bins_), previous_linked_magnitude_(bins_),
          fft_work_(static_cast<std::size_t>(channels_) * n_fft_), envelope_work_(n_fft_),
          log_envelope_(bins_), formant_gain_(bins_, 1.0F), peaks_(bins_), owners_(bins_),
          fuzzy_(config.mode >= BOILEDEGG_RESEARCH_PV_RT_FUZZY ? bins_ : 0U,
                 n_fft_, sample_rate_) {
        const float scale = 2.0F * std::numbers::pi_v<float> / static_cast<float>(n_fft_);
        for (std::uint32_t i = 0; i < n_fft_; ++i) {
            window_[i] = std::sqrt(0.5F - 0.5F * std::cos(scale * static_cast<float>(i)));
        }
        for (std::uint32_t k = 0; k < bins_; ++k) omega_[k] = scale * static_cast<float>(k);
        (void)kernels(); // precompute resampler tables during construction, never in the hot path
        scheduled_=execution.scheduled!=0;
        simd_=execution.simd!=0;
        if (scheduled_) {
            // Conservative finite work budget. Scheduler overruns are reported,
            // not hidden by synchronously finishing a late frame in push().
            unsigned levels=0; for(auto n=n_fft_;n>1;n>>=1) ++levels;
            steps_per_input_=2U + (n_fft_*(channels_+1U)*(levels+20U)+128U*analysis_hop_-1U)/(128U*analysis_hop_);
            const auto step_bound=execution::frame_step_bound(n_fft_,channels_,formant_mode_,mode_);
            steps_per_input_=std::max(steps_per_input_,(step_bound+analysis_hop_-1U)/analysis_hop_);
            frame_task_=frame_sequence(); formant_task_=formant_sequence(); peaks_task_=peaks_sequence();
            if (mode_>=BOILEDEGG_RESEARCH_PV_RT_FUZZY) fuzzy_.enable_slicing();
        }
        reset();
    }

    static bool valid(const boiledegg_research_pv_rt_config& c) noexcept {
        return c.struct_size >= sizeof(boiledegg_research_pv_rt_config) &&
               c.abi_version == BOILEDEGG_RESEARCH_PV_RT_ABI_VERSION &&
               c.sample_rate >= 8000U && c.sample_rate <= 384000U && c.channels >= 1U && c.channels <= 8U &&
               c.max_block_frames >= 1U && c.max_block_frames <= 16384U && power_of_two(c.fft_size) &&
               c.fft_size <= 16384U && c.analysis_hop >= 1U && c.analysis_hop <= c.fft_size / 2U &&
               c.mode <= BOILEDEGG_RESEARCH_PV_RT_FUZZY_NOISE && finite_ratio(c.initial_time_ratio) &&
               finite_ratio(c.initial_pitch_ratio) && std::isfinite(c.transient_floor) && c.transient_floor >= 0.0F &&
               std::isfinite(c.transient_sigma) && c.transient_sigma >= 0.0F &&
               c.formant_mode <= BOILEDEGG_RESEARCH_PV_RT_FORMANT_MONOPHONIC &&
               c.formant_cepstral_order >= 4U && c.formant_cepstral_order < c.fft_size / 2U &&
               std::isfinite(c.formant_gain_limit_db) && c.formant_gain_limit_db >= 0.0F && c.formant_gain_limit_db <= 36.0F &&
               std::isfinite(c.monophonic_min_f0_hz) && std::isfinite(c.monophonic_max_f0_hz) &&
               c.monophonic_min_f0_hz >= 40.0F && c.monophonic_max_f0_hz > c.monophonic_min_f0_hz &&
               c.monophonic_max_f0_hz <= 2000.0F;
    }

    void reset() noexcept {
        finish_task();
        completed_frames_=frame_overruns_=max_frame_steps_=current_steps_=0;
        fuzzy_.reset();
        smoothed_formant_ratio_ = formant_ratio_;
        std::fill(input_.begin(), input_.end(), 0.0F);
        std::fill(ola_.begin(), ola_.end(), 0.0F);
        std::fill(weight_.begin(), weight_.end(), 0.0F);
        std::fill(pv_fifo_.begin(), pv_fifo_.end(), 0.0F);
        std::fill(fifo_.begin(), fifo_.end(), 0.0F);
        std::fill(previous_phase_.begin(), previous_phase_.end(), 0.0F);
        std::fill(previous_output_phase_.begin(), previous_output_phase_.end(), 0.0F);
        std::fill(previous_linked_magnitude_.begin(), previous_linked_magnitude_.end(), 0.0F);
        input_write_ = n_fft_ / 2U;
        analysis_start_ = 0;
        synthesis_position_ = 0.0;
        latest_safe_position_ = 0;
        cleanup_position_ = 0;
        startup_crop_ = startup_crop();
        real_input_frames_ = 0;
        expected_pv_frames_ = 0.0;
        expected_output_frames_ = 0.0;
        pv_emitted_frames_ = 0;
        emitted_frames_ = 0;
        pv_start_ = 0;
        pv_write_ = 0;
        resample_pos_ = 0.0;
        fifo_read_ = 0;
        fifo_write_ = 0;
        fifo_count_ = 0;
        initialized_ = false;
        flushed_ = false;
        flux_mean_ = 0.0F;
        flux_variance_ = 0.0F;
        formant_energy_compensation_ = 1.0F;
        target_pv_frames_ = std::numeric_limits<std::uint64_t>::max();
        target_output_frames_ = std::numeric_limits<std::uint64_t>::max();
    }

    boiledegg_research_pv_rt_result set_time_ratio(float value) noexcept {
        if (!finite_ratio(value) || flushed_) return flushed_ ? BOILEDEGG_RESEARCH_PV_RT_ALREADY_FLUSHED : BOILEDEGG_RESEARCH_PV_RT_INVALID_ARGUMENT;
        if (scheduled_ && value != 1.0F) return BOILEDEGG_RESEARCH_PV_RT_INVALID_ARGUMENT;
        time_ratio_ = value;
        if (scheduled_) { update_startup_crop(); return BOILEDEGG_RESEARCH_PV_RT_OK; }
        update_startup_crop();
        drain_safe(false);
        process_resampler(false);
        return BOILEDEGG_RESEARCH_PV_RT_OK;
    }

    boiledegg_research_pv_rt_result set_pitch_ratio(float value) noexcept {
        if (!finite_ratio(value) || flushed_) return flushed_ ? BOILEDEGG_RESEARCH_PV_RT_ALREADY_FLUSHED : BOILEDEGG_RESEARCH_PV_RT_INVALID_ARGUMENT;
        if (scheduled_ && (value < 0.5F || value > 2.0F || (real_input_frames_ && value != pitch_ratio_)))
            return BOILEDEGG_RESEARCH_PV_RT_INVALID_ARGUMENT;
        pitch_ratio_ = value;
        if (scheduled_) { update_startup_crop(); return BOILEDEGG_RESEARCH_PV_RT_OK; }
        update_startup_crop();
        drain_safe(false);
        process_resampler(false);
        return BOILEDEGG_RESEARCH_PV_RT_OK;
    }

    boiledegg_research_pv_rt_result set_formant_ratio(float value) noexcept {
        if (flushed_) return BOILEDEGG_RESEARCH_PV_RT_ALREADY_FLUSHED;
        if (!features::ratio_valid(value) ||
            (formant_mode_ == BOILEDEGG_RESEARCH_PV_RT_FORMANT_OFF && value != 1.0F))
            return BOILEDEGG_RESEARCH_PV_RT_INVALID_ARGUMENT;
        formant_ratio_ = value;
        if (!initialized_ && !frame_active_) smoothed_formant_ratio_ = value;
        return BOILEDEGG_RESEARCH_PV_RT_OK;
    }
    [[nodiscard]] float formant_ratio() const noexcept { return formant_ratio_; }

    boiledegg_research_pv_rt_result push(const float* const* input, std::uint32_t frames) noexcept {
        if (flushed_) return BOILEDEGG_RESEARCH_PV_RT_ALREADY_FLUSHED;
        if (frames > max_block_ || (frames != 0U && input == nullptr)) return BOILEDEGG_RESEARCH_PV_RT_INVALID_ARGUMENT;
        for (std::uint32_t ch = 0; ch < channels_; ++ch) if (frames != 0U && input[ch] == nullptr) return BOILEDEGG_RESEARCH_PV_RT_INVALID_ARGUMENT;
        for (std::uint32_t i = 0; i < frames; ++i) {
            if (!ensure_input_space()) return BOILEDEGG_RESEARCH_PV_RT_INTERNAL_ERROR;
            const std::size_t slot = static_cast<std::size_t>(input_write_ % input_capacity_);
            for (std::uint32_t ch = 0; ch < channels_; ++ch)
                input_[static_cast<std::size_t>(ch) * input_capacity_ + slot] = input[ch][i];
            ++input_write_;
            ++real_input_frames_;
            expected_output_frames_ += static_cast<double>(time_ratio_);
            expected_pv_frames_ += internal_stretch();
            if (scheduled_) { if (!tick()) return BOILEDEGG_RESEARCH_PV_RT_INTERNAL_ERROR; }
            else process_available();
            drain_safe(false);
            process_resampler(false);
            if (fifo_count_ >= fifo_capacity_) return BOILEDEGG_RESEARCH_PV_RT_FIFO_OVERFLOW;
        }
        if (scheduled_) return BOILEDEGG_RESEARCH_PV_RT_OK;
        process_available();
        drain_safe(false);
        process_resampler(false);
        return BOILEDEGG_RESEARCH_PV_RT_OK;
    }

    boiledegg_research_pv_rt_result flush() noexcept {
        if (flushed_) return BOILEDEGG_RESEARCH_PV_RT_ALREADY_FLUSHED;
        flushed_ = true;
        target_pv_frames_ = round_u64(expected_pv_frames_);
        target_output_frames_ = round_u64(expected_output_frames_);
        finish_task();
        const std::uint64_t timeline_target = startup_crop_ + target_pv_frames_;
        std::uint64_t guard = 0;
        const std::uint64_t guard_limit = static_cast<std::uint64_t>(n_fft_) * 96U + target_pv_frames_ * 2U + 131072U;
        while ((latest_safe_position_ < timeline_target || pv_emitted_frames_ < target_pv_frames_) && guard < guard_limit) {
            if (!ensure_input_space()) return BOILEDEGG_RESEARCH_PV_RT_INTERNAL_ERROR;
            const std::size_t slot = static_cast<std::size_t>(input_write_ % input_capacity_);
            for (std::uint32_t ch = 0; ch < channels_; ++ch)
                input_[static_cast<std::size_t>(ch) * input_capacity_ + slot] = 0.0F;
            ++input_write_;
            process_available();
            drain_safe(true);
            process_resampler(false);
            ++guard;
            if (fifo_count_ >= fifo_capacity_ && emitted_frames_ < target_output_frames_)
                return BOILEDEGG_RESEARCH_PV_RT_FIFO_OVERFLOW;
        }
        drain_safe(true);
        process_resampler(true);
        return (pv_emitted_frames_ == target_pv_frames_ && emitted_frames_ == target_output_frames_)
            ? BOILEDEGG_RESEARCH_PV_RT_OK : BOILEDEGG_RESEARCH_PV_RT_INTERNAL_ERROR;
    }

    std::uint32_t pull(float* const* output, std::uint32_t capacity) noexcept {
        if (capacity != 0U && output == nullptr) return 0U;
        for (std::uint32_t ch = 0; ch < channels_; ++ch) if (capacity != 0U && output[ch] == nullptr) return 0U;
        if (!scheduled_ || flushed_) process_resampler(flushed_ && pv_emitted_frames_ == target_pv_frames_);
        const std::uint32_t count = static_cast<std::uint32_t>(std::min<std::uint64_t>(capacity, fifo_count_));
        for (std::uint32_t i = 0; i < count; ++i) {
            const std::size_t slot = static_cast<std::size_t>((fifo_read_ + i) % fifo_capacity_);
            for (std::uint32_t ch = 0; ch < channels_; ++ch)
                output[ch][i] = fifo_[static_cast<std::size_t>(ch) * fifo_capacity_ + slot];
        }
        fifo_read_ = (fifo_read_ + count) % fifo_capacity_;
        fifo_count_ -= count;
        if (!scheduled_ || flushed_) process_resampler(flushed_ && pv_emitted_frames_ == target_pv_frames_);
        return count;
    }

    [[nodiscard]] std::uint32_t available() const noexcept {
        return static_cast<std::uint32_t>(std::min<std::uint64_t>(fifo_count_, std::numeric_limits<std::uint32_t>::max()));
    }
    [[nodiscard]] float time_ratio() const noexcept { return time_ratio_; }
    [[nodiscard]] float pitch_ratio() const noexcept { return pitch_ratio_; }
    [[nodiscard]] std::uint32_t latency() const noexcept { // Centered startup can require more input at compression. Fixed bound for
        // all time*pitch >= 1/16 avoids a ratio-dependent underreported hint.
        return (timing_policy_ == BOILEDEGG_RESEARCH_TIMING_CENTERED ? 9U*n_fft_ + analysis_hop_ + 16U*k_resampler_half : n_fft_)
            + max_block_ + k_resampler_half + 2U; }
    [[nodiscard]] std::uint64_t input_frames() const noexcept { return real_input_frames_; }
    [[nodiscard]] std::uint64_t output_frames() const noexcept { return emitted_frames_; }

private:
    static std::size_t next_capacity(std::size_t value) noexcept {
        std::size_t result = 1;
        while (result < value) result <<= 1;
        return result;
    }
    [[nodiscard]] double internal_stretch() const noexcept {
        return static_cast<double>(time_ratio_) * static_cast<double>(pitch_ratio_);
    }
    [[nodiscard]] std::uint64_t startup_crop() const noexcept {
        // Analysis is prepadded N/2, but synthesis frame centers remain N/2
        // from each frame start, not N/2 * stretch. Crop in synthesis units.
        return timing_policy_ == BOILEDEGG_RESEARCH_TIMING_CENTERED ? n_fft_/2U
            : round_u64(static_cast<double>(n_fft_/2U) * internal_stretch());
    }
    void update_startup_crop() noexcept {
        if (real_input_frames_ == 0 && !initialized_)
            startup_crop_ = startup_crop();
    }
    [[nodiscard]] bool full_analysis_frame() const noexcept { return input_write_ >= analysis_start_ + n_fft_; }
    [[nodiscard]] bool ensure_input_space() noexcept {
        if (scheduled_) return input_write_ - analysis_start_ < input_capacity_ - 1U;
        while (input_write_ - analysis_start_ >= input_capacity_ - 1U) {
            if (!full_analysis_frame()) return false;
            process_frame();
        }
        return true;
    }
    void process_available() noexcept {
        while (full_analysis_frame()) {
            if (scheduled_) { if (!frame_active_) start_task(); finish_task(); }
            else process_frame();
        }
    }

    void find_peaks() noexcept {
        peak_count_ = 0;
        float maximum = 0.0F;
        for (float value : linked_magnitude_) maximum = std::max(maximum, value);
        const float threshold = maximum * std::pow(10.0F, -55.0F / 20.0F);
        if (bins_ >= 2U && linked_magnitude_[0] > linked_magnitude_[1] && linked_magnitude_[0] >= threshold)
            peaks_[peak_count_++] = 0U;
        for (std::uint32_t k = 1; k + 1U < bins_; ++k)
            if (linked_magnitude_[k] >= linked_magnitude_[k - 1U] && linked_magnitude_[k] > linked_magnitude_[k + 1U] && linked_magnitude_[k] >= threshold)
                peaks_[peak_count_++] = k;
        if (bins_ >= 2U && linked_magnitude_[bins_ - 1U] >= linked_magnitude_[bins_ - 2U] && linked_magnitude_[bins_ - 1U] >= threshold)
            peaks_[peak_count_++] = bins_ - 1U;
        if (peak_count_ == 0U)
            peaks_[peak_count_++] = static_cast<std::uint32_t>(std::distance(linked_magnitude_.begin(), std::max_element(linked_magnitude_.begin(), linked_magnitude_.end())));
        std::uint32_t begin = 0;
        for (std::uint32_t i = 0; i < peak_count_; ++i) {
            const std::uint32_t end = (i + 1U < peak_count_) ? ((peaks_[i] + peaks_[i + 1U]) / 2U + 1U) : bins_;
            for (std::uint32_t k = begin; k < end; ++k) owners_[k] = peaks_[i];
            begin = end;
        }
    }

    void estimate_formant_gain() noexcept {
        std::fill(formant_gain_.begin(), formant_gain_.end(), 1.0F);
        if (smoothed_formant_ratio_ != formant_ratio_) {
            const float error = std::log(formant_ratio_ / smoothed_formant_ratio_);
            smoothed_formant_ratio_ = std::abs(error) < 1.0e-6F ? formant_ratio_
                : smoothed_formant_ratio_ * std::exp(formant_smoothing_ * error);
        }
        const float envelope_warp = pitch_ratio_ / smoothed_formant_ratio_;
        if (formant_mode_ == BOILEDEGG_RESEARCH_PV_RT_FORMANT_OFF ||
            std::abs(envelope_warp - 1.0F) < 1.0e-6F || formant_gain_limit_db_ <= 0.0F) {
            formant_energy_compensation_ = 1.0F;
            return;
        }

        for (std::uint32_t k = 0; k < bins_; ++k)
            envelope_work_[k] = {std::log(std::max(linked_magnitude_[k], 1.0e-7F)), 0.0F};
        for (std::uint32_t k = bins_; k < n_fft_; ++k)
            envelope_work_[k] = envelope_work_[n_fft_ - k];
        transform(envelope_work_.data(), true);

        float f0_hz = 0.0F;
        float voiced_confidence = 0.0F;
        if (formant_mode_ == BOILEDEGG_RESEARCH_PV_RT_FORMANT_MONOPHONIC) {
            const std::uint32_t q_min = std::max<std::uint32_t>(2U, static_cast<std::uint32_t>(std::floor(static_cast<float>(sample_rate_) / monophonic_max_f0_hz_)));
            const std::uint32_t q_max = std::min<std::uint32_t>(n_fft_ / 2U - 1U, static_cast<std::uint32_t>(std::ceil(static_cast<float>(sample_rate_) / monophonic_min_f0_hz_)));
            float peak = 0.0F;
            std::uint32_t peak_q = 0U;
            double energy = k_epsilon;
            std::uint32_t count = 0U;
            if (q_min <= q_max) {
                for (std::uint32_t q = q_min; q <= q_max; ++q) {
                    const float value = std::max(0.0F, envelope_work_[q].real());
                    energy += static_cast<double>(value) * value;
                    ++count;
                    if (value > peak) { peak = value; peak_q = q; }
                }
            }
            if (peak_q != 0U && count != 0U) {
                const float rms = static_cast<float>(std::sqrt(energy / count));
                const float salience = peak / std::max(rms, 1.0e-7F);
                voiced_confidence = std::clamp((salience - 1.4F) / 3.0F, 0.0F, 1.0F);
                f0_hz = static_cast<float>(sample_rate_) / static_cast<float>(peak_q);
            }
        }

        const std::uint32_t order = std::min<std::uint32_t>(formant_cepstral_order_, n_fft_ / 2U - 1U);
        const std::uint32_t taper = std::min<std::uint32_t>(8U, order > 1U ? order - 1U : 0U);
        for (std::uint32_t q = 1; q < n_fft_; ++q) {
            const std::uint32_t folded = std::min<std::uint32_t>(q, n_fft_ - q);
            if (folded > order) {
                envelope_work_[q] = {0.0F, 0.0F};
            } else if (taper != 0U && folded > order - taper) {
                const float x = static_cast<float>(folded - (order - taper)) / static_cast<float>(taper);
                const float w = 0.5F * (1.0F + std::cos(std::numbers::pi_v<float> * x));
                envelope_work_[q] *= w;
            }
        }
        transform(envelope_work_.data(), false);
        for (std::uint32_t k = 0; k < bins_; ++k) log_envelope_[k] = envelope_work_[k].real();

        constexpr float db_per_neper = 20.0F / 2.302585092994046F;
        constexpr float neper_per_db = 2.302585092994046F / 20.0F;
        const float bin_hz = static_cast<float>(sample_rate_) / static_cast<float>(n_fft_);
        for (std::uint32_t k = 0; k < bins_; ++k) {
            const float warped = static_cast<float>(k) * envelope_warp;
            const std::uint32_t k0 = static_cast<std::uint32_t>(std::min<float>(std::floor(warped), static_cast<float>(bins_ - 1U)));
            const std::uint32_t k1 = std::min<std::uint32_t>(k0 + 1U, bins_ - 1U);
            const float fraction = std::clamp(warped - static_cast<float>(k0), 0.0F, 1.0F);
            const float target_log = log_envelope_[k0] + fraction * (log_envelope_[k1] - log_envelope_[k0]);
            float gain_db = std::clamp((target_log - log_envelope_[k]) * db_per_neper,
                                       -formant_gain_limit_db_, formant_gain_limit_db_);
            float weight = 1.0F;
            if (formant_mode_ == BOILEDEGG_RESEARCH_PV_RT_FORMANT_MONOPHONIC && gain_db > 0.0F) {
                // Laroche's main failure case for naive envelope preservation is
                // large amplification between harmonics. Attenuation is safe to
                // apply everywhere; positive correction is concentrated around
                // the estimated harmonic lobes instead.
                weight = 0.0F;
                if (voiced_confidence > 0.0F && f0_hz > 0.0F && k != 0U) {
                    const float frequency = static_cast<float>(k) * bin_hz;
                    const float harmonic = std::max(1.0F, std::round(frequency / f0_hz));
                    const float distance = std::abs(frequency - harmonic * f0_hz);
                    const float radius = std::max(2.0F * bin_hz, 0.46F * f0_hz);
                    if (distance < radius) {
                        const float x = distance / radius;
                        const float c = std::cos(0.5F * std::numbers::pi_v<float> * x);
                        weight = voiced_confidence * c * c;
                    }
                }
            }
            formant_gain_[k] = std::exp(gain_db * weight * neper_per_db);
        }

        // Centre the formant EQ around 0 dB in a magnitude-squared weighted
        // log domain, then remove any remaining positive broadband power gain.
        // This keeps the relative envelope shape while avoiding the large
        // programme-level boosts/attenuations produced by a one-sided power
        // limiter. The scalar is linked across channels, preserving stereo.
        double input_energy = k_epsilon;
        double weighted_log_gain = 0.0;
        for (std::uint32_t k = 0; k < bins_; ++k) {
            const double symmetry = (k == 0U || k + 1U == bins_) ? 1.0 : 2.0;
            const double magnitude = static_cast<double>(linked_magnitude_[k]);
            const double weight_energy = symmetry * magnitude * magnitude;
            input_energy += weight_energy;
            weighted_log_gain += weight_energy *
                std::log(std::max(static_cast<double>(formant_gain_[k]), 1.0e-12));
        }
        const float log_centre = static_cast<float>(std::exp(-weighted_log_gain / input_energy));
        for (float& gain : formant_gain_) gain *= log_centre;

        double corrected_energy = k_epsilon;
        for (std::uint32_t k = 0; k < bins_; ++k) {
            const double symmetry = (k == 0U || k + 1U == bins_) ? 1.0 : 2.0;
            const double magnitude = static_cast<double>(linked_magnitude_[k]);
            const double corrected = magnitude * static_cast<double>(formant_gain_[k]);
            corrected_energy += symmetry * corrected * corrected;
        }
        float power_compensation = 1.0F;
        if (corrected_energy > input_energy) {
            power_compensation = static_cast<float>(std::sqrt(input_energy / corrected_energy));
            power_compensation = std::clamp(power_compensation, 0.25F, 1.0F);
        }
        formant_energy_compensation_ = log_centre * power_compensation;
        for (float& gain : formant_gain_) gain *= power_compensation;
    }

    void process_frame() noexcept {
        const std::uint64_t synth_start = round_u64(synthesis_position_);
        for (std::uint32_t ch = 0; ch < channels_; ++ch) {
            auto* work = fft_work_.data() + static_cast<std::size_t>(ch) * n_fft_;
            for (std::uint32_t n = 0; n < n_fft_; ++n) {
                const std::size_t slot = static_cast<std::size_t>((analysis_start_ + n) % input_capacity_);
                work[n] = {input_[static_cast<std::size_t>(ch) * input_capacity_ + slot] * window_[n], 0.0F};
            }
            transform(work, false);
            for (std::uint32_t k = 0; k < bins_; ++k) {
                const std::size_t idx = static_cast<std::size_t>(ch) * bins_ + k;
                magnitude_[idx] = std::abs(work[k]);
                phase_[idx] = std::arg(work[k]);
            }
        }
        for (std::uint32_t k = 0; k < bins_; ++k) {
            double sum = 0.0;
            for (std::uint32_t ch = 0; ch < channels_; ++ch) {
                const float m = magnitude_[static_cast<std::size_t>(ch) * bins_ + k];
                sum += static_cast<double>(m) * m;
            }
            linked_magnitude_[k] = static_cast<float>(std::sqrt(sum / static_cast<double>(channels_) + k_epsilon));
        }
        estimate_formant_gain();

        float flux_numerator = 0.0F, flux_denominator = k_epsilon;
        for (std::uint32_t k = 0; k < bins_; ++k) {
            flux_numerator += std::max(0.0F, linked_magnitude_[k] - previous_linked_magnitude_[k]);
            flux_denominator += previous_linked_magnitude_[k];
        }
        const float flux = initialized_ ? flux_numerator / flux_denominator : 0.0F;
        const float sigma = std::sqrt(std::max(flux_variance_, 0.0F));
        const bool transient = mode_ == BOILEDEGG_RESEARCH_PV_RT_TRANSIENT && initialized_ &&
                               flux > transient_floor_ && flux > flux_mean_ + transient_sigma_ * sigma;
        if (mode_ != BOILEDEGG_RESEARCH_PV_RT_CLASSIC) find_peaks();
        const std::uint64_t previous_synth = previous_synth_start_;
        const float synthesis_hop = initialized_ ? static_cast<float>(synth_start - previous_synth) : 0.0F;
        const bool fuzzy_mode = mode_ >= BOILEDEGG_RESEARCH_PV_RT_FUZZY;
        if (fuzzy_mode) {
            fuzzy_.process(linked_magnitude_.data(), previous_linked_magnitude_.data(),
                magnitude_.data(), phase_.data(), previous_phase_.data(), owners_.data(),
                omega_.data(), channels_, analysis_hop_, synthesis_hop,
                static_cast<float>(internal_stretch()), initialized_,
                mode_ == BOILEDEGG_RESEARCH_PV_RT_FUZZY, output_phase_.data());
        }
        for (std::uint32_t ch = 0; ch < channels_; ++ch) {
            if (!fuzzy_mode) {
            for (std::uint32_t k = 0; k < bins_; ++k) {
                const std::size_t idx = static_cast<std::size_t>(ch) * bins_ + k;
                if (!initialized_ || transient) {
                    output_phase_[idx] = phase_[idx];
                } else {
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
            }
            auto* work = fft_work_.data() + static_cast<std::size_t>(ch) * n_fft_;
            for (std::uint32_t k = 0; k < bins_; ++k) {
                const std::size_t idx = static_cast<std::size_t>(ch) * bins_ + k;
                work[k] = std::polar(magnitude_[idx] * formant_gain_[k], output_phase_[idx]);
            }
            for (std::uint32_t k = bins_; k < n_fft_; ++k) work[k] = std::conj(work[n_fft_ - k]);
            transform(work, true);
            for (std::uint32_t n = 0; n < n_fft_; ++n) {
                const std::uint64_t absolute = synth_start + n;
                const std::size_t slot = static_cast<std::size_t>(absolute % ola_capacity_);
                ola_[static_cast<std::size_t>(ch) * ola_capacity_ + slot] += work[n].real() * window_[n];
            }
        }
        for (std::uint32_t n = 0; n < n_fft_; ++n) {
            const std::size_t slot = static_cast<std::size_t>((synth_start + n) % ola_capacity_);
            weight_[slot] += window_[n] * window_[n];
        }
        latest_safe_position_ = synth_start;
        drain_safe(flushed_);
        process_resampler(false);
        previous_phase_ = phase_;
        previous_output_phase_ = output_phase_;
        previous_linked_magnitude_ = linked_magnitude_;
        if (initialized_) {
            constexpr float alpha = 0.04F;
            const float difference = flux - flux_mean_;
            flux_mean_ += alpha * difference;
            flux_variance_ = (1.0F - alpha) * (flux_variance_ + alpha * difference * difference);
        } else {
            flux_mean_ = flux;
            flux_variance_ = 0.0F;
            initialized_ = true;
        }
        previous_synth_start_ = synth_start;
        synthesis_position_ += static_cast<double>(analysis_hop_) * internal_stretch();
        analysis_start_ += analysis_hop_;
    }

    [[nodiscard]] std::uint64_t pv_count() const noexcept { return pv_write_ - pv_start_; }
    [[nodiscard]] std::uint64_t pv_free() const noexcept { return pv_capacity_ - pv_count(); }
    float pv_get(std::uint32_t ch, std::int64_t index) const noexcept {
        if (index < 0) return 0.0F;
        const auto u = static_cast<std::uint64_t>(index);
        if (u < pv_start_ || u >= pv_write_) return 0.0F;
        return pv_fifo_[static_cast<std::size_t>(ch) * pv_capacity_ + static_cast<std::size_t>(u % pv_capacity_)];
    }
    void pv_discard_before(std::uint64_t index) noexcept { pv_start_ = std::min(std::max(pv_start_, index), pv_write_); }

    void drain_safe(bool finalizing) noexcept {
        const std::uint64_t max_emit = finalizing ? target_pv_frames_
            : static_cast<std::uint64_t>(std::floor(std::max(0.0, expected_pv_frames_)));
        const std::uint64_t timeline_limit = startup_crop_ + max_emit;
        const std::uint64_t target = std::min(latest_safe_position_, timeline_limit);
        std::uint32_t budget=(scheduled_ && !flushed_)?8U:std::numeric_limits<std::uint32_t>::max();
        while (cleanup_position_ < target && budget--) {
            const std::size_t slot = static_cast<std::size_t>(cleanup_position_ % ola_capacity_);
            if (cleanup_position_ >= startup_crop_) {
                if (pv_free() == 0U) {
                    process_resampler(false);
                    if (pv_free() == 0U) return;
                }
                const float norm = weight_[slot] > 1.0e-9F ? 1.0F / weight_[slot] : 0.0F;
                const std::size_t pv_slot = static_cast<std::size_t>(pv_write_ % pv_capacity_);
                for (std::uint32_t ch = 0; ch < channels_; ++ch)
                    pv_fifo_[static_cast<std::size_t>(ch) * pv_capacity_ + pv_slot] = ola_[static_cast<std::size_t>(ch) * ola_capacity_ + slot] * norm;
                ++pv_write_;
                ++pv_emitted_frames_;
            }
            for (std::uint32_t ch = 0; ch < channels_; ++ch)
                ola_[static_cast<std::size_t>(ch) * ola_capacity_ + slot] = 0.0F;
            weight_[slot] = 0.0F;
            ++cleanup_position_;
        }
    }

    void push_final_frame(const float* values) noexcept {
        if (fifo_count_ >= fifo_capacity_ || emitted_frames_ >= target_output_frames_) return;
        const std::size_t slot = static_cast<std::size_t>(fifo_write_ % fifo_capacity_);
        for (std::uint32_t ch = 0; ch < channels_; ++ch)
            fifo_[static_cast<std::size_t>(ch) * fifo_capacity_ + slot] = values[ch];
        fifo_write_ = (fifo_write_ + 1U) % fifo_capacity_;
        ++fifo_count_;
        ++emitted_frames_;
    }

    void process_resampler(bool finalizing) noexcept {
        if (fifo_count_ >= fifo_capacity_) return;
        const std::uint64_t output_limit = finalizing ? target_output_frames_
            : static_cast<std::uint64_t>(std::floor(std::max(0.0, expected_output_frames_)));
        std::uint32_t budget=(scheduled_ && !flushed_)?2U:std::numeric_limits<std::uint32_t>::max();
        if (std::abs(pitch_ratio_ - 1.0F) < 1.0e-7F) {
            while (pv_start_ < pv_write_ && emitted_frames_ < output_limit && fifo_count_ < fifo_capacity_ && budget--) {
                const std::size_t source_slot = static_cast<std::size_t>(pv_start_ % pv_capacity_);
                const std::size_t dst_slot = static_cast<std::size_t>(fifo_write_ % fifo_capacity_);
                for (std::uint32_t ch = 0; ch < channels_; ++ch)
                    fifo_[static_cast<std::size_t>(ch) * fifo_capacity_ + dst_slot] = pv_fifo_[static_cast<std::size_t>(ch) * pv_capacity_ + source_slot];
                ++pv_start_;
                resample_pos_ = static_cast<double>(pv_start_);
                fifo_write_ = (fifo_write_ + 1U) % fifo_capacity_;
                ++fifo_count_;
                ++emitted_frames_;
            }
            return;
        }

        const auto& bank = kernels();
        const double desired_cutoff = 0.94 * std::min(1.0, 1.0 / static_cast<double>(pitch_ratio_));
        const int cutoff_index = resampler_kernel_bank::cutoff_index(desired_cutoff);
        while (emitted_frames_ < output_limit && fifo_count_ < fifo_capacity_ && budget--) {
            const std::int64_t center = static_cast<std::int64_t>(std::floor(resample_pos_));
            if (!finalizing && center + k_resampler_half + 1 >= static_cast<std::int64_t>(pv_write_)) break;
            if (finalizing && center - k_resampler_half > static_cast<std::int64_t>(pv_write_) + k_resampler_half) break;
            const double frac = resample_pos_ - static_cast<double>(center);
            const int phase = std::clamp(static_cast<int>(std::lround(frac * resampler_kernel_bank::phases)), 0, resampler_kernel_bank::phases - 1);
            const float* kernel = bank.data(cutoff_index, phase);
            float samples[8]{};
            for (std::uint32_t ch = 0; ch < channels_; ++ch) {
                double sum = 0.0;
                for (int tap = 0; tap < k_resampler_taps; ++tap) {
                    const int offset = tap - (k_resampler_half - 1);
                    sum += static_cast<double>(pv_get(ch, center + offset)) * kernel[tap];
                }
                samples[ch] = static_cast<float>(sum);
            }
            push_final_frame(samples);
            resample_pos_ += static_cast<double>(pitch_ratio_);
            const std::int64_t keep = static_cast<std::int64_t>(std::floor(resample_pos_)) - k_resampler_half - 2;
            if (keep > 0) pv_discard_before(static_cast<std::uint64_t>(keep));
        }
    }

#include "pv_execution.inc"
public:
    boiledegg_research_execution_stats stats() const noexcept {
        return {sizeof(boiledegg_research_execution_stats),steps_per_input_,completed_frames_,frame_overruns_,max_frame_steps_};
    }
private:
    bool scheduled_{}, simd_{}, frame_active_{};
    std::uint32_t steps_per_input_{};
    std::uint64_t completed_frames_{},frame_overruns_{},max_frame_steps_{},current_steps_{};
    float frame_formant_target_{1.0F};
    fft_plan::cursor fft_cursor_{};
    work_sequence frame_task_,formant_task_,peaks_task_;
    std::uint32_t sample_rate_{}, channels_{}, max_block_{}, n_fft_{}, bins_{}, analysis_hop_{};
    boiledegg_research_pv_rt_mode mode_{};
    boiledegg_research_pv_rt_formant_mode formant_mode_{};
    float time_ratio_{}, pitch_ratio_{};
    std::uint32_t timing_policy_{};
    float formant_ratio_{1.0F}, smoothed_formant_ratio_{1.0F}, formant_smoothing_{};
    float transient_floor_{}, transient_sigma_{};
    std::uint32_t formant_cepstral_order_{};
    float formant_gain_limit_db_{}, monophonic_min_f0_hz_{}, monophonic_max_f0_hz_{};
    fft_plan fft_;
    std::size_t input_capacity_{}, ola_capacity_{}, pv_capacity_{}, fifo_capacity_{};
    std::vector<float> input_, ola_, weight_, pv_fifo_, fifo_, window_, omega_, magnitude_, phase_, previous_phase_, previous_output_phase_, output_phase_, linked_magnitude_, previous_linked_magnitude_;
    std::vector<std::complex<float>> fft_work_, envelope_work_;
    std::vector<float> log_envelope_, formant_gain_;
    std::vector<std::uint32_t> peaks_, owners_;
    fuzzy_phase fuzzy_;
    std::uint32_t peak_count_{};
    std::uint64_t input_write_{}, analysis_start_{}, previous_synth_start_{}, latest_safe_position_{}, cleanup_position_{}, startup_crop_{}, real_input_frames_{}, pv_emitted_frames_{}, emitted_frames_{};
    double synthesis_position_{}, expected_pv_frames_{}, expected_output_frames_{}, resample_pos_{};
    std::uint64_t pv_start_{}, pv_write_{}, fifo_read_{}, fifo_write_{}, fifo_count_{}, target_pv_frames_{}, target_output_frames_{};
    bool initialized_{}, flushed_{};
    float flux_mean_{}, flux_variance_{};
    float formant_energy_compensation_{1.0F};
};

} // namespace boiled_egg::research::detail

struct boiledegg_research_pv_rt_handle { boiled_egg::research::detail::engine* engine{}; };

extern "C" {
boiledegg_research_pv_rt_config boiledegg_research_pv_rt_default_config(uint32_t sample_rate, uint32_t channels, uint32_t max_block_frames) {
    boiledegg_research_pv_rt_config c{};
    c.struct_size = sizeof(c);
    c.abi_version = BOILEDEGG_RESEARCH_PV_RT_ABI_VERSION;
    c.sample_rate = sample_rate;
    c.channels = channels;
    c.max_block_frames = max_block_frames;
    c.fft_size = 2048;
    c.analysis_hop = 256;
    c.mode = BOILEDEGG_RESEARCH_PV_RT_PHASE_LOCKED;
    c.initial_time_ratio = 1.0F;
    c.initial_pitch_ratio = 1.0F;
    c.transient_floor = 0.12F;
    c.transient_sigma = 2.5F;
    c.formant_mode = BOILEDEGG_RESEARCH_PV_RT_FORMANT_OFF;
    c.formant_cepstral_order = 40U;
    c.formant_gain_limit_db = 15.0F;
    c.monophonic_min_f0_hz = 60.0F;
    c.monophonic_max_f0_hz = 900.0F;
    return c;
}
boiledegg_research_pv_rt_handle* boiledegg_research_pv_rt_create(const boiledegg_research_pv_rt_config* config, boiledegg_research_pv_rt_result* result) {
    const auto features = boiledegg_research_default_features();
    return boiledegg_research_pv_rt_create_ex(config, &features, result);
}
boiledegg_research_features boiledegg_research_default_features(void) {
    return {sizeof(boiledegg_research_features), BOILEDEGG_RESEARCH_FEATURES_VERSION,
            BOILEDEGG_RESEARCH_TIMING_LEGACY, BOILEDEGG_RESEARCH_RATE_FIXED, 1.0F};
}
boiledegg_research_pv_rt_handle* boiledegg_research_pv_rt_create_ex(
    const boiledegg_research_pv_rt_config* config, const boiledegg_research_features* features,
    boiledegg_research_pv_rt_result* result) {
    const auto execution=boiledegg_research_default_execution();
    return boiledegg_research_pv_rt_create_exec(config,features,&execution,result);
}
boiledegg_research_execution boiledegg_research_default_execution(void) {
    return {sizeof(boiledegg_research_execution),BOILEDEGG_RESEARCH_EXECUTION_VERSION,0,0};
}
uint32_t boiledegg_research_simd_available(void) { return boiled_egg::research::detail::fft_plan::simd_available(); }
boiledegg_research_pv_rt_result boiledegg_research_pv_rt_execution_stats(
    const boiledegg_research_pv_rt_handle* h, boiledegg_research_execution_stats* stats) {
    if (!h || !h->engine || !stats || stats->struct_size<sizeof(*stats)) return BOILEDEGG_RESEARCH_PV_RT_INVALID_ARGUMENT;
    *stats=h->engine->stats(); return BOILEDEGG_RESEARCH_PV_RT_OK;
}
boiledegg_research_pv_rt_handle* boiledegg_research_pv_rt_create_exec(
    const boiledegg_research_pv_rt_config* config, const boiledegg_research_features* features,
    const boiledegg_research_execution* execution, boiledegg_research_pv_rt_result* result) {
    if (result) *result = BOILEDEGG_RESEARCH_PV_RT_INVALID_CONFIG;
    if (!config || config->struct_size < sizeof(*config) || !boiled_egg::research::features::valid(features, config->formant_mode)) return nullptr;
    if (!boiled_egg::research::execution::valid(execution,config->initial_time_ratio,config->initial_pitch_ratio) ||
        (execution->scheduled && config->analysis_hop<64U)) return nullptr;
    auto scaled = *config;
    if (!boiled_egg::research::detail::engine::valid(scaled) ||
        !boiled_egg::research::features::scale_pv(scaled, *features) ||
        !boiled_egg::research::detail::engine::valid(scaled)) {
        if (result) *result = BOILEDEGG_RESEARCH_PV_RT_INVALID_CONFIG;
        return nullptr;
    }
    try {
        auto* h = new boiledegg_research_pv_rt_handle;
        try { h->engine = new boiled_egg::research::detail::engine(scaled, *features, *execution); }
        catch (...) { delete h; throw; }
        if (result) *result = BOILEDEGG_RESEARCH_PV_RT_OK;
        return h;
    } catch (const std::bad_alloc&) {
        if (result) *result = BOILEDEGG_RESEARCH_PV_RT_OUT_OF_MEMORY;
        return nullptr;
    } catch (...) {
        if (result) *result = BOILEDEGG_RESEARCH_PV_RT_INTERNAL_ERROR;
        return nullptr;
    }
}
boiledegg_research_pv_rt_result boiledegg_research_pv_rt_set_formant_ratio(boiledegg_research_pv_rt_handle* h, float ratio) { return (!h || !h->engine) ? BOILEDEGG_RESEARCH_PV_RT_INVALID_ARGUMENT : h->engine->set_formant_ratio(ratio); }
float boiledegg_research_pv_rt_get_formant_ratio(const boiledegg_research_pv_rt_handle* h) { return (!h || !h->engine) ? 0.0F : h->engine->formant_ratio(); }
void boiledegg_research_pv_rt_destroy(boiledegg_research_pv_rt_handle* h) { if (h) { delete h->engine; delete h; } }
boiledegg_research_pv_rt_result boiledegg_research_pv_rt_reset(boiledegg_research_pv_rt_handle* h) { if (!h || !h->engine) return BOILEDEGG_RESEARCH_PV_RT_INVALID_ARGUMENT; h->engine->reset(); return BOILEDEGG_RESEARCH_PV_RT_OK; }
boiledegg_research_pv_rt_result boiledegg_research_pv_rt_set_time_ratio(boiledegg_research_pv_rt_handle* h, float ratio) { return (!h || !h->engine) ? BOILEDEGG_RESEARCH_PV_RT_INVALID_ARGUMENT : h->engine->set_time_ratio(ratio); }
float boiledegg_research_pv_rt_get_time_ratio(const boiledegg_research_pv_rt_handle* h) { return (!h || !h->engine) ? 0.0F : h->engine->time_ratio(); }
boiledegg_research_pv_rt_result boiledegg_research_pv_rt_set_pitch_ratio(boiledegg_research_pv_rt_handle* h, float ratio) { return (!h || !h->engine) ? BOILEDEGG_RESEARCH_PV_RT_INVALID_ARGUMENT : h->engine->set_pitch_ratio(ratio); }
float boiledegg_research_pv_rt_get_pitch_ratio(const boiledegg_research_pv_rt_handle* h) { return (!h || !h->engine) ? 0.0F : h->engine->pitch_ratio(); }
boiledegg_research_pv_rt_result boiledegg_research_pv_rt_push(boiledegg_research_pv_rt_handle* h, const float* const* input, uint32_t frames) { return (!h || !h->engine) ? BOILEDEGG_RESEARCH_PV_RT_INVALID_ARGUMENT : h->engine->push(input, frames); }
uint32_t boiledegg_research_pv_rt_available(const boiledegg_research_pv_rt_handle* h) { return (!h || !h->engine) ? 0U : h->engine->available(); }
uint32_t boiledegg_research_pv_rt_pull(boiledegg_research_pv_rt_handle* h, float* const* output, uint32_t capacity) { return (!h || !h->engine) ? 0U : h->engine->pull(output, capacity); }
boiledegg_research_pv_rt_result boiledegg_research_pv_rt_flush(boiledegg_research_pv_rt_handle* h) { return (!h || !h->engine) ? BOILEDEGG_RESEARCH_PV_RT_INVALID_ARGUMENT : h->engine->flush(); }
uint32_t boiledegg_research_pv_rt_latency_frames(const boiledegg_research_pv_rt_handle* h) { return (!h || !h->engine) ? 0U : h->engine->latency(); }
uint64_t boiledegg_research_pv_rt_input_frames(const boiledegg_research_pv_rt_handle* h) { return (!h || !h->engine) ? 0U : h->engine->input_frames(); }
uint64_t boiledegg_research_pv_rt_output_frames(const boiledegg_research_pv_rt_handle* h) { return (!h || !h->engine) ? 0U : h->engine->output_frames(); }
const char* boiledegg_research_pv_rt_result_string(boiledegg_research_pv_rt_result r) {
    switch (r) {
        case BOILEDEGG_RESEARCH_PV_RT_OK: return "ok";
        case BOILEDEGG_RESEARCH_PV_RT_INVALID_ARGUMENT: return "invalid argument";
        case BOILEDEGG_RESEARCH_PV_RT_INVALID_CONFIG: return "invalid config";
        case BOILEDEGG_RESEARCH_PV_RT_OUT_OF_MEMORY: return "out of memory";
        case BOILEDEGG_RESEARCH_PV_RT_FIFO_OVERFLOW: return "output FIFO overflow";
        case BOILEDEGG_RESEARCH_PV_RT_ALREADY_FLUSHED: return "already flushed";
        default: return "internal error";
    }
}
}
