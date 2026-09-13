#include "boiled_egg_multires_rt.h"
#include "research_features.hpp"

#include <algorithm>
#include <cmath>
#include <cstddef>
#include <cstdint>
#include <limits>
#include <new>
#include <numbers>
#include <vector>

namespace boiled_egg::research::multires_detail {
namespace {
constexpr float k_min_ratio = 0.25F;
constexpr float k_max_ratio = 4.0F;
constexpr double k_kaiser_beta = 8.0;

bool finite_ratio(float value) noexcept {
    return std::isfinite(value) && value >= k_min_ratio && value <= k_max_ratio;
}

std::size_t next_capacity(std::size_t value) noexcept {
    std::size_t result = 1U;
    while (result < value) result <<= 1U;
    return result;
}

double sinc_pi(double x) noexcept {
    if (std::abs(x) < 1.0e-14) return 1.0;
    const double p = std::numbers::pi_v<double> * x;
    return std::sin(p) / p;
}

// Numerical Recipes-style I0 approximation. Accuracy is more than sufficient
// for construction-time Kaiser window generation and avoids platform-specific
// special-function dependencies.
double bessel_i0(double x) noexcept {
    const double ax = std::abs(x);
    if (ax < 3.75) {
        const double y = x / 3.75;
        const double y2 = y * y;
        return 1.0 + y2 * (3.5156229 + y2 * (3.0899424 + y2 * (1.2067492
            + y2 * (0.2659732 + y2 * (0.0360768 + y2 * 0.0045813)))));
    }
    const double y = 3.75 / ax;
    return (std::exp(ax) / std::sqrt(ax)) * (0.39894228 + y * (0.01328592
        + y * (0.00225319 + y * (-0.00157565 + y * (0.00916281
        + y * (-0.02057706 + y * (0.02635537 + y * (-0.01647633
        + y * 0.00392377))))))));
}

} // namespace

class ring_buffer {
public:
    ring_buffer(std::uint32_t channels, std::size_t capacity)
        : channels_(channels), capacity_(capacity), data_(static_cast<std::size_t>(channels) * capacity, 0.0F) {}

    void reset() noexcept {
        std::fill(data_.begin(), data_.end(), 0.0F);
        read_ = 0U;
        write_ = 0U;
        count_ = 0U;
    }

    [[nodiscard]] std::size_t count() const noexcept { return count_; }
    [[nodiscard]] std::size_t free() const noexcept { return capacity_ - count_; }

    bool push_planar(float* const* source, std::uint32_t frames) noexcept {
        if (frames > free()) return false;
        for (std::uint32_t frame = 0U; frame < frames; ++frame) {
            const std::size_t slot = (write_ + frame) % capacity_;
            for (std::uint32_t channel = 0U; channel < channels_; ++channel) {
                data_[static_cast<std::size_t>(channel) * capacity_ + slot] = source[channel][frame];
            }
        }
        write_ = (write_ + frames) % capacity_;
        count_ += frames;
        return true;
    }

    bool pop_frame(float* destination) noexcept {
        if (count_ == 0U) return false;
        for (std::uint32_t channel = 0U; channel < channels_; ++channel) {
            destination[channel] = data_[static_cast<std::size_t>(channel) * capacity_ + read_];
        }
        read_ = (read_ + 1U) % capacity_;
        --count_;
        return true;
    }

    std::uint32_t pull_planar(float* const* destination, std::uint32_t capacity_frames) noexcept {
        const auto frames = static_cast<std::uint32_t>(std::min<std::size_t>(capacity_frames, count_));
        for (std::uint32_t frame = 0U; frame < frames; ++frame) {
            const std::size_t slot = (read_ + frame) % capacity_;
            for (std::uint32_t channel = 0U; channel < channels_; ++channel) {
                destination[channel][frame] = data_[static_cast<std::size_t>(channel) * capacity_ + slot];
            }
        }
        read_ = (read_ + frames) % capacity_;
        count_ -= frames;
        return frames;
    }

