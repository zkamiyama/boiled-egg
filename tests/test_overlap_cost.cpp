#include "engine.hpp"
#include <array>
#include <bit>
#include <cfenv>
#include <iostream>
#include <random>
#include <stdexcept>

namespace boiled_egg::detail {
struct EngineOverlapCostTest {
    static void check(bool ok, const char* text) { if (!ok) throw std::runtime_error(text); }
    static bool same(float a, float b) { return std::bit_cast<uint32_t>(a)==std::bit_cast<uint32_t>(b); }
    static unsigned run() {
        check(std::fegetround()==FE_TONEAREST, "round-to-nearest test environment");
        std::mt19937 random(20260922);
        unsigned comparisons=0;
        for (unsigned channels : {1u,2u,8u,32u})
        for (unsigned window : {128u,130u,254u,258u,512u,1024u,1536u,2048u})
        for (unsigned extra : {0u,27u}) {
            const unsigned capacity=window*4+extra;
            boiledegg_config c{}; c.sample_rate=48000;c.channels=channels;c.max_block_size=64;
            c.window_frames=window;c.search_frames=window/8;c.fifo_frames=capacity;
            Engine engine(c);
            auto weights=engine.overlap_weights_;
            check(weights.size()==window/2, "one channel-independent cache");
            for (unsigned i=0;i<window/2;++i) {
                const float t=static_cast<float>(i)/static_cast<float>(window/2-1);
                const float w=.5f-.5f*std::cos(3.14159265358979323846f*t);
                check(same(w,weights[i]),"cached weight changed arithmetic");++comparisons;
            }
            for (unsigned cycle=0;cycle<2;++cycle) {
                engine.reset();
                check(engine.overlap_weights_==weights,"reset modified fixed coefficients");
                std::array<float,32> frame{};
                const unsigned frames=capacity*(cycle?2:0)+window*2+13;
                for (unsigned i=0;i<frames;++i) {
                    if (!engine.input_.free_space())engine.input_.discard_before(engine.input_.start_index()+1);
                    for (unsigned ch=0;ch<channels;++ch)
                        frame[ch]=static_cast<float>(static_cast<int>(random()%2049u)-1024)/2048.f;
                    check(engine.input_.push_one(frame.data()),"fixture ring full");
                }
                const auto begin=static_cast<int64_t>(engine.input_.start_index());
                const auto end=static_cast<int64_t>(engine.input_.end_index());
                for (int64_t start : {int64_t(-11),begin-3,begin+11,
                                     int64_t(capacity)-window/4, end-window-1,end-window/4}) {
                    engine.intermediate_.reset();
                    for (auto& x:engine.prev_tail_)
                        x=static_cast<float>(static_cast<int>(random()%2049u)-1024)/2048.f;
                    const auto original=engine.prev_tail_;
                    engine.emit_overlap_frame(start);
                    for (unsigned ch=0;ch<channels;++ch) for (unsigned i=0;i<window/2;++i) {
                        const float t=static_cast<float>(i)/static_cast<float>(window/2-1);
                        const float w=.5f-.5f*std::cos(3.14159265358979323846f*t);
                        const float cur=engine.input_.get(ch,start+i);
                        const float scalar=(1.f-w)*original[ch*(window/2)+i]+w*cur;
                        check(same(scalar,engine.intermediate_.get(ch,i)),"span or fade changed sample");
                        check(same(engine.prev_tail_[ch*(window/2)+i],engine.input_.get(ch,start+window/2+i)),"tail copy changed sample");
                        ++comparisons;
                    }
                }
            }
            engine.reset();
            // With no accepted input, the output limit blocks any work even
            // when internal coefficients exist. Never consume future output.
            std::array<float,32> one{};one.fill(.25f);
            for(unsigned i=0;i<window;++i)check(engine.intermediate_.push_one(one.data()),"intermediate fixture");
            engine.process_resampler();
            check(engine.produced_total_==0&&engine.resample_pos_==0&&engine.output_.size()==0,"empty budget advances state");
            engine.target_output_accum_=7;
            engine.process_resampler();
            check(engine.produced_total_==7&&engine.output_.size()==7,"published budget differs");
            auto pos=engine.resample_pos_;
            engine.process_resampler();
            check(engine.resample_pos_==pos&&engine.output_.size()==7,"blocked budget advances twice");
        }
        return comparisons;
    }
};
}
int main() {try {
    std::cout<<boiled_egg::detail::EngineOverlapCostTest::run()<<" exact weight/PCM comparisons; blocked-budget and reset checks passed\n";
    return 0;
} catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}}
