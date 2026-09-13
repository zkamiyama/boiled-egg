#ifndef BOILED_EGG_FORMANT_LAB_COMMON_HPP
#define BOILED_EGG_FORMANT_LAB_COMMON_HPP
#include "boiled_egg_research_host.h"
#include <array>
#include <atomic>
#include <bit>
#include <cmath>
#include <cstdint>
namespace boiled_egg::lab {
constexpr std::uint32_t parameter_id=0x42454601U;
constexpr std::uint32_t state_magic=0x42464C42U; // BFLB, distinct from the product
constexpr unsigned max_events=BOILEDEGG_RESEARCH_HOST_MAX_EVENTS;
inline bool valid_semitones(double st) noexcept { return std::isfinite(st)&&st>=-12.&&st<=12.; }
inline float to_ratio(double st) noexcept { return std::exp2(static_cast<float>(st)/12.F); }
inline bool valid_rate(double r) noexcept {return std::isfinite(r)&&r>=16000.&&r<=384000.&&std::floor(r)==r;}
inline unsigned scale(unsigned rate) noexcept {unsigned s=1;while(rate>48000U*s)s*=2;return s;}
// Fuzzy profile, time/pitch fixed at 1; mirrors the validated core contract.
inline unsigned latency(unsigned rate) noexcept {return (2560U*scale(rate)+128U+31U)&~31U;}
inline unsigned tail(unsigned rate) noexcept {return latency(rate)+4352U*scale(rate);}
struct target {
    static_assert(std::atomic<std::uint32_t>::is_always_lock_free);
    std::atomic<std::uint32_t> value{std::bit_cast<std::uint32_t>(0.F)}, pending{0};
    float get() const noexcept {return std::bit_cast<float>(value.load(std::memory_order_acquire));}
    bool request(double st) noexcept {
        if(!valid_semitones(st))return false;
        auto bits=std::bit_cast<std::uint32_t>(static_cast<float>(st));
        value.store(bits,std::memory_order_release);
        // Ratio is positive, making zero an unambiguous empty mailbox.
        pending.store(std::bit_cast<std::uint32_t>(to_ratio(st)),std::memory_order_release);return true;
    }
    void observed(float st) noexcept {value.store(std::bit_cast<std::uint32_t>(st),std::memory_order_release);}
    bool consume(boiledegg_research_host_handle* core) noexcept {
        auto bits=pending.exchange(0,std::memory_order_acq_rel);
        return !bits||boiledegg_research_host_request_formant(core,std::bit_cast<float>(bits))==BOILEDEGG_RESEARCH_PV_RT_OK;
    }
};
inline std::array<std::uint8_t,16> save(float st) noexcept {
    std::array<std::uint8_t,16> bytes{};
    const std::uint32_t words[]={state_magic,1U,std::bit_cast<std::uint32_t>(st),0U};
    for(unsigned i=0;i<4;++i)for(unsigned j=0;j<4;++j)bytes[i*4+j]=static_cast<std::uint8_t>(words[i]>>(8*j));
    return bytes;
}
inline bool load(const std::array<std::uint8_t,16>& bytes,float& st) noexcept {
    std::uint32_t words[4]{};
    for(unsigned i=0;i<4;++i)for(unsigned j=0;j<4;++j)words[i]|=std::uint32_t(bytes[i*4+j])<<(8*j);
    st=std::bit_cast<float>(words[2]);
    return words[0]==state_magic&&words[1]==1&&words[3]==0&&valid_semitones(st);
}
}
#endif