    bool push_frame(const float* source) noexcept {
        if (count_ == capacity_) return false;
        for (std::uint32_t channel = 0U; channel < channels_; ++channel) {
            data_[static_cast<std::size_t>(channel) * capacity_ + write_] = source[channel];
        }
        write_ = (write_ + 1U) % capacity_;
        ++count_;
        return true;
    }

private:
    std::uint32_t channels_{};
    std::size_t capacity_{};
    std::vector<float> data_;
    std::size_t read_{}, write_{}, count_{};
};

class engine {
public:
    explicit engine(const boiledegg_research_multires_rt_config& config, const boiledegg_research_features& features)
        : sample_rate_(config.sample_rate), channels_(config.channels), max_block_(config.max_block_frames),
          crossover_hz_(config.crossover_hz), fir_taps_(config.fir_taps), fir_half_(fir_taps_ / 2U),
          time_ratio_(config.initial_time_ratio), pitch_ratio_(config.initial_pitch_ratio),
          branch_capacity_(next_capacity(std::max<std::size_t>(65536U,
              static_cast<std::size_t>(max_block_) * 128U + 8192U))),
          output_capacity_(branch_capacity_), scratch_frames_(std::max<std::uint32_t>(8192U, max_block_ * 16U)),
          low_queue_(channels_, branch_capacity_), high_queue_(channels_, branch_capacity_),
          output_queue_(channels_, output_capacity_),
          low_scratch_(static_cast<std::size_t>(channels_) * scratch_frames_, 0.0F),
          high_scratch_(static_cast<std::size_t>(channels_) * scratch_frames_, 0.0F),
          low_ptrs_(channels_), high_ptrs_(channels_),
          low_frame_(channels_, 0.0F), high_frame_(channels_, 0.0F), output_frame_(channels_, 0.0F),
          lowpass_(fir_taps_, 0.0F),
          diff_history_(static_cast<std::size_t>(channels_) * fir_taps_, 0.0F),
          high_history_(static_cast<std::size_t>(channels_) * fir_taps_, 0.0F) {
        for (std::uint32_t channel = 0U; channel < channels_; ++channel) {
            low_ptrs_[channel] = low_scratch_.data() + static_cast<std::size_t>(channel) * scratch_frames_;
            high_ptrs_[channel] = high_scratch_.data() + static_cast<std::size_t>(channel) * scratch_frames_;
        }
        build_filter();
        create_children(config, features);
        reset_local();
    }

    ~engine() {
        boiledegg_research_pv_rt_destroy(low_);
        boiledegg_research_pv_rt_destroy(high_);
    }

    engine(const engine&) = delete;
    engine& operator=(const engine&) = delete;

    static bool valid(const boiledegg_research_multires_rt_config& config) noexcept {
        return config.struct_size >= sizeof(boiledegg_research_multires_rt_config)
            && config.abi_version == BOILEDEGG_RESEARCH_MULTIRES_RT_ABI_VERSION
            && config.sample_rate >= 8000U && config.sample_rate <= 384000U
            && config.channels >= 1U && config.channels <= 8U
            && config.max_block_frames >= 1U && config.max_block_frames <= 16384U
            && finite_ratio(config.initial_time_ratio) && finite_ratio(config.initial_pitch_ratio)
            && config.formant_mode <= BOILEDEGG_RESEARCH_PV_RT_FORMANT_MONOPHONIC
            && config.formant_cepstral_order >= 4U && config.formant_cepstral_order < 256U
            && std::isfinite(config.formant_gain_limit_db) && config.formant_gain_limit_db >= 0.0F
            && config.formant_gain_limit_db <= 36.0F
            && std::isfinite(config.monophonic_min_f0_hz) && std::isfinite(config.monophonic_max_f0_hz)
            && config.monophonic_min_f0_hz >= 40.0F
            && config.monophonic_max_f0_hz > config.monophonic_min_f0_hz
            && config.monophonic_max_f0_hz <= 2000.0F
            && std::isfinite(config.crossover_hz) && config.crossover_hz > 1000.0F
            && config.crossover_hz < 0.45F * static_cast<float>(config.sample_rate)
            && config.fir_taps >= 33U && config.fir_taps <= 513U && (config.fir_taps & 1U) != 0U;
    }

    boiledegg_research_pv_rt_result reset() noexcept {
        auto result = boiledegg_research_pv_rt_reset(low_);
        if (result != BOILEDEGG_RESEARCH_PV_RT_OK) return result;
        result = boiledegg_research_pv_rt_reset(high_);
        if (result != BOILEDEGG_RESEARCH_PV_RT_OK) return result;
        reset_local();
        return BOILEDEGG_RESEARCH_PV_RT_OK;
    }

