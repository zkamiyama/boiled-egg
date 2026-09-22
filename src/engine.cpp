#include "engine.hpp"

#include <cassert>
#include <array>
#include <vector>

namespace boiled_egg::detail {

namespace { void warm_resampler_bank(); }

static constexpr float kPi = 3.14159265358979323846f;

Engine::Engine(const boiledegg_config& c)
    : sample_rate_(c.sample_rate),
      channels_(c.channels),
      max_block_(c.max_block_size),
      window_(c.window_frames),
      overlap_(c.window_frames / 2u),
      hop_(c.window_frames / 2u),
      search_(c.search_frames),
      input_(c.channels, c.fifo_frames),
      intermediate_(c.channels, c.fifo_frames),
      output_(c.channels, c.fifo_frames),
      prev_tail_(static_cast<size_t>(c.channels) * overlap_, 0.0f),
      emit_scratch_(static_cast<size_t>(c.channels) * hop_, 0.0f),
      overlap_weights_(overlap_, 0.0f),
      correlation_tail_(overlap_, 0.0),
      correlation_input_(static_cast<size_t>(overlap_) + 2u * static_cast<size_t>(search_), 0.0),
      sample_scratch_(c.channels, 0.0f),
      zero_scratch_(static_cast<size_t>(c.channels) * c.max_block_size, 0.0f),
      zero_ptrs_(c.channels, nullptr) {
    // Retain the exact original float expression; no approximation or fast-math.
    for (uint32_t i = 0; i < overlap_; ++i) {
        const float t = overlap_ > 1 ? static_cast<float>(i) / static_cast<float>(overlap_ - 1u) : 1.0f;
        overlap_weights_[i] = 0.5f - 0.5f * std::cos(kPi * t);
    }
    for (uint32_t ch = 0; ch < channels_; ++ch) {
        zero_ptrs_[ch] = zero_scratch_.data() + static_cast<size_t>(ch) * max_block_;
    }
    warm_resampler_bank();
    reset();
}

boiledegg_result Engine::reset() noexcept {
    input_.reset(); intermediate_.reset(); output_.reset();
    std::fill(prev_tail_.begin(), prev_tail_.end(), 0.0f);
    std::fill(emit_scratch_.begin(), emit_scratch_.end(), 0.0f);
    have_prev_ = false; flushing_ = false; flush_padding_done_ = false;
    next_expected_ = 0.0; last_start_ = 0; resample_pos_ = 0.0;
    input_total_ = 0; produced_total_ = 0; target_output_accum_ = 0.0;
    target_output_frames_ = std::numeric_limits<uint64_t>::max();
    return BOILEDEGG_OK;
}

boiledegg_result Engine::set_time_ratio(float ratio) noexcept {
    if (!std::isfinite(ratio) || ratio < 0.25f || ratio > 4.0f) return BOILEDEGG_INVALID_ARGUMENT;
    time_ratio_ = ratio; return BOILEDEGG_OK;
}
boiledegg_result Engine::set_pitch_ratio(float ratio) noexcept {
    if (!std::isfinite(ratio) || ratio < 0.25f || ratio > 4.0f) return BOILEDEGG_INVALID_ARGUMENT;
    pitch_ratio_ = ratio; return BOILEDEGG_OK;
}

boiledegg_result Engine::push(const float* const* input, uint32_t frames, uint32_t& accepted) noexcept {
    accepted = 0;
    if (flushing_) return BOILEDEGG_END_OF_STREAM;
    if (!input || frames == 0) return frames == 0 ? BOILEDEGG_OK : BOILEDEGG_INVALID_ARGUMENT;
    for (uint32_t ch = 0; ch < channels_; ++ch) if (!input[ch]) return BOILEDEGG_INVALID_ARGUMENT;
    const uint32_t n = std::min(frames, input_.free_space());
    if (n == 0) return BOILEDEGG_BUFFER_FULL;
    if (!input_.push_planar(input, n)) return BOILEDEGG_INTERNAL_ERROR;
    accepted = n; input_total_ += n;
    target_output_accum_ += static_cast<double>(n) * static_cast<double>(time_ratio_);
    process_available();
    return n == frames ? BOILEDEGG_OK : BOILEDEGG_BUFFER_FULL;
}

boiledegg_result Engine::pull(float* const* output, uint32_t capacity, uint32_t& produced) noexcept {
    produced = 0;
    if (capacity == 0) return BOILEDEGG_OK;
    if (!output) return BOILEDEGG_INVALID_ARGUMENT;
    for (uint32_t ch = 0; ch < channels_; ++ch) if (!output[ch]) return BOILEDEGG_INVALID_ARGUMENT;
    process_available(); produced = output_.pop_planar(output, capacity); process_available();
    return BOILEDEGG_OK;
}

bool Engine::feed_padding(uint32_t frames) noexcept {
    while (frames > 0) {
        const uint32_t chunk = std::min(frames, max_block_);
        if (chunk > input_.free_space()) return false;
        if (!input_.push_planar(zero_ptrs_.data(), chunk)) return false;
        frames -= chunk;
    }
    return true;
}

boiledegg_result Engine::flush() noexcept {
    if (flushing_) { process_available(); return BOILEDEGG_OK; }
    flushing_ = true;
    target_output_frames_ = static_cast<uint64_t>(std::llround(target_output_accum_));
    const uint32_t pad = window_ + search_ + hop_ * 4u;
    if (!feed_padding(pad)) return BOILEDEGG_BUFFER_FULL;
    flush_padding_done_ = true; process_available(); return BOILEDEGG_OK;
}

void Engine::process_available() noexcept {
    bool progress = true;
    while (progress) {
        progress = false;
        while (intermediate_.free_space() >= hop_) {
            if (!process_wsola_frame()) break;
            progress = true;
        }
        const uint32_t before = output_.size(); process_resampler();
        if (output_.size() != before) progress = true;
        if (flushing_ && produced_total_ >= target_output_frames_) break;
        if (!progress && flushing_ && produced_total_ < target_output_frames_ && output_.free_space() > 0) {
            const uint32_t chunk = std::min<uint32_t>(max_block_, input_.free_space());
            if (chunk > 0 && feed_padding(chunk)) progress = true;
        }
    }
}

float Engine::correlation(int64_t candidate) noexcept {
    double dot = 0.0, bb = 1e-12;
    const uint32_t correlation_stride = sample_rate_ >= 88200 ? 8u : 2u;
    const size_t offset = static_cast<size_t>(candidate - correlation_start_);
    for (uint32_t i = 0; i < overlap_; i += correlation_stride) {
        const double a = correlation_tail_[i], b = correlation_input_[offset + i];
        dot += a * b; bb += b * b;
    }
    return static_cast<float>(dot / std::sqrt(correlation_tail_energy_ * bb));
}

int64_t Engine::choose_candidate(int64_t expected) noexcept {
    const double stretch = static_cast<double>(time_ratio_) * static_cast<double>(pitch_ratio_);
    if (std::abs(stretch - 1.0) < 1e-6) return expected;
    int64_t low = expected - static_cast<int64_t>(search_);
    int64_t high = expected + static_cast<int64_t>(search_);
    low = std::max<int64_t>(low, static_cast<int64_t>(input_.start_index()));
    high = std::min<int64_t>(high, static_cast<int64_t>(input_.end_index()) - static_cast<int64_t>(window_));
    if (high < low) return std::numeric_limits<int64_t>::min();
    // The tail and source channel means are identical for every candidate.
    // Compute them once per search, not again in each correlation evaluation.
    // No score approximation, new downmix rule or changed candidate ordering.
    correlation_start_ = low;
    correlation_tail_energy_ = 1e-12;
    const uint32_t stride = sample_rate_ >= 88200 ? 8u : 2u;
    for (uint32_t i = 0; i < overlap_; i += stride) {
        double mean = 0.0;
        for (uint32_t ch = 0; ch < channels_; ++ch)
            mean += prev_tail_[static_cast<size_t>(ch) * overlap_ + i];
        mean /= static_cast<double>(channels_);
        correlation_tail_[i] = mean;
        correlation_tail_energy_ += mean * mean;
    }
    const size_t needed = static_cast<size_t>(high - low) + overlap_;
    assert(needed <= correlation_input_.size());
    for (size_t i = 0; i < needed; ++i) {
        double mean = 0.0;
        for (uint32_t ch = 0; ch < channels_; ++ch)
            mean += input_.get(ch, low + static_cast<int64_t>(i));
        correlation_input_[i] = mean / static_cast<double>(channels_);
    }
    const int64_t coarse_step = sample_rate_ >= 88200 ? 8 : 4;
    float best_score = -std::numeric_limits<float>::infinity(); int64_t best = low;
    for (int64_t c = low; c <= high; c += coarse_step) {
        const float score = correlation(c);
        if (score > best_score) { best_score = score; best = c; }
    }
    const int64_t refine_low = std::max(low, best - coarse_step + 1);
    const int64_t refine_high = std::min(high, best + coarse_step - 1);
    for (int64_t c = refine_low; c <= refine_high; ++c) {
        const float score = correlation(c);
        if (score > best_score) { best_score = score; best = c; }
    }
    return best;
}

void Engine::emit_first_frame(int64_t start) noexcept {
    for (uint32_t ch = 0; ch < channels_; ++ch) {
        float* emit = emit_scratch_.data() + static_cast<size_t>(ch) * hop_;
        float* tail = prev_tail_.data() + static_cast<size_t>(ch) * overlap_;
        for (uint32_t i = 0; i < hop_; ++i) emit[i] = input_.get(ch, start + static_cast<int64_t>(i));
        for (uint32_t i = 0; i < overlap_; ++i) tail[i] = input_.get(ch, start + static_cast<int64_t>(hop_ + i));
    }
    (void)intermediate_.push_interleaved_scratch(emit_scratch_.data(), hop_);
}

void Engine::emit_overlap_frame(int64_t start) noexcept {
    for (uint32_t ch = 0; ch < channels_; ++ch) {
        float* emit = emit_scratch_.data() + static_cast<size_t>(ch) * hop_;
        float* tail = prev_tail_.data() + static_cast<size_t>(ch) * overlap_;
        for (uint32_t i = 0; i < overlap_; ++i) {
            const float w = overlap_weights_[i];
            const float cur = input_.get(ch, start + static_cast<int64_t>(i));
            emit[i] = (1.0f - w) * tail[i] + w * cur;
        }
        for (uint32_t i = 0; i < overlap_; ++i) tail[i] = input_.get(ch, start + static_cast<int64_t>(hop_ + i));
    }
    (void)intermediate_.push_interleaved_scratch(emit_scratch_.data(), hop_);
}

bool Engine::process_wsola_frame() noexcept {
    const double stretch = static_cast<double>(time_ratio_) * static_cast<double>(pitch_ratio_);
    if (stretch <= 0.0) return false;
    if (!have_prev_) {
        const int64_t start = static_cast<int64_t>(input_.start_index());
        const uint64_t need = static_cast<uint64_t>(start) + window_ + search_;
        if (input_.end_index() < need) return false;
        emit_first_frame(start); have_prev_ = true; last_start_ = start;
        next_expected_ = static_cast<double>(start) + static_cast<double>(hop_) / stretch;
        return true;
    }
    const int64_t expected = static_cast<int64_t>(std::llround(next_expected_));
    const int64_t low_need = expected - static_cast<int64_t>(search_);
    const int64_t high_need = expected + static_cast<int64_t>(search_) + static_cast<int64_t>(window_);
    // The next search never reads earlier samples. Reclaim them even while
    // waiting for a long analysis hop, so a legal small FIFO can make progress.
    // At startup choose_candidate() already clamps a negative lower bound.
    input_.discard_before(static_cast<uint64_t>(std::max<int64_t>(0, low_need)));
    if (static_cast<uint64_t>(high_need) > input_.end_index()) return false;
    const int64_t chosen = choose_candidate(expected);
    if (chosen == std::numeric_limits<int64_t>::min()) return false;
    emit_overlap_frame(chosen); last_start_ = chosen; next_expected_ += static_cast<double>(hop_) / stretch;
    const int64_t safe = std::max<int64_t>(0, chosen - static_cast<int64_t>(search_ + 2u));
    input_.discard_before(static_cast<uint64_t>(safe)); return true;
}

namespace {
inline double sinc_pi(double x) noexcept {
    if (std::abs(x) < 1.0e-12) return 1.0;
    const double pix = 3.141592653589793238462643383279502884 * x;
    return std::sin(pix) / pix;
}
inline double blackman_window(double x, double half_width) noexcept {
    const double ax = std::abs(x); if (ax >= half_width) return 0.0;
    const double phase = 3.141592653589793238462643383279502884 * x / half_width;
    return 0.42 + 0.5 * std::cos(phase) + 0.08 * std::cos(2.0 * phase);
}
struct ResamplerKernelBank {
    static constexpr int taps = 40, half = taps / 2, phases = 1024, cutoffs = 32;
    static constexpr double cutoff_min = 0.94 / 4.0, cutoff_max = 0.94;
    std::vector<float> weights;
    ResamplerKernelBank() : weights(static_cast<size_t>(cutoffs) * phases * taps) {
        for (int ci = 0; ci < cutoffs; ++ci) {
            const double cutoff = cutoff_for_index(ci);
            for (int pi = 0; pi < phases; ++pi) {
                const double frac = static_cast<double>(pi) / phases; double sum = 0.0; float* row = data(ci, pi);
                for (int tap = 0; tap < taps; ++tap) {
                    const double distance = static_cast<double>(tap - (half - 1)) - frac;
                    const double w = cutoff * sinc_pi(cutoff * distance) * blackman_window(distance, static_cast<double>(half));
                    row[tap] = static_cast<float>(w); sum += w;
                }
                if (std::abs(sum) > 1.0e-12) {
                    const float inv = static_cast<float>(1.0 / sum);
                    for (int tap = 0; tap < taps; ++tap) row[tap] *= inv;
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
    float* data(int ci, int pi) noexcept { return weights.data() + (static_cast<size_t>(ci) * phases + static_cast<size_t>(pi)) * taps; }
    const float* data(int ci, int pi) const noexcept { return weights.data() + (static_cast<size_t>(ci) * phases + static_cast<size_t>(pi)) * taps; }
};
const ResamplerKernelBank& resampler_bank() { static const ResamplerKernelBank bank; return bank; }
void warm_resampler_bank() { (void)resampler_bank(); }
} // namespace

void Engine::process_resampler() noexcept {
    // Only accepted input earns output time.  A WSOLA hop can be larger than
    // that budget at compression / pitch-down boundaries; never release its
    // speculative samples before more input arrives.  Keep the final nearest-
    // integer rounding in flush(), but only complete frames before EOF.
    const uint64_t output_limit = flushing_ ? target_output_frames_
        : static_cast<uint64_t>(target_output_accum_);
    // Avoid invariant kernel preparation on the frequent no-output calls.
    if (produced_total_ >= output_limit || output_.free_space() == 0) return;
    const auto& bank = resampler_bank();
    constexpr int kTaps = ResamplerKernelBank::taps, kHalf = ResamplerKernelBank::half;
    const double desired_cutoff = 0.94 * std::min(1.0, 1.0 / static_cast<double>(pitch_ratio_));
    const int cutoff_index = ResamplerKernelBank::cutoff_index(desired_cutoff);
    while (output_.free_space() > 0) {
        if (produced_total_ >= output_limit) return;
        const int64_t center = static_cast<int64_t>(std::floor(resample_pos_));
        const int64_t first = center - (kHalf - 1), last = center + kHalf;
        if (last < 0 || static_cast<uint64_t>(last) >= intermediate_.end_index()) return;
        const double frac = resample_pos_ - static_cast<double>(center);
        if (std::abs(static_cast<double>(pitch_ratio_) - 1.0) < 1.0e-12 && std::abs(frac) < 1.0e-12) {
            if (center < 0 || static_cast<uint64_t>(center) < intermediate_.start_index()) {
                resample_pos_ = static_cast<double>(intermediate_.start_index()); continue;
            }
            for (uint32_t ch = 0; ch < channels_; ++ch) sample_scratch_[ch] = intermediate_.get(ch, center);
        } else {
            const int phase = std::clamp(static_cast<int>(frac * ResamplerKernelBank::phases), 0, ResamplerKernelBank::phases - 1);
            const float* kernel = bank.data(cutoff_index, phase);
            for (uint32_t ch = 0; ch < channels_; ++ch) {
                float sum = 0.0f;
                if (const float* span = intermediate_.contiguous(ch, first, kTaps)) {
                    // Same ascending tap order and float multiply/add, without
                    // repeating range checks and integer remainder per tap.
                    for (int tap = 0; tap < kTaps; ++tap) sum += kernel[tap] * span[tap];
                } else {
                    for (int tap = 0; tap < kTaps; ++tap)
                        sum += kernel[tap] * intermediate_.get(ch, first + tap);
                }
                sample_scratch_[ch] = sum;
            }
        }
        if (!output_.push_one(sample_scratch_.data())) return;
        ++produced_total_; resample_pos_ += static_cast<double>(pitch_ratio_);
        const int64_t keep = static_cast<int64_t>(std::floor(resample_pos_)) - kHalf - 2;
        if (keep > 0) intermediate_.discard_before(static_cast<uint64_t>(keep));
    }
}

} // namespace boiled_egg::detail
