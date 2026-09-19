#ifndef BOILED_EGG_FILE_TRANSPORT_HPP
#define BOILED_EGG_FILE_TRANSPORT_HPP
#include "transport.h"
#include <span>
#include <stdexcept>
#include <utility>
namespace boiled_egg {
/* Single-owner RAII wrapper for the separate experimental transport module. */
class file_transport {
    be_transport* handle_{};
    uint32_t channels_{};
    static void checked(int code) { if(code!=BE_T_OK)throw std::runtime_error("native file transport error"); }
public:
    file_transport(be_transport_config config, std::span<const float> pcm):channels_(config.channels) {
        if(!channels_ || pcm.size()%channels_)throw std::invalid_argument("interleaved source shape");
        int result{};handle_=be_transport_create(&config,pcm.data(),pcm.size()/channels_,&result);
        checked(result);
    }
    ~file_transport(){be_transport_destroy(handle_);}
    file_transport(const file_transport&)=delete;
    file_transport& operator=(const file_transport&)=delete;
    file_transport(file_transport&& other) noexcept:handle_(std::exchange(other.handle_,nullptr)),channels_(other.channels_){}
    file_transport& operator=(file_transport&& other) noexcept {
        if(this!=&other){be_transport_destroy(handle_);handle_=std::exchange(other.handle_,nullptr);channels_=other.channels_;}return *this;
    }
    int render_nothrow(std::span<float> output,std::span<const be_transport_event> events={}) noexcept {
        if(!handle_ || output.size()%channels_ || output.size()/channels_>8192 || events.size()>4096)return BE_T_INVALID;
        return be_transport_render(handle_,output.data(),static_cast<uint32_t>(output.size()/channels_),events.data(),static_cast<uint32_t>(events.size()));
    }
    void render(std::span<float> output,std::span<const be_transport_event> events={}){checked(render_nothrow(output,events));}
    void seek(double frame){checked(be_transport_seek(handle_,frame));}
    be_transport_info info() const {be_transport_info value{};value.struct_size=sizeof(value);checked(be_transport_get_info(handle_,&value));return value;}
};
}
#endif