    boiledegg_research_pv_rt_result set_time_ratio(float value) noexcept {
        if (!finite_ratio(value) || flushed_) {
            return flushed_ ? BOILEDEGG_RESEARCH_PV_RT_ALREADY_FLUSHED : BOILEDEGG_RESEARCH_PV_RT_INVALID_ARGUMENT;
        }
        auto result = boiledegg_research_pv_rt_set_time_ratio(low_, value);
        if (result != BOILEDEGG_RESEARCH_PV_RT_OK) return result;
        result = boiledegg_research_pv_rt_set_time_ratio(high_, value);
        if (result != BOILEDEGG_RESEARCH_PV_RT_OK) return result;
        time_ratio_ = value;
        return pump(false);
    }

    boiledegg_research_pv_rt_result set_pitch_ratio(float value) noexcept {
        if (!finite_ratio(value) || flushed_) {
            return flushed_ ? BOILEDEGG_RESEARCH_PV_RT_ALREADY_FLUSHED : BOILEDEGG_RESEARCH_PV_RT_INVALID_ARGUMENT;
        }
        auto result = boiledegg_research_pv_rt_set_pitch_ratio(low_, value);
        if (result != BOILEDEGG_RESEARCH_PV_RT_OK) return result;
        result = boiledegg_research_pv_rt_set_pitch_ratio(high_, value);
        if (result != BOILEDEGG_RESEARCH_PV_RT_OK) return result;
        pitch_ratio_ = value;
        return pump(false);
    }

    boiledegg_research_pv_rt_result set_formant_ratio(float value) noexcept {
        auto result = boiledegg_research_pv_rt_set_formant_ratio(low_, value);
        if (result != BOILEDEGG_RESEARCH_PV_RT_OK) return result;
        return boiledegg_research_pv_rt_set_formant_ratio(high_, value);
    }
    [[nodiscard]] float formant_ratio() const noexcept {
        return boiledegg_research_pv_rt_get_formant_ratio(low_);
    }
    boiledegg_research_pv_rt_result push(const float* const* input, std::uint32_t frames) noexcept {
        if (flushed_) return BOILEDEGG_RESEARCH_PV_RT_ALREADY_FLUSHED;
        auto result = pump(false);
        if (result != BOILEDEGG_RESEARCH_PV_RT_OK) return result;
        result = boiledegg_research_pv_rt_push(low_, input, frames);
        if (result != BOILEDEGG_RESEARCH_PV_RT_OK) return result;
        result = boiledegg_research_pv_rt_push(high_, input, frames);
        if (result != BOILEDEGG_RESEARCH_PV_RT_OK) return result;
        input_frames_ += frames;
        return pump(false);
    }

    boiledegg_research_pv_rt_result flush() noexcept {
        if (flushed_) return BOILEDEGG_RESEARCH_PV_RT_ALREADY_FLUSHED;
        auto result = pump(false);
        if (result != BOILEDEGG_RESEARCH_PV_RT_OK) return result;
        result = boiledegg_research_pv_rt_flush(low_);
        if (result != BOILEDEGG_RESEARCH_PV_RT_OK) return result;
        result = boiledegg_research_pv_rt_flush(high_);
        if (result != BOILEDEGG_RESEARCH_PV_RT_OK) return result;
        flushed_ = true;
        result = pump(true);
        if (result != BOILEDEGG_RESEARCH_PV_RT_OK) return result;

        // Both child engines have exact-duration contracts. At finalization all
        // branch samples must be paired before the FIR tail is generated.
        if (low_queue_.count() != 0U || high_queue_.count() != 0U) {
            return BOILEDEGG_RESEARCH_PV_RT_INTERNAL_ERROR;
        }
        if (boiledegg_research_pv_rt_output_frames(low_) != boiledegg_research_pv_rt_output_frames(high_)) {
            return BOILEDEGG_RESEARCH_PV_RT_INTERNAL_ERROR;
        }

        for (std::uint32_t i = 0U; i < fir_half_; ++i) {
            std::fill(low_frame_.begin(), low_frame_.end(), 0.0F);
            std::fill(high_frame_.begin(), high_frame_.end(), 0.0F);
            if (!filter_pair(low_frame_.data(), high_frame_.data())) {
                return BOILEDEGG_RESEARCH_PV_RT_FIFO_OVERFLOW;
            }
        }
        const auto expected = boiledegg_research_pv_rt_output_frames(low_);
        return output_frames_ == expected ? BOILEDEGG_RESEARCH_PV_RT_OK
                                          : BOILEDEGG_RESEARCH_PV_RT_INTERNAL_ERROR;
    }

