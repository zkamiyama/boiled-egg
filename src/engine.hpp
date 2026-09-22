#pragma once

#include <algorithm>
#include <cmath>
#include <cstdint>
#include <limits>
#include <vector>

#include <boiled_egg/boiled_egg.h>

namespace boiled_egg::detail {

class PlanarRing {
public:
    PlanarRing() = default;
    PlanarRing(uint32_t channels, uint32_t capacity) { init(channels, capacity); }

    void init(uint32_t channels, uint32_t capacity) {
        channels_ = channels;
        capacity_ = std::max<uint32_t>(capacity, 8u);
        mask_ = (capacity_ & (capacity_ - 1u)) == 0u ? capacity_ - 1u : 0u;
        data_.assign(static_cast<size_t>(channels_) * capacity_, 0.0f);
        reset();
    }

    void reset() noexcept {
        start_ = 0;
        end_ = 0;
        std::fill(data_.begin(), data_.end(), 0.0f);
    }

    uint64_t start_index() const noexcept { return start_; }
    uint64_t end_index() const noexcept { return end_; }
    uint32_t size() const noexcept { return static_cast<uint32_t>(end_ - start_); }
    uint32_t free_space() const noexcept { return capacity_ - size(); }
    uint32_t capacity() const noexcept { return capacity_; }

    float get(uint32_t ch, int64_t absolute_index) const noexcept {
        if (absolute_index < 0) return 0.0f;
        const auto idx = static_cast<uint64_t>(absolute_index);
        if (idx < start_ || idx >= end_ || ch >= channels_) return 0.0f;
        return data_[static_cast<size_t>(ch) * capacity_ + slot_index(idx)];
    }

    // Borrow a complete non-wrapping readable span; boundary/zero-padding
    // cases deliberately fall back to get(). No unchecked storage access.
    const float* contiguous(uint32_t ch, int64_t absolute_index, uint32_t frames) const noexcept {
        if (absolute_index < 0 || ch >= channels_) return nullptr;
        const auto index = static_cast<uint64_t>(absolute_index);
        if (index < start_ || index > end_ || frames > end_ - index) return nullptr;
        const auto slot = slot_index(index);
        if (frames > capacity_ - slot) return nullptr;
        return data_.data() + static_cast<size_t>(ch) * capacity_ + slot;
    }

    bool push_planar(const float* const* src, uint32_t frames) noexcept {
        if (frames > free_space()) return false;
        for (uint32_t i = 0; i < frames; ++i) {
            const uint64_t pos = end_ + i;
            const size_t slot = slot_index(pos);
            for (uint32_t ch = 0; ch < channels_; ++ch) {
                data_[static_cast<size_t>(ch) * capacity_ + slot] = src[ch][i];
            }
        }
        end_ += frames;
        return true;
    }

    bool push_interleaved_scratch(const float* src_planar_contiguous, uint32_t frames) noexcept {
        if (frames > free_space()) return false;
        for (uint32_t i = 0; i < frames; ++i) {
            const uint64_t pos = end_ + i;
            const size_t slot = slot_index(pos);
            for (uint32_t ch = 0; ch < channels_; ++ch) {
                data_[static_cast<size_t>(ch) * capacity_ + slot] =
                    src_planar_contiguous[static_cast<size_t>(ch) * frames + i];
            }
        }
        end_ += frames;
        return true;
    }

    bool push_one(const float* frame) noexcept {
        if (free_space() == 0) return false;
        const size_t slot = slot_index(end_);
        for (uint32_t ch = 0; ch < channels_; ++ch) {
            data_[static_cast<size_t>(ch) * capacity_ + slot] = frame[ch];
        }
        ++end_;
        return true;
    }

    uint32_t pop_planar(float* const* dst, uint32_t frames) noexcept {
        const uint32_t n = std::min(frames, size());
        for (uint32_t i = 0; i < n; ++i) {
            const size_t slot = slot_index(start_ + i);
            for (uint32_t ch = 0; ch < channels_; ++ch) {
                dst[ch][i] = data_[static_cast<size_t>(ch) * capacity_ + slot];
            }
        }
        discard_before(start_ + n);
        return n;
    }

