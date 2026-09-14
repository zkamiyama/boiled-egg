// Opt-in cooperative frame producer. Included inside engine's private section.
// Numerical steps mirror the immediate scalar path; regression compares complete
// WAVs. Each coroutine is created once by construction, never by push/pull/reset.
void transform(std::complex<float>* data, bool inverse) noexcept {
    if (!simd_) { if (inverse) fft_.inverse(data); else fft_.forward(data); return; }
    fft_plan::cursor cursor;
    fft_.start(cursor,data,inverse,true);
    while(fft_.advance(cursor,4096U)) {}
}
void finish_task() noexcept {
    while (frame_active_) {
        ++current_steps_;
        frame_active_=frame_task_.step();
        if (!frame_active_) {
            ++completed_frames_;
            max_frame_steps_=std::max(max_frame_steps_,current_steps_);
        }
    }
}
void start_task() noexcept {
    frame_formant_target_=formant_ratio_;
    latch_timeline();
    frame_active_=true;
    current_steps_=0;
}
bool tick() noexcept {
    if (!frame_active_ && full_analysis_frame()) start_task();
    for (std::uint32_t i=0; i<steps_per_input_ && frame_active_; ++i) {
        ++current_steps_;
        frame_active_=frame_task_.step();
        if (!frame_active_) {
            ++completed_frames_;
            max_frame_steps_=std::max(max_frame_steps_,current_steps_);
        }
    }
    if (frame_active_ && input_write_ >= analysis_start_+n_fft_+analysis_hop_) {
        ++frame_overruns_; return false;
    }
    return true;
}
work_sequence formant_sequence() { for (;;) {

        std::fill(formant_gain_.begin(), formant_gain_.end(), 1.0F);
        if (smoothed_formant_ratio_ != frame_formant_target_) {
            const float error = std::log(frame_formant_target_ / smoothed_formant_ratio_);
            smoothed_formant_ratio_ = std::abs(error) < 1.0e-6F ? frame_formant_target_
            : smoothed_formant_ratio_ * std::exp(formant_smoothing_ * error);
        }
        const float envelope_warp = frame_pitch() / smoothed_formant_ratio_;
        if (formant_mode_ == BOILEDEGG_RESEARCH_PV_RT_FORMANT_OFF ||
        std::abs(envelope_warp - 1.0F) < 1.0e-6F || formant_gain_limit_db_ <= 0.0F) {
            formant_energy_compensation_ = 1.0F;
            co_yield false;
            continue;
        }

        for (std::uint32_t k = 0; k < bins_; ++k)
        {
            if ((k & 31U) == 0U) co_yield true;
            envelope_work_[k] = {std::log(std::max(linked_magnitude_[k], 1.0e-7F)), 0.0F};
        }
        for (std::uint32_t k = bins_; k < n_fft_; ++k)
        {
            if ((k & 31U) == 0U) co_yield true;
            envelope_work_[k] = envelope_work_[n_fft_ - k];
        }
        fft_.start(fft_cursor_, envelope_work_.data(), true, simd_);
        while (fft_.advance(fft_cursor_, 128U)) co_yield true;
        co_yield true;

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
                    if ((q & 31U) == 0U) co_yield true;

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
            if ((q & 31U) == 0U) co_yield true;

            const std::uint32_t folded = std::min<std::uint32_t>(q, n_fft_ - q);
            if (folded > order) {
                envelope_work_[q] = {0.0F, 0.0F};
            } else if (taper != 0U && folded > order - taper) {
                const float x = static_cast<float>(folded - (order - taper)) / static_cast<float>(taper);
                const float w = 0.5F * (1.0F + std::cos(std::numbers::pi_v<float> * x));
                envelope_work_[q] *= w;
            }
        }
        fft_.start(fft_cursor_, envelope_work_.data(), false, simd_);
        while (fft_.advance(fft_cursor_, 128U)) co_yield true;
        co_yield true;
        for (std::uint32_t k = 0; k < bins_; ++k) {
            if ((k & 31U) == 0U) co_yield true;
            log_envelope_[k] = envelope_work_[k].real();
        }

        constexpr float db_per_neper = 20.0F / 2.302585092994046F;
        constexpr float neper_per_db = 2.302585092994046F / 20.0F;
        const float bin_hz = static_cast<float>(sample_rate_) / static_cast<float>(n_fft_);
        for (std::uint32_t k = 0; k < bins_; ++k) {
            if ((k & 31U) == 0U) co_yield true;

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
            if ((k & 31U) == 0U) co_yield true;

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
            if ((k & 31U) == 0U) co_yield true;

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

        co_yield false;
    } }