    std::uint32_t pull(float* const* output, std::uint32_t capacity_frames) noexcept {
        if (capacity_frames != 0U && output == nullptr) return 0U;
        for (std::uint32_t channel = 0U; channel < channels_; ++channel) {
            if (capacity_frames != 0U && output[channel] == nullptr) return 0U;
        }
        (void)pump(flushed_);
        const auto pulled = output_queue_.pull_planar(output, capacity_frames);
        (void)pump(flushed_);
        return pulled;
    }

    [[nodiscard]] std::uint32_t available() const noexcept {
        return static_cast<std::uint32_t>(std::min<std::size_t>(output_queue_.count(),
            std::numeric_limits<std::uint32_t>::max()));
    }
    [[nodiscard]] float time_ratio() const noexcept { return time_ratio_; }
    [[nodiscard]] float pitch_ratio() const noexcept { return pitch_ratio_; }
    [[nodiscard]] std::uint64_t input_frames() const noexcept { return input_frames_; }
    [[nodiscard]] std::uint64_t output_frames() const noexcept { return output_frames_; }
    [[nodiscard]] std::uint32_t latency() const noexcept {
        const auto child = std::max(boiledegg_research_pv_rt_latency_frames(low_),
                                    boiledegg_research_pv_rt_latency_frames(high_));
        const auto total = static_cast<std::uint64_t>(child) + fir_half_;
        return static_cast<std::uint32_t>(std::min<std::uint64_t>(total, std::numeric_limits<std::uint32_t>::max()));
    }

private:
    void create_children(const boiledegg_research_multires_rt_config& config, const boiledegg_research_features& features) {
        auto base = boiledegg_research_pv_rt_default_config(config.sample_rate, config.channels, config.max_block_frames);
        base.initial_time_ratio = config.initial_time_ratio;
        base.initial_pitch_ratio = config.initial_pitch_ratio;
        base.formant_mode = config.formant_mode;
        base.formant_cepstral_order = config.formant_cepstral_order;
        base.formant_gain_limit_db = config.formant_gain_limit_db;
        base.monophonic_min_f0_hz = config.monophonic_min_f0_hz;
        base.monophonic_max_f0_hz = config.monophonic_max_f0_hz;
        base.mode = BOILEDEGG_RESEARCH_PV_RT_PHASE_LOCKED;

        auto low_config = base;
        low_config.fft_size = 1024U;
        low_config.analysis_hop = 256U;
        boiledegg_research_pv_rt_result result{};
        low_ = boiledegg_research_pv_rt_create_ex(&low_config, &features, &result);
        if (low_ == nullptr) throw result;

        auto high_config = base;
        high_config.fft_size = 512U;
        high_config.analysis_hop = 192U;
        high_ = boiledegg_research_pv_rt_create_ex(&high_config, &features, &result);
        if (high_ == nullptr) {
            boiledegg_research_pv_rt_destroy(low_);
            low_ = nullptr;
            throw result;
        }
    }

    void build_filter() noexcept {
        const auto midpoint = static_cast<std::int64_t>(fir_half_);
        const double cutoff = static_cast<double>(crossover_hz_) / static_cast<double>(sample_rate_);
        const double beta_denominator = bessel_i0(k_kaiser_beta);
        double sum = 0.0;
        for (std::uint32_t tap = 0U; tap < fir_taps_; ++tap) {
            const auto offset = static_cast<std::int64_t>(tap) - midpoint;
            const double ideal = 2.0 * cutoff * sinc_pi(2.0 * cutoff * static_cast<double>(offset));
            const double position = fir_taps_ > 1U ? (2.0 * static_cast<double>(tap) / static_cast<double>(fir_taps_ - 1U) - 1.0) : 0.0;
            const double window = bessel_i0(k_kaiser_beta * std::sqrt(std::max(0.0, 1.0 - position * position))) / beta_denominator;
            lowpass_[tap] = static_cast<float>(ideal * window);
            sum += lowpass_[tap];
        }
        if (std::abs(sum) > 1.0e-15) {
            const float normalizer = static_cast<float>(1.0 / sum);
            for (float& value : lowpass_) value *= normalizer;
        }
    }

