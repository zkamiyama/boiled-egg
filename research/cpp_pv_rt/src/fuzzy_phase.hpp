#ifndef BOILED_EGG_RESEARCH_FUZZY_PHASE_HPP
#define BOILED_EGG_RESEARCH_FUZZY_PHASE_HPP

#include <algorithm>
#include <array>
#include <cmath>
#include <cstddef>
#include <cstdint>
#include <numbers>
#include <vector>

namespace boiled_egg::research::detail {

// Causal research adaptation, NOT a reproduction of the complete 2017 method.
// Damskagg & Valimaki, doi:10.3390/app7121293, equations (4)-(6), (12)-(13).
// Differences: trailing nine-frame median; no extra lookahead; shared channel
// rotation; exact identity at stretch=1; optional local onset reset, NOT the
// paper's magnitude suppression/compensation and transient-center lookahead.
class fuzzy_phase {
public:
    struct membership { float tonal, noise, transient; };
    static constexpr std::size_t history_size = 9;
    static constexpr std::uint32_t seed = 0x9e3779b9U;

    fuzzy_phase(std::uint32_t bins, std::uint32_t fft, std::uint32_t rate)
        : bins_(bins), radius_(std::clamp(
              static_cast<std::uint32_t>(std::lround(250.0 * fft / rate)), 2U, 31U)),
          history_(static_cast<std::size_t>(bins) * history_size),
          sorted_history_(static_cast<std::size_t>(bins) * history_size),
          rotation_(bins), predicted_(bins), membership_(bins), jitter_(bins),
          refractory_(bins) {
        // Precompute the noisiness term of (13), outside the callback.
        for (std::size_t i = 0; i < noise_lut_.size(); ++i) {
            const float r = static_cast<float>(i) / 1024.0F;
            noise_lut_[i] = 0.5F * (std::tanh(4.0F * (r - 1.0F)) + 1.0F);
        }
        reset();
    }

    void reset() noexcept {
        std::fill(history_.begin(), history_.end(), 0.0F);
        std::fill(sorted_history_.begin(), sorted_history_.end(), 0.0F);
        std::fill(rotation_.begin(), rotation_.end(), 0.0F);
        std::fill(refractory_.begin(), refractory_.end(), 0U);
        position_ = 0;
        populated_ = false;
        random_ = seed;
        last_stretch_ = -1.0F;
    }

    static membership classify(float horizontal, float vertical) noexcept {
        const float sum = horizontal + vertical;
        if (!(sum > 4.0e-6F)) return {1.0F, 0.0F, 0.0F};
        const float tonal = std::clamp(horizontal / sum, 0.0F, 1.0F);
        return {tonal, 1.0F - std::abs(2.0F * tonal - 1.0F), 1.0F - tonal};
    }

    static float wrap(float value) noexcept {
        constexpr float pi = std::numbers::pi_v<float>;
        value = std::fmod(value + pi, 2.0F * pi);
        if (value < 0.0F) value += 2.0F * pi;
        return value - pi;
    }

    void analyze(const float* linked) noexcept {
        if (!populated_) {
            // Replicate the first frame instead of inventing preceding silence.
            for (std::size_t i = 0; i < history_size; ++i)
                std::copy_n(linked, bins_, history_.data() + i * bins_);
            for (std::uint32_t k = 0; k < bins_; ++k)
                std::fill_n(sorted_history_.data() + k * history_size, history_size, linked[k]);
            populated_ = true;
        }
        // Exact rolling order statistics. The initial frequency window is
        // sorted once; each successive bin evicts/inserts one value. Time
        // windows similarly replace the outgoing ring entry. This preserves
        // the original medians, including replicated edges and duplicate bins,
        // without re-sorting two complete windows at every time-frequency bin.
        std::array<float, 63> vertical{};
        const auto length = 2U * radius_ + 1U;
        for (std::uint32_t j = 0; j < length; ++j) {
            const auto bin = std::clamp(static_cast<int>(j) - static_cast<int>(radius_),
                                       0, static_cast<int>(bins_) - 1);
            vertical[j] = linked[static_cast<std::uint32_t>(bin)];
        }
        (void)median(vertical.data(), length);
        float* oldest = history_.data() + position_ * bins_;
        for (std::uint32_t k = 0; k < bins_; ++k) {
            float* horizontal = sorted_history_.data() + k * history_size;
            replace_sorted(horizontal, history_size, oldest[k], linked[k]);
            oldest[k] = linked[k];
            if (k) {
                const auto outgoing = k > radius_ ? k - radius_ - 1U : 0U;
                const auto incoming = std::min(k + radius_, bins_ - 1U);
                replace_sorted(vertical.data(), length, linked[outgoing], linked[incoming]);
            }
            membership_[k] = classify(horizontal[history_size / 2U], vertical[length / 2U]);
        }
        position_ = (position_ + 1U) % history_size;
    }

