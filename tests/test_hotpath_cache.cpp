#include "engine.hpp"
#include <array>
#include <bit>
#include <iostream>
#include <random>
#include <stdexcept>

namespace boiled_egg::detail {
static void require(bool value, const char* reason) {
    if (!value) throw std::runtime_error(reason);
}

struct EngineCorrelationTest {
    static float original(Engine& engine, int64_t candidate) {
        double dot = 0.0, aa = 1e-12, bb = 1e-12;
        const uint32_t stride = engine.sample_rate_ >= 88200 ? 8u : 2u;
        for (uint32_t i = 0; i < engine.overlap_; i += stride) {
            double a = 0.0, b = 0.0;
            for (uint32_t ch = 0; ch < engine.channels_; ++ch) {
                a += engine.prev_tail_[static_cast<size_t>(ch)*engine.overlap_ + i];
                b += engine.input_.get(ch, candidate + i);
            }
            a /= engine.channels_; b /= engine.channels_;
            dot += a*b; aa += a*a; bb += b*b;
        }
        return static_cast<float>(dot / std::sqrt(aa*bb));
    }
    static unsigned overlap_checks() {
        std::mt19937 rng(20260922); unsigned compared=0;
        for(unsigned channels : {1u,2u,8u}) for(unsigned window : {128u,256u,512u,1536u,2048u,8192u})
        for(unsigned offset : {0u,32700u}) {
            boiledegg_config c{}; c.sample_rate=48000;c.channels=channels;c.max_block_size=64;
            c.window_frames=window;c.search_frames=window/8;c.fifo_frames=32771;
            Engine engine(c); const auto weights=engine.overlap_weights_;
            require(weights.size()==window/2,"wrong overlap cache size");
            for(unsigned cycle=0;cycle<2;++cycle) {
                engine.reset(); require(engine.overlap_weights_==weights,"reset changed immutable cache");
                std::array<float,8> frame{};
                for(unsigned i=0;i<offset+window;++i) {
                    if(!engine.input_.free_space())engine.input_.discard_before(engine.input_.start_index()+1);
                    for(unsigned ch=0;ch<channels;++ch)frame[ch]=static_cast<float>(static_cast<int>(rng()%2049u)-1024)/2048.f;
                    require(engine.input_.push_one(frame.data()),"overlap input fixture");
                }
                for(auto& v:engine.prev_tail_)v=static_cast<float>(static_cast<int>(rng()%2049u)-1024)/2048.f;
                auto expected=engine.prev_tail_;
                for(unsigned ch=0;ch<channels;++ch)for(unsigned i=0;i<engine.overlap_;++i) {
                    const float t=engine.overlap_>1?static_cast<float>(i)/static_cast<float>(engine.overlap_-1u):1.0f;
                    const float w=0.5f-0.5f*std::cos(3.14159265358979323846f*t);
                    require(std::bit_cast<uint32_t>(w)==std::bit_cast<uint32_t>(weights[i]),"cached overlap coefficient differs");
                    const auto k=static_cast<size_t>(ch)*engine.overlap_+i;
                    expected[k]=(1.0f-w)*engine.prev_tail_[k]+w*engine.input_.get(ch,offset+i);
                }
                engine.emit_overlap_frame(offset);
                for(unsigned ch=0;ch<channels;++ch)for(unsigned i=0;i<engine.overlap_;++i) {
                    const auto k=static_cast<size_t>(ch)*engine.overlap_+i;
                    require(std::bit_cast<uint32_t>(expected[k])==std::bit_cast<uint32_t>(engine.intermediate_.get(ch,i)),"cached overlap changed PCM");
                    require(engine.prev_tail_[k]==engine.input_.get(ch,offset+engine.hop_+i),"cached overlap changed tail");
                    ++compared;
                }
            }
        }
        return compared;
    }
    static unsigned run() {
        std::mt19937 rng(20260914); unsigned compared = 0;
        for (unsigned rate : {48000u, 96000u}) for (unsigned channels : {1u,2u,8u})
        for (unsigned window : {128u,512u,1536u}) for (unsigned capacity : {16384u,16411u}) {
            boiledegg_config c{}; c.sample_rate=rate; c.channels=channels; c.max_block_size=64;
            c.window_frames=window; c.search_frames=window/8; c.fifo_frames=capacity;
            Engine engine(c); engine.set_pitch_ratio(.5f);
            for (unsigned cycle=0; cycle<3; ++cycle) {
                engine.reset();
                const auto frames=2u*capacity + 31u + cycle*997u;
                std::array<float,8> frame{};
                for (unsigned i=0; i<frames; ++i) {
                    if (!engine.input_.free_space()) engine.input_.discard_before(engine.input_.start_index()+1);
                    for (unsigned ch=0; ch<channels; ++ch) {
                        frame[ch]=static_cast<float>(static_cast<int>(rng()%2001u)-1000)/1024.f;
                        if (cycle==1 && ch%2) frame[ch]=-frame[ch-1];
                        if (cycle==2) frame[ch]=0.f;
                    }
                    require(engine.input_.push_one(frame.data()), "fixture ring push");
                }
                for (auto& value : engine.prev_tail_)
                    value=cycle==2 ? 0.f : static_cast<float>(static_cast<int>(rng()%2001u)-1000)/1024.f;
                const auto before=engine.prev_tail_;
                const int64_t expected=static_cast<int64_t>(engine.input_.end_index())-window-c.search_frames-3;
                const int64_t low=expected-c.search_frames, high=expected+c.search_frames;
                const int64_t coarse=rate>=88200 ? 8 : 4;
                float best_score=-std::numeric_limits<float>::infinity(); auto best=low;
                for (auto at=low; at<=high; at+=coarse) {
                    const auto value=original(engine,at);
                    if (value>best_score) {best_score=value;best=at;}
                }
                const auto begin=std::max(low,best-coarse+1), end=std::min(high,best+coarse-1);
                for (auto at=begin; at<=end; ++at) {
                    const auto value=original(engine,at);
                    if (value>best_score) {best_score=value;best=at;}
                }
                require(engine.choose_candidate(expected)==best,"cached search changed selected offset");
                for (auto at=low; at<=high; ++at) {
                    require(std::bit_cast<uint32_t>(engine.correlation(at))==std::bit_cast<uint32_t>(original(engine,at)),
                            "cached score changed floating-point result");
                    ++compared;
                }
                require(engine.prev_tail_==before,"correlation changed tail");
            }
        }
        return compared;
    }
};

static unsigned test_ring_spans() {
    unsigned comparisons=0;
    for (unsigned capacity : {8u,9u,32u,33u,127u,128u}) {
        PlanarRing ring(2,capacity);
        std::array<float,2> frame{};
        for (unsigned i=0; i<capacity*5; ++i) {
            if (!ring.free_space()) ring.discard_before(ring.start_index()+1);
            frame={static_cast<float>(i),-static_cast<float>(i)};
            require(ring.push_one(frame.data()),"ring push");
            for (unsigned ch=0; ch<3; ++ch) for (int64_t start=static_cast<int64_t>(ring.start_index())-2;
                 start<=static_cast<int64_t>(ring.end_index())+2; ++start) {
                const auto value=ring.get(ch,start);
                const float expected=ch<2 && start>=static_cast<int64_t>(ring.start_index()) && start<static_cast<int64_t>(ring.end_index())
                    ? (ch ? -static_cast<float>(start) : static_cast<float>(start)) : 0.f;
                require(value==expected,"ring modulo behavior changed");
                for (unsigned length : {1u,4u,40u}) {
                    const float* span=ring.contiguous(ch,start,length);
                    const bool readable=ch<2 && start>=0 && static_cast<uint64_t>(start)>=ring.start_index()
                        && static_cast<uint64_t>(start)<=ring.end_index()
                        && length<=ring.end_index()-static_cast<uint64_t>(start)
                        && length<=capacity-static_cast<uint64_t>(start)%capacity;
                    require((span!=nullptr)==readable,"invalid borrowed span");
                    if (span) for (unsigned j=0;j<length;++j)
                        require(span[j]==ring.get(ch,start+j),"span differs from scalar sample");
                    ++comparisons;
                }
            }
        }
        ring.reset();require(ring.size()==0 && !ring.contiguous(0,0,1),"reset span");
    }
    return comparisons;
}
} // namespace boiled_egg::detail

int main() {
    try {
        const auto spans=boiled_egg::detail::test_ring_spans();
        const auto scores=boiled_egg::detail::EngineCorrelationTest::run();
        const auto overlap=boiled_egg::detail::EngineCorrelationTest::overlap_checks();
        std::cout<<overlap<<" bit-identical overlap samples and immutable cache checks\n";
        std::cout<<spans<<" ring/span cases; "<<scores<<" bit-identical correlation scores and search choices\n";
    } catch(const std::exception& error) { std::cerr<<error.what()<<'\n'; return 1; }
}
