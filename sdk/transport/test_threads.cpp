// One owner per handle, including concurrent first construction of shared tables.
#include "transport.hpp"
#include <array>
#include <cmath>
#include <exception>
#include <iostream>
#include <latch>
#include <thread>
#include <vector>
struct Result { std::vector<float> audio; be_transport_info info{}; };
static Result run(unsigned index) {
    const unsigned rate=index<6?48000:96000;
    auto config=be_transport_default_config(rate,2);config.mode=index%6;
    config.formant_policy=config.mode<3?index%3:0;config.max_block_frames=257;
    std::vector<float> pcm(rate*2);
    for(unsigned i=0;i<rate;++i){
        const double t=double(i)/rate;
        pcm[2*i]=float(.1*std::cos(6.283185307179586*(137*t+75*t*t)));
        pcm[2*i+1]=float(.08*std::sin(6.283185307179586*419*t));
    }
    boiled_egg::file_transport h(config,pcm);h.seek(rate/4);
    Result result;result.audio.resize(16001*2);
    const std::array<be_transport_event,3> events{{{1024,BE_T_SPEED,0,0,0},
        {2048,BE_T_PITCH_SEMITONES,2000,0,7},{8192,BE_T_SPEED,1024,0,.5}}};
    unsigned next=0;
    for(unsigned offset=0;offset<16001;){
        const unsigned n=std::min(257U,16001-offset);
        std::array<be_transport_event,3> batch{};unsigned count=0;
        while(next<events.size() && events[next].offset<offset+n){
            batch[count]=events[next++];batch[count++].offset-=offset;
        }
        h.render(std::span(result.audio).subspan(offset*2,n*2),std::span(batch.data(),count));
        offset+=n;
    }
    result.info=h.info();return result;
}
int main(){
    constexpr unsigned count=12;
    std::array<Result,count> parallel{};std::array<std::exception_ptr,count> errors{};
    std::latch start(count);std::vector<std::jthread> threads;
    for(unsigned i=0;i<count;++i)threads.emplace_back([&,i]{
        start.arrive_and_wait();try{parallel[i]=run(i);}catch(...){errors[i]=std::current_exception();}
    });
    threads.clear();
    try{
        for(unsigned i=0;i<count;++i){
            if(errors[i])std::rethrow_exception(errors[i]);
            const auto reference=run(i);const auto& actual=parallel[i];
            if(actual.audio!=reference.audio || actual.info.source_position!=reference.info.source_position
                || actual.info.output_frames!=reference.info.output_frames
                || actual.info.owned_bytes!=reference.info.owned_bytes)
                throw std::runtime_error("Independent-owner parallel replay changed");
            double energy=0;for(float v:actual.audio){if(!std::isfinite(v))throw std::runtime_error("nonfinite");energy+=double(v)*v;}
            if(energy<1e-8)throw std::runtime_error("silent false pass");
        }
        std::cout<<count<<" concurrent first-construction / independent-owner histories exactly match sequential replay\n";
    }catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}
}