    void reset_local() noexcept {
        low_queue_.reset();
        high_queue_.reset();
        output_queue_.reset();
        std::fill(diff_history_.begin(), diff_history_.end(), 0.0F);
        std::fill(high_history_.begin(), high_history_.end(), 0.0F);
        history_position_ = 0U;
        raw_pairs_ = 0U;
        output_frames_ = 0U;
        input_frames_ = 0U;
        flushed_ = false;
    }

    boiledegg_research_pv_rt_result drain_child(
        boiledegg_research_pv_rt_handle* handle,
        ring_buffer& queue,
        std::vector<float*>& pointers) noexcept {
        while (boiledegg_research_pv_rt_available(handle) != 0U) {
            if (queue.free() == 0U) return BOILEDEGG_RESEARCH_PV_RT_FIFO_OVERFLOW;
            const auto capacity = static_cast<std::uint32_t>(std::min<std::size_t>(scratch_frames_, queue.free()));
            const auto pulled = boiledegg_research_pv_rt_pull(handle, pointers.data(), capacity);
            if (pulled == 0U) break;
            if (!queue.push_planar(pointers.data(), pulled)) return BOILEDEGG_RESEARCH_PV_RT_FIFO_OVERFLOW;
        }
        return BOILEDEGG_RESEARCH_PV_RT_OK;
    }

    bool filter_pair(const float* low, const float* high) noexcept {
        const std::size_t position = history_position_;
        for (std::uint32_t channel = 0U; channel < channels_; ++channel) {
            const std::size_t base = static_cast<std::size_t>(channel) * fir_taps_;
            diff_history_[base + position] = low[channel] - high[channel];
            high_history_[base + position] = high[channel];
        }

        if (raw_pairs_ >= fir_half_) {
            for (std::uint32_t channel = 0U; channel < channels_; ++channel) {
                const std::size_t base = static_cast<std::size_t>(channel) * fir_taps_;
                double lowpass_difference = 0.0;
                // Two reverse contiguous spans replace a variable integer
                // remainder for every tap. Preserve tap/accumulation order
                // exactly; this is not a reordered or symmetric FIR sum.
                std::uint32_t tap = 0U;
                for (std::size_t slot = position + 1U; slot != 0U; --slot, ++tap)
                    lowpass_difference += static_cast<double>(lowpass_[tap]) * diff_history_[base + slot - 1U];
                for (std::size_t slot = fir_taps_; tap < fir_taps_; --slot, ++tap)
                    lowpass_difference += static_cast<double>(lowpass_[tap]) * diff_history_[base + slot - 1U];
                const std::size_t delayed = (position + fir_taps_ - fir_half_) % fir_taps_;
                output_frame_[channel] = high_history_[base + delayed] + static_cast<float>(lowpass_difference);
            }
            if (!output_queue_.push_frame(output_frame_.data())) return false;
            ++output_frames_;
        }

        history_position_ = (position + 1U) % fir_taps_;
        ++raw_pairs_;
        return true;
    }

    boiledegg_research_pv_rt_result pump(bool finalizing) noexcept {
        auto result = drain_child(low_, low_queue_, low_ptrs_);
        if (result != BOILEDEGG_RESEARCH_PV_RT_OK) return result;
        result = drain_child(high_, high_queue_, high_ptrs_);
        if (result != BOILEDEGG_RESEARCH_PV_RT_OK) return result;

        while (low_queue_.count() != 0U && high_queue_.count() != 0U) {
            if (output_queue_.free() == 0U) return BOILEDEGG_RESEARCH_PV_RT_FIFO_OVERFLOW;
            (void)low_queue_.pop_frame(low_frame_.data());
            (void)high_queue_.pop_frame(high_frame_.data());
            if (!filter_pair(low_frame_.data(), high_frame_.data())) return BOILEDEGG_RESEARCH_PV_RT_FIFO_OVERFLOW;
        }

        if (finalizing && low_queue_.count() != high_queue_.count()) {
            return BOILEDEGG_RESEARCH_PV_RT_INTERNAL_ERROR;
        }
        return BOILEDEGG_RESEARCH_PV_RT_OK;
    }