work_sequence peaks_sequence() { for (;;) {

        peak_count_ = 0;
        float maximum = 0.0F;
        for (float value : linked_magnitude_) maximum = std::max(maximum, value);
        const float threshold = maximum * std::pow(10.0F, -55.0F / 20.0F);
        if (bins_ >= 2U && linked_magnitude_[0] > linked_magnitude_[1] && linked_magnitude_[0] >= threshold)
        peaks_[peak_count_++] = 0U;
        for (std::uint32_t k = 1; k + 1U < bins_; ++k)
        {
            if ((k & 31U) == 0U) co_yield true;
            if (linked_magnitude_[k] >= linked_magnitude_[k - 1U] && linked_magnitude_[k] > linked_magnitude_[k + 1U] && linked_magnitude_[k] >= threshold)
            peaks_[peak_count_++] = k;
        }
        if (bins_ >= 2U && linked_magnitude_[bins_ - 1U] >= linked_magnitude_[bins_ - 2U] && linked_magnitude_[bins_ - 1U] >= threshold)
        peaks_[peak_count_++] = bins_ - 1U;
        if (peak_count_ == 0U)
        peaks_[peak_count_++] = static_cast<std::uint32_t>(std::distance(linked_magnitude_.begin(), std::max_element(linked_magnitude_.begin(), linked_magnitude_.end())));
        std::uint32_t begin = 0;
        for (std::uint32_t i = 0; i < peak_count_; ++i) {
            const std::uint32_t end = (i + 1U < peak_count_) ? ((peaks_[i] + peaks_[i + 1U]) / 2U + 1U) : bins_;
            for (std::uint32_t k = begin; k < end; ++k) {
                if ((k & 31U) == 0U) co_yield true;
                owners_[k] = peaks_[i];
            }
            begin = end;
        }

        co_yield false;
    } }