    // Arrays have channels*bins elements unless explicitly linked/owners/omega.
    // Each bin receives one common rotation, including a common random offset,
    // so input inter-channel phase differences survive spectral synthesis.
    void process(const float* linked, const float* previous_linked,
                 const float* magnitude, const float* phase, const float* previous_phase,
                 const std::uint32_t* owners, const float* omega,
                 std::uint32_t channels, std::uint32_t analysis_hop, float synthesis_hop,
                 float stretch, bool initialized, bool reset_onsets, float* output) noexcept {
        analyze(linked);
        if (stretch != last_stretch_) {
            // (13) is intended mainly for expansion. Keep its asymmetry, but
            // taper exactly to zero at unity for SDK identity/automation use.
            stretch_noise_ = 0.5F * (std::tanh(4.0F * (stretch - 1.5F)) + 1.0F) *
                std::min(1.0F, 4.0F * std::abs(stretch - 1.0F));
            last_stretch_ = stretch;
        }
        const float hop = static_cast<float>(analysis_hop);
        for (std::uint32_t k = 0; k < bins_; ++k) {
            std::uint32_t reference = 0;
            for (std::uint32_t ch = 1; ch < channels; ++ch)
                if (magnitude[static_cast<std::size_t>(ch) * bins_ + k] >
                    magnitude[static_cast<std::size_t>(reference) * bins_ + k]) reference = ch;
            const auto index = static_cast<std::size_t>(reference) * bins_ + k;
            const float residual = wrap(phase[index] - previous_phase[index] - omega[k] * hop);
            const float frequency = omega[k] + residual / hop;
            predicted_[k] = initialized ? wrap(rotation_[k] + (synthesis_hop - hop) * frequency) : 0.0F;
            jitter_[k] = draw(); // fixed work, deterministic across input block partitions
        }
        for (std::uint32_t k = 0; k < bins_; ++k) {
            float rotation = predicted_[owners[k]];
            const auto member = membership_[k];
            if (refractory_[k]) --refractory_[k];
            // Optional zero-lookahead ablation. Only strongly transient bins
            // with a >2x local rise are reset. No frame-wide reset or gain boost.
            if (reset_onsets && initialized && refractory_[k] == 0U &&
                member.transient > 0.7F && linked[k] > 2.0F * previous_linked[k] &&
                linked[k] > 1.0e-4F) {
                const float strength = (member.transient - 0.7F) / 0.3F;
                rotation *= 1.0F - strength;
                refractory_[k] = 3U;
            }
            rotation_[k] = wrap(rotation); // do not accumulate random jitter
            const float lut_index = member.noise * 1024.0F;
            const auto i = std::min(static_cast<std::size_t>(lut_index), std::size_t{1023});
            const float fraction = lut_index - static_cast<float>(i);
            const float noise_amount = noise_lut_[i] + fraction * (noise_lut_[i + 1U] - noise_lut_[i]);
            // Protect the whole lobe of a tonal peak, not just its central bin.
            // Otherwise Hann sidelobes classified as noise modulate pure tones.
            const float owner_tonal = membership_[owners[k]].tonal;
            const float protection = std::clamp((0.9F - owner_tonal) / 0.3F, 0.0F, 1.0F);
            const float perturb = initialized && k != 0U && k + 1U != bins_
                ? std::numbers::pi_v<float> * stretch_noise_ * noise_amount * protection * jitter_[k] : 0.0F;
            for (std::uint32_t ch = 0; ch < channels; ++ch) {
                const auto index = static_cast<std::size_t>(ch) * bins_ + k;
                output[index] = wrap(phase[index] + rotation_[k] + perturb);
            }
        }
    }

    [[nodiscard]] membership bin(std::uint32_t k) const noexcept { return membership_[k]; }

private:
    static void replace_sorted(float* data, std::size_t size, float outgoing, float incoming) noexcept {
        // Finite nonnegative magnitudes; exactly one copy of outgoing exists.
        // All loops are bounded by size (9 in time, at most 63 in frequency).
        if (outgoing == incoming) return;
        std::size_t i = 0;
        while (i + 1U < size && data[i] < outgoing) ++i;
        if (incoming > outgoing) {
            while (i + 1U < size && data[i + 1U] < incoming) {
                data[i] = data[i + 1U]; ++i;
            }
        } else {
            while (i && data[i - 1U] > incoming) {
                data[i] = data[i - 1U]; --i;
            }
        }
        data[i] = incoming;
    }
    static float median(float* data, std::size_t size) noexcept {
        // Insertion sort has bounded work and does not allocate; windows <=63.
        for (std::size_t i = 1; i < size; ++i) {
            const float value = data[i];
            std::size_t j = i;
            while (j && data[j - 1U] > value) { data[j] = data[j - 1U]; --j; }
            data[j] = value;
        }
        return data[size / 2U];
    }
    float draw() noexcept {
        // Per-instance xorshift32; no shared RNG, random_device, locks or I/O.
        random_ ^= random_ << 13U;
        random_ ^= random_ >> 17U;
        random_ ^= random_ << 5U;
        return static_cast<float>(random_ >> 8U) * (1.0F / 16777216.0F) - 0.5F;
    }
    std::uint32_t bins_, radius_;
    std::vector<float> history_, sorted_history_, rotation_, predicted_;
    std::vector<membership> membership_;
    std::vector<float> jitter_;
    std::vector<std::uint32_t> refractory_;
    std::array<float, 1025> noise_lut_{};
    std::size_t position_{};
    bool populated_{};
    std::uint32_t random_{};
    float stretch_noise_{}, last_stretch_{};
};
} // namespace boiled_egg::research::detail
#endif
