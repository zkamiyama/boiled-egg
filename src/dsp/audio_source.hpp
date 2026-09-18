#ifndef BOILED_EGG_DSP_AUDIO_SOURCE_HPP
#define BOILED_EGG_DSP_AUDIO_SOURCE_HPP
#include <algorithm>
#include <cmath>
#include <cstdint>
#include <limits>
#include <span>
#include <stdexcept>
#include <vector>

namespace boiled_egg::dsp {
// Internal, single-owner source contract. A view expires on mutation/destruction
// of its owner. A missing live sample must not masquerade as known zero padding.
enum class sample_state { ready, padding, future, expired, outside_capture, invalid };
struct source_sample {
    float value{};
    sample_state state{sample_state::invalid};
    [[nodiscard]] bool available() const noexcept {
        return state == sample_state::ready || state == sample_state::padding;
    }
};
class prepared_source;
class rolling_source;
class captured_source;
class source_view {
    friend class prepared_source;
    friend class rolling_source;
    friend class captured_source;
    enum class kind { file, rolling, capture };
    std::span<const float> data_;
    std::int64_t first_{}, end_{};
    std::size_t capacity_{};
    unsigned channels_{};
    kind kind_{kind::capture};
    source_view(std::span<const float> data, std::int64_t first, std::int64_t end,
                unsigned channels, kind type) noexcept
        : data_(data), first_(first), end_(end), capacity_(data.size()/channels),
          channels_(channels), kind_(type) {}
public:
    source_view() = default;
    [[nodiscard]] unsigned channels() const noexcept { return channels_; }
    [[nodiscard]] std::int64_t first() const noexcept { return first_; }
    [[nodiscard]] std::int64_t end() const noexcept { return end_; }
    [[nodiscard]] source_sample read(std::int64_t frame, unsigned channel) const noexcept {
        if(channel >= channels_) return {};
        if(kind_ == kind::file && (frame < 0 || frame >= end_))
            return {0.F, sample_state::padding};
        if(kind_ == kind::rolling && frame < 0)
            return {0.F, sample_state::padding}; // known before-start boundary only
        if(frame < first_) return {0.F, kind_ == kind::capture
            ? sample_state::outside_capture : sample_state::expired};
        if(frame >= end_) return {0.F, kind_ == kind::capture
            ? sample_state::outside_capture : sample_state::future};
        const auto slot = kind_ == kind::rolling
            ? static_cast<std::uint64_t>(frame) % capacity_
            : static_cast<std::uint64_t>(frame-first_);
        return {data_[static_cast<std::size_t>(slot)*channels_+channel], sample_state::ready};
    }
};
inline std::size_t source_storage_size(std::size_t frames, unsigned channels) {
    if(!channels || channels > 8 || frames > std::numeric_limits<std::size_t>::max()/channels
       || frames > static_cast<std::uint64_t>(std::numeric_limits<std::int64_t>::max()))
        throw std::invalid_argument("source dimensions");
    return frames*channels;
}
class prepared_source {
    unsigned channels_;
    std::vector<float> samples_;
public:
    prepared_source(std::span<const float> pcm, unsigned channels) : channels_(channels) {
        if(!channels || channels>8 || pcm.size()%channels)
            throw std::invalid_argument("source interleaving");
        source_storage_size(pcm.size()/channels,channels);
        for(float value:pcm) if(!std::isfinite(value)) throw std::invalid_argument("nonfinite source");
        samples_.assign(pcm.begin(),pcm.end());
    }
    [[nodiscard]] source_view view() const noexcept {
        return {samples_,0,static_cast<std::int64_t>(samples_.size()/channels_),channels_,source_view::kind::file};
    }
    [[nodiscard]] std::size_t owned_bytes() const noexcept { return samples_.capacity()*sizeof(float); }
};
enum class source_write_status { ok, invalid, clock_overflow, missing_range };
struct source_write_result {
    source_write_status status{source_write_status::invalid};
    std::uint64_t accepted{}, discarded{};
};
class rolling_source {
    unsigned channels_;
    std::size_t capacity_;
    std::vector<float> samples_;
    std::int64_t end_{};
    std::uint64_t discarded_{};
public:
    rolling_source(std::size_t frames, unsigned channels)
        : channels_(channels), capacity_(frames), samples_(source_storage_size(frames,channels)) {
        if(!frames) throw std::invalid_argument("zero rolling capacity");
    }
    // Entire supplied batch is validated first. Oversized batches retain only
    // their newest capacity frames, reporting both old and new discarded data.
    [[nodiscard]] source_write_result append(std::span<const float> pcm) noexcept {
        if(pcm.size()%channels_) return {};
        const auto count=pcm.size()/channels_;
        if(count > static_cast<std::uint64_t>(std::numeric_limits<std::int64_t>::max()-end_))
            return {source_write_status::clock_overflow,0,0};
        for(float value:pcm) if(!std::isfinite(value)) return {};
        const auto next=end_+static_cast<std::int64_t>(count);
        const auto old_first=std::max<std::int64_t>(0,end_-static_cast<std::int64_t>(capacity_));
        const auto new_first=std::max<std::int64_t>(0,next-static_cast<std::int64_t>(capacity_));
        const auto skip=count>capacity_?count-capacity_:0;
        for(std::size_t i=skip;i<count;++i) {
            const auto slot=(static_cast<std::uint64_t>(end_)+i)%capacity_;
            std::copy_n(pcm.data()+i*channels_,channels_,samples_.data()+slot*channels_);
        }
        const auto dropped=static_cast<std::uint64_t>(new_first-old_first);
        end_=next;discarded_+=dropped;
        return {source_write_status::ok,count,dropped};
    }
    [[nodiscard]] source_view view() const noexcept {
        return {samples_,std::max<std::int64_t>(0,end_-static_cast<std::int64_t>(capacity_)),
                end_,channels_,source_view::kind::rolling};
    }
    void reset() noexcept { end_=0;discarded_=0; } // old storage becomes inaccessible
    [[nodiscard]] std::uint64_t discarded_frames() const noexcept { return discarded_; }
    [[nodiscard]] std::size_t owned_bytes() const noexcept { return samples_.capacity()*sizeof(float); }
};
class captured_source {
    unsigned channels_;
    std::vector<float> samples_;
    std::int64_t first_{}, end_{};
public:
    captured_source(std::size_t frames, unsigned channels)
        : channels_(channels), samples_(source_storage_size(frames,channels)) {
        if(!frames) throw std::invalid_argument("zero capture capacity");
    }
    // Captures a nonnegative absolute range. Callers choose how startup padding
    // is placed. No resizing, and a failed capture keeps the previous capture.
    [[nodiscard]] source_write_status capture(source_view input, std::int64_t first,
                                              std::size_t frames) noexcept {
        if(input.channels()!=channels_ || first<0 || !frames || frames>samples_.size()/channels_
           || frames>static_cast<std::uint64_t>(std::numeric_limits<std::int64_t>::max()-first))
            return source_write_status::invalid;
        const auto end=first+static_cast<std::int64_t>(frames);
        for(auto at=first;at<end;++at)
            for(unsigned ch=0;ch<channels_;++ch)
                if(!input.read(at,ch).available()) return source_write_status::missing_range;
        // Views must remain stable over both passes (single audio owner).
        for(std::size_t i=0;i<frames;++i)
            for(unsigned ch=0;ch<channels_;++ch)
                samples_[i*channels_+ch]=input.read(first+static_cast<std::int64_t>(i),ch).value;
        first_=first;end_=end;
        return source_write_status::ok;
    }
    [[nodiscard]] source_view view() const noexcept {
        return {samples_,first_,end_,channels_,source_view::kind::capture};
    }
    [[nodiscard]] std::size_t owned_bytes() const noexcept { return samples_.capacity()*sizeof(float); }
};
}
#endif