work_sequence frame_sequence() { for (;;) {

        const std::uint64_t synth_start = round_u64(synthesis_position_);
        for (std::uint32_t ch = 0; ch < channels_; ++ch) {
            auto* work = fft_work_.data() + static_cast<std::size_t>(ch) * n_fft_;
            for (std::uint32_t n = 0; n < n_fft_; ++n) {
                if ((n & 31U) == 0U) co_yield true;

                const std::size_t slot = static_cast<std::size_t>((analysis_start_ + n) % input_capacity_);
                work[n] = {input_[static_cast<std::size_t>(ch) * input_capacity_ + slot] * window_[n], 0.0F};
            }
            fft_.start(fft_cursor_, work, false, simd_);
            while (fft_.advance(fft_cursor_, 128U)) co_yield true;
            co_yield true;
            for (std::uint32_t k = 0; k < bins_; ++k) {
                if ((k & 31U) == 0U) co_yield true;

                const std::size_t idx = static_cast<std::size_t>(ch) * bins_ + k;
                magnitude_[idx] = std::abs(work[k]);
                phase_[idx] = std::arg(work[k]);
            }
        }
        for (std::uint32_t k = 0; k < bins_; ++k) {
            if ((k & 31U) == 0U) co_yield true;

            double sum = 0.0;
            for (std::uint32_t ch = 0; ch < channels_; ++ch) {
                const float m = magnitude_[static_cast<std::size_t>(ch) * bins_ + k];
                sum += static_cast<double>(m) * m;
            }
            linked_magnitude_[k] = static_cast<float>(std::sqrt(sum / static_cast<double>(channels_) + k_epsilon));
        }
        while (formant_task_.step()) co_yield true;

        float flux_numerator = 0.0F, flux_denominator = k_epsilon;
        for (std::uint32_t k = 0; k < bins_; ++k) {
            if ((k & 31U) == 0U) co_yield true;

            flux_numerator += std::max(0.0F, linked_magnitude_[k] - previous_linked_magnitude_[k]);
            flux_denominator += previous_linked_magnitude_[k];
        }
        const float flux = initialized_ ? flux_numerator / flux_denominator : 0.0F;
        const float sigma = std::sqrt(std::max(flux_variance_, 0.0F));
        const bool transient = mode_ == BOILEDEGG_RESEARCH_PV_RT_TRANSIENT && initialized_ &&
        flux > transient_floor_ && flux > flux_mean_ + transient_sigma_ * sigma;
        if (mode_ != BOILEDEGG_RESEARCH_PV_RT_CLASSIC) { while (peaks_task_.step()) co_yield true; }
        const std::uint64_t previous_synth = previous_synth_start_;
        const float synthesis_hop = initialized_ ? static_cast<float>(synth_start - previous_synth) : 0.0F;
        const bool fuzzy_mode = mode_ >= BOILEDEGG_RESEARCH_PV_RT_FUZZY;
        if (fuzzy_mode) {
            fuzzy_.begin_sliced(linked_magnitude_.data(), previous_linked_magnitude_.data(),
            magnitude_.data(), phase_.data(), previous_phase_.data(), owners_.data(),
            omega_.data(), channels_, analysis_hop_, synthesis_hop,
            static_cast<float>(internal_stretch()), initialized_,
            mode_ == BOILEDEGG_RESEARCH_PV_RT_FUZZY, output_phase_.data());
            while (fuzzy_.advance_sliced()) co_yield true;
        }
        if(timeline_.enabled()) {
            for(std::uint32_t k=0;k<bins_;++k){if((k&31U)==0U)co_yield true;timeline_predict(k,synthesis_hop);}
            for(std::uint32_t k=0;k<bins_;++k){if((k&31U)==0U)co_yield true;timeline_phase(k);}
        }
        for (std::uint32_t ch = 0; ch < channels_; ++ch) {
            if (!fuzzy_mode && !timeline_.enabled()) {
                for (std::uint32_t k = 0; k < bins_; ++k) {
                    if ((k & 31U) == 0U) co_yield true;

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
                        if ((k & 31U) == 0U) co_yield true;

                        const std::uint32_t owner = owners_[k];
                        const std::size_t idx = static_cast<std::size_t>(ch) * bins_ + k;
                        const std::size_t owner_idx = static_cast<std::size_t>(ch) * bins_ + owner;
                        output_phase_[idx] = output_phase_[owner_idx] + wrap_phase(phase_[idx] - phase_[owner_idx]);
                    }
                }
            }
            auto* work = fft_work_.data() + static_cast<std::size_t>(ch) * n_fft_;
            for (std::uint32_t k = 0; k < bins_; ++k) {
                if ((k & 31U) == 0U) co_yield true;

                const std::size_t idx = static_cast<std::size_t>(ch) * bins_ + k;
                work[k] = std::polar(magnitude_[idx] * formant_gain_[k], output_phase_[idx]);
            }
            for (std::uint32_t k = bins_; k < n_fft_; ++k) {
                if ((k & 31U) == 0U) co_yield true;
                work[k] = std::conj(work[n_fft_ - k]);
            }
            fft_.start(fft_cursor_, work, true, simd_);
            while (fft_.advance(fft_cursor_, 128U)) co_yield true;
            co_yield true;
            for (std::uint32_t n = 0; n < n_fft_; ++n) {
                if ((n & 31U) == 0U) co_yield true;

                const std::uint64_t absolute = synth_start + n;
                const std::size_t slot = static_cast<std::size_t>(absolute % ola_capacity_);
                ola_[static_cast<std::size_t>(ch) * ola_capacity_ + slot] += work[n].real() * window_[n];
            }
        }
        for (std::uint32_t n = 0; n < n_fft_; ++n) {
            if ((n & 31U) == 0U) co_yield true;

            const std::size_t slot = static_cast<std::size_t>((synth_start + n) % ola_capacity_);
            weight_[slot] += window_[n] * window_[n];
        }
        latest_safe_position_ = synth_start;

        for (std::size_t k=0; k<phase_.size(); ++k) {
            if ((k & 63U)==0U) co_yield true;
            previous_phase_[k]=phase_[k];
        }
        for (std::size_t k=0; k<output_phase_.size(); ++k) {
            if ((k & 63U)==0U) co_yield true;
            previous_output_phase_[k]=output_phase_[k];
        }
        for (std::size_t k=0; k<linked_magnitude_.size(); ++k) {
            if ((k & 63U)==0U) co_yield true;
            previous_linked_magnitude_[k]=linked_magnitude_[k];
        }
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

        co_yield false;
    } }