    std::uint32_t sample_rate_{}, channels_{}, max_block_{};
    float crossover_hz_{};
    std::uint32_t fir_taps_{}, fir_half_{};
    float time_ratio_{}, pitch_ratio_{};
    std::size_t branch_capacity_{}, output_capacity_{};
    std::uint32_t scratch_frames_{};
    ring_buffer low_queue_, high_queue_, output_queue_;
    std::vector<float> low_scratch_, high_scratch_;
    std::vector<float*> low_ptrs_, high_ptrs_;
    std::vector<float> low_frame_, high_frame_, output_frame_;
    std::vector<float> lowpass_, diff_history_, high_history_;
    std::size_t history_position_{};
    std::uint64_t raw_pairs_{}, input_frames_{}, output_frames_{};
    bool flushed_{};
    boiledegg_research_pv_rt_handle* low_{};
    boiledegg_research_pv_rt_handle* high_{};
};

} // namespace boiled_egg::research::multires_detail

struct boiledegg_research_multires_rt_handle { boiled_egg::research::multires_detail::engine* engine{}; };

extern "C" {
boiledegg_research_multires_rt_config boiledegg_research_multires_rt_default_config(
    std::uint32_t sample_rate, std::uint32_t channels, std::uint32_t max_block_frames) {
    boiledegg_research_multires_rt_config config{};
    config.struct_size = sizeof(config);
    config.abi_version = BOILEDEGG_RESEARCH_MULTIRES_RT_ABI_VERSION;
    config.sample_rate = sample_rate;
    config.channels = channels;
    config.max_block_frames = max_block_frames;
    config.initial_time_ratio = 1.0F;
    config.initial_pitch_ratio = 1.0F;
    config.formant_mode = BOILEDEGG_RESEARCH_PV_RT_FORMANT_HARMONIC;
    config.formant_cepstral_order = 40U;
    config.formant_gain_limit_db = 15.0F;
    config.monophonic_min_f0_hz = 60.0F;
    config.monophonic_max_f0_hz = 900.0F;
    config.crossover_hz = 6500.0F;
    config.fir_taps = 129U;
    return config;
}

boiledegg_research_multires_rt_handle* boiledegg_research_multires_rt_create(
    const boiledegg_research_multires_rt_config* config,
    boiledegg_research_pv_rt_result* result) {
    const auto features = boiledegg_research_default_features();
    return boiledegg_research_multires_rt_create_ex(config, &features, result);
}
boiledegg_research_multires_rt_handle* boiledegg_research_multires_rt_create_ex(
    const boiledegg_research_multires_rt_config* config,
    const boiledegg_research_features* features,
    boiledegg_research_pv_rt_result* result) {
    if (result != nullptr) *result = BOILEDEGG_RESEARCH_PV_RT_INVALID_CONFIG;
    if (config == nullptr || config->struct_size < sizeof(*config) || !boiled_egg::research::features::valid(features, config->formant_mode) ||
        !boiled_egg::research::multires_detail::engine::valid(*config)) {
        if (result != nullptr) *result = BOILEDEGG_RESEARCH_PV_RT_INVALID_CONFIG;
        return nullptr;
    }
    auto scaled = *config;
    const auto scale = boiled_egg::research::features::scale(config->sample_rate, *features);
    scaled.fir_taps = (config->fir_taps - 1U) * scale + 1U;
    try {
        auto* handle = new boiledegg_research_multires_rt_handle;
        try {
            handle->engine = new boiled_egg::research::multires_detail::engine(scaled, *features);
        } catch (...) {
            delete handle;
            throw;
        }
        if (result != nullptr) *result = BOILEDEGG_RESEARCH_PV_RT_OK;
        return handle;
    } catch (const std::bad_alloc&) {
        if (result != nullptr) *result = BOILEDEGG_RESEARCH_PV_RT_OUT_OF_MEMORY;
        return nullptr;
    } catch (...) {
        if (result != nullptr) *result = BOILEDEGG_RESEARCH_PV_RT_INTERNAL_ERROR;
        return nullptr;
    }
}

boiledegg_research_pv_rt_result boiledegg_research_multires_rt_set_formant_ratio(boiledegg_research_multires_rt_handle* h, float ratio) {
    return (!h || !h->engine) ? BOILEDEGG_RESEARCH_PV_RT_INVALID_ARGUMENT : h->engine->set_formant_ratio(ratio);
}
float boiledegg_research_multires_rt_get_formant_ratio(const boiledegg_research_multires_rt_handle* h) {
    return (!h || !h->engine) ? 0.0F : h->engine->formant_ratio();
}
void boiledegg_research_multires_rt_destroy(boiledegg_research_multires_rt_handle* handle) {
    if (handle != nullptr) {
        delete handle->engine;
        delete handle;
    }
}

boiledegg_research_pv_rt_result boiledegg_research_multires_rt_reset(boiledegg_research_multires_rt_handle* handle) {
    return handle == nullptr || handle->engine == nullptr ? BOILEDEGG_RESEARCH_PV_RT_INVALID_ARGUMENT : handle->engine->reset();
}

boiledegg_research_pv_rt_result boiledegg_research_multires_rt_set_time_ratio(
    boiledegg_research_multires_rt_handle* handle, float ratio) {
    return handle == nullptr || handle->engine == nullptr ? BOILEDEGG_RESEARCH_PV_RT_INVALID_ARGUMENT : handle->engine->set_time_ratio(ratio);
}

float boiledegg_research_multires_rt_get_time_ratio(const boiledegg_research_multires_rt_handle* handle) {
    return handle == nullptr || handle->engine == nullptr ? 0.0F : handle->engine->time_ratio();
}

boiledegg_research_pv_rt_result boiledegg_research_multires_rt_set_pitch_ratio(
    boiledegg_research_multires_rt_handle* handle, float ratio) {
    return handle == nullptr || handle->engine == nullptr ? BOILEDEGG_RESEARCH_PV_RT_INVALID_ARGUMENT : handle->engine->set_pitch_ratio(ratio);
}

float boiledegg_research_multires_rt_get_pitch_ratio(const boiledegg_research_multires_rt_handle* handle) {
    return handle == nullptr || handle->engine == nullptr ? 0.0F : handle->engine->pitch_ratio();
}

boiledegg_research_pv_rt_result boiledegg_research_multires_rt_push(
    boiledegg_research_multires_rt_handle* handle, const float* const* input, std::uint32_t frames) {
    return handle == nullptr || handle->engine == nullptr ? BOILEDEGG_RESEARCH_PV_RT_INVALID_ARGUMENT : handle->engine->push(input, frames);
}

std::uint32_t boiledegg_research_multires_rt_available(const boiledegg_research_multires_rt_handle* handle) {
    return handle == nullptr || handle->engine == nullptr ? 0U : handle->engine->available();
}

std::uint32_t boiledegg_research_multires_rt_pull(
    boiledegg_research_multires_rt_handle* handle, float* const* output, std::uint32_t capacity_frames) {
    return handle == nullptr || handle->engine == nullptr ? 0U : handle->engine->pull(output, capacity_frames);
}

boiledegg_research_pv_rt_result boiledegg_research_multires_rt_flush(boiledegg_research_multires_rt_handle* handle) {
    return handle == nullptr || handle->engine == nullptr ? BOILEDEGG_RESEARCH_PV_RT_INVALID_ARGUMENT : handle->engine->flush();
}

std::uint32_t boiledegg_research_multires_rt_latency_frames(const boiledegg_research_multires_rt_handle* handle) {
    return handle == nullptr || handle->engine == nullptr ? 0U : handle->engine->latency();
}

std::uint64_t boiledegg_research_multires_rt_input_frames(const boiledegg_research_multires_rt_handle* handle) {
    return handle == nullptr || handle->engine == nullptr ? 0U : handle->engine->input_frames();
}

std::uint64_t boiledegg_research_multires_rt_output_frames(const boiledegg_research_multires_rt_handle* handle) {
    return handle == nullptr || handle->engine == nullptr ? 0U : handle->engine->output_frames();
}
}
