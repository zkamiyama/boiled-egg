#include <boiled_egg/boiled_egg.hpp>
#include <type_traits>
#include <utility>
static_assert(!std::is_copy_constructible_v<boiled_egg::engine>);
static_assert(std::is_nothrow_move_constructible_v<boiled_egg::engine>);
int main() { try {
    auto c=boiledegg_default_config(48000,1);c.max_block_size=64;
    auto b=boiledegg_default_backend_config();b.io_contract=BOILEDEGG_IO_REALTIME;
    if(EXPECT_SPECTRAL) {b.backend_id=1;b.flags=1;b.formant_policy=2;}
    boiled_egg::engine original(c,b);auto engine=std::move(original);
    float x[64]{};const float* in[]={x};float* out[]={x};
    if(EXPECT_SPECTRAL)engine.set_formant_semitones(-3.f);
    auto event=boiled_egg::parameter_event::formant_semitones(31,EXPECT_SPECTRAL?3.f:0.f);
    if(engine.process_realtime_nothrow(in,out,64,std::span(&event,1)))return 1;
    auto state=engine.backend_parameter_state();engine.set_backend_parameter_state(state);engine.reset();
    if(engine.backend_configuration().backend_id!=b.backend_id)return 2;
    return 0;
} catch(...) { return 3; } }
