// Persistent opt-in slices. Included within fuzzy_phase.
public:
void enable_slicing() { slice_task_=sliced_sequence(); }
void begin_sliced(const float* linked, const float* previous_linked,
const float* magnitude, const float* phase, const float* previous_phase,
const std::uint32_t* owners, const float* omega,
std::uint32_t channels, std::uint32_t analysis_hop, float synthesis_hop,
float stretch, bool initialized, bool reset_onsets, float* output) noexcept {
    slice_job_={linked,previous_linked,magnitude,phase,previous_phase,owners,omega,
        channels,analysis_hop,synthesis_hop,stretch,initialized,reset_onsets,output};
}
bool advance_sliced() noexcept { return slice_task_.step(); }
private:
struct sliced_job { const float *linked, *previous_linked, *magnitude, *phase, *previous_phase;
    const std::uint32_t* owners; const float* omega;
    std::uint32_t channels,analysis_hop; float synthesis_hop,stretch;
    bool initialized,reset_onsets; float* output; } slice_job_{};
work_sequence slice_task_;
work_sequence sliced_sequence() { for (;;) {
        const auto [linked,previous_linked,magnitude,phase,previous_phase,owners,omega,
        channels,analysis_hop,synthesis_hop,stretch,initialized,reset_onsets,output]=slice_job_;

        if (!populated_) {
            // Replicate the first frame instead of inventing preceding silence.
            for (std::uint32_t k=0; k<bins_; ++k) {
                if ((k & 31U)==0U) co_yield true;
                for (std::size_t i=0; i<history_size; ++i) history_[i*bins_+k]=linked[k];
            }
            for (std::uint32_t k = 0; k < bins_; ++k)
            {
                if ((k & 31U) == 0U) co_yield true;
                std::fill_n(sorted_history_.data() + k * history_size, history_size, linked[k]);
            }
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
            if ((k & 31U) == 0U) co_yield true;

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

        if (stretch != last_stretch_) {
            // (13) is intended mainly for expansion. Keep its asymmetry, but
            // taper exactly to zero at unity for SDK identity/automation use.
            stretch_noise_ = 0.5F * (std::tanh(4.0F * (stretch - 1.5F)) + 1.0F) *
            std::min(1.0F, 4.0F * std::abs(stretch - 1.0F));
            last_stretch_ = stretch;
        }
        const float hop = static_cast<float>(analysis_hop);
        for (std::uint32_t k = 0; k < bins_; ++k) {
            if ((k & 31U) == 0U) co_yield true;

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
            if ((k & 31U) == 0U) co_yield true;

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

        co_yield false;
    } }