    void discard_before(uint64_t absolute_index) noexcept {
        if (absolute_index <= start_) return;
        start_ = std::min(absolute_index, end_);
    }

private:
    // Preserve arbitrary-capacity behavior; only exact powers of two use the
    // mask. No capacity rounding, extra storage or floating-point change.
    size_t slot_index(uint64_t absolute_index) const noexcept {
        return static_cast<size_t>(mask_ ? (absolute_index & mask_) : (absolute_index % capacity_));
    }
    uint32_t mask_ = 0;
    uint32_t channels_ = 0;
    uint32_t capacity_ = 0;
    uint64_t start_ = 0;
    uint64_t end_ = 0;
    std::vector<float> data_;
};

class Engine {
    friend struct EngineCorrelationTest; // Internal numerical regression, not an installed API.
public:
    explicit Engine(const boiledegg_config& config);

    boiledegg_result reset() noexcept;
    boiledegg_result set_time_ratio(float ratio) noexcept;
    boiledegg_result set_pitch_ratio(float ratio) noexcept;
    float time_ratio() const noexcept { return time_ratio_; }
    float pitch_ratio() const noexcept { return pitch_ratio_; }
    uint32_t available() const noexcept { return output_.size(); }
    uint32_t input_latency_frames() const noexcept { return window_ + search_; }
    bool drained() const noexcept { return flushing_ && output_.size() == 0 && produced_total_ >= target_output_frames_; }

    boiledegg_result push(const float* const* input, uint32_t frames, uint32_t& accepted) noexcept;
    boiledegg_result pull(float* const* output, uint32_t capacity, uint32_t& produced) noexcept;
    boiledegg_result flush() noexcept;

private:
    void process_available() noexcept;
    bool process_wsola_frame() noexcept;
    void process_resampler() noexcept;
    int64_t choose_candidate(int64_t expected) noexcept;
    float correlation(int64_t candidate) noexcept;
    void emit_first_frame(int64_t start) noexcept;
    void emit_overlap_frame(int64_t start) noexcept;
    bool feed_padding(uint32_t frames) noexcept;

    uint32_t sample_rate_ = 0;
    uint32_t channels_ = 0;
    uint32_t max_block_ = 0;
    uint32_t window_ = 0;
    uint32_t overlap_ = 0;
    uint32_t hop_ = 0;
    uint32_t search_ = 0;

    float time_ratio_ = 1.0f;
    float pitch_ratio_ = 1.0f;

    PlanarRing input_;
    PlanarRing intermediate_;
    PlanarRing output_;

    std::vector<float> prev_tail_;     // channels * overlap
    std::vector<float> emit_scratch_;  // channels * hop
    // Immutable per-configuration coefficients, shared by all channels.
    std::vector<float> overlap_weights_; // overlap, computed only at construction
    // Construction-only scratch. Cached channel means retain the original
    // double arithmetic and candidate/stride accumulation order.
    std::vector<double> correlation_tail_, correlation_input_;
    double correlation_tail_energy_ = 1e-12;
    int64_t correlation_start_ = 0;
    std::vector<float> sample_scratch_;// channels
    std::vector<float> zero_scratch_;  // channels * max_block
    std::vector<const float*> zero_ptrs_;

    bool have_prev_ = false;
    bool flushing_ = false;
    bool flush_padding_done_ = false;
    double next_expected_ = 0.0;
    int64_t last_start_ = 0;

    double resample_pos_ = 0.0;
    uint64_t input_total_ = 0;
    uint64_t produced_total_ = 0;
    double target_output_accum_ = 0.0;
    uint64_t target_output_frames_ = std::numeric_limits<uint64_t>::max();
};

} // namespace boiled_egg::detail
