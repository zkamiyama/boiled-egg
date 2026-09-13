// Research-only documented REAPER pitch API; host/SDK binaries not redistributed.
#define read_wav reaper_sdk_unused_read_wav
#include "reaper_plugin.h"
#undef read_wav
#include "wav.hpp"
#include <algorithm>
#include <cstdlib>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <memory>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>
namespace {
reaper_plugin_info_t* host{};
IReaperPitchShift* (*create_shift)(int){};
bool (*enum_mode)(int,const char**){};
const char* (*enum_sub)(int,int){};
const char* (*app_version)(){};
std::filesystem::path root;
template<class T> constexpr bool has_flush=requires(T& x){x.FlushSamples();};
template<class T> void flush(T* sh) {
    if constexpr(has_flush<T>)sh->FlushSamples();
    else throw std::runtime_error("compiled SDK lacks documented FlushSamples; rendering refused, discovery only");
}
std::vector<std::string> split(const std::string& s) {
    std::vector<std::string> v;std::stringstream f(s);std::string x;
    while(std::getline(f,x,'\t'))v.push_back(x);return v;
}
void render(const std::vector<std::string>& v,std::ofstream& report) {
    if(v.size()!=8)throw std::runtime_error("job must have 8 TSV fields");
    const int mode=std::stoi(v[3]),sub=std::stoi(v[4]);
    const double pitch=std::stod(v[5]),time=std::stod(v[6]),formant=std::stod(v[7]);
    if(!(pitch>=.5&&pitch<=2&&time>=.5&&time<=2&&formant>=.5&&formant<=2))throw std::runtime_error("invalid ratio");
    const char* name=nullptr;if(!enum_mode(mode,&name)||!name)throw std::runtime_error("mode unavailable");
    const char* subname=enum_sub(mode,sub);
    std::unique_ptr<IReaperPitchShift> sh(create_shift(REAPER_PITCHSHIFT_API_VER));
    if(!sh)throw std::runtime_error("native shift API unavailable");
    const auto src=read_wav(v[1]);const size_t frames=src.interleaved.size()/src.channels;
    sh->set_srate(src.sample_rate);sh->set_nch(src.channels);sh->SetQualityParameter((mode<<16)|sub);
    sh->set_shift(pitch);sh->set_tempo(1/time);sh->set_formant_shift(formant);sh->Reset();
    std::vector<ReaSample> scratch(8192*src.channels);std::vector<float> out;
    auto drain=[&]{for(unsigned guard=0;guard<100000;++guard){
        int n=sh->GetSamples(8192,scratch.data());if(n<0||n>8192)throw std::runtime_error("invalid native output count");
        if(!n)return;for(size_t i=0;i<size_t(n)*src.channels;++i)out.push_back(static_cast<float>(scratch[i]));
    }throw std::runtime_error("native drain did not terminate");};
    for(size_t pos=0;pos<frames;pos+=256){
        int n=static_cast<int>(std::min<size_t>(256,frames-pos));auto* in=sh->GetBuffer(n);
        if(!in)throw std::runtime_error("native GetBuffer failed");
        for(size_t i=0;i<size_t(n)*src.channels;++i)in[i]=src.interleaved[pos*src.channels+i];
        sh->BufferDone(n);drain();
    }
    flush(sh.get());drain();
    std::filesystem::create_directories(std::filesystem::path(v[2]).parent_path());
    write_wav_float32(v[2],wav_audio{src.sample_rate,src.channels,std::move(out)});
    const auto info=read_wav(v[2]);
    report<<v[0]<<'\t'<<name<<'\t'<<(subname?subname:"")<<'\t'<<mode<<'\t'<<sub<<'\t'<<std::setprecision(17)
          <<pitch<<'\t'<<time<<'\t'<<formant<<'\t'<<frames<<'\t'<<info.interleaved.size()/src.channels<<'\n';report.flush();
}
void timer(){
    host->Register("-timer",reinterpret_cast<void*>(timer));
    try{
        std::filesystem::create_directories(root);
        std::ofstream(root/"api-capabilities.txt")<<"api_version="<<REAPER_PITCHSHIFT_API_VER<<"\nhas_flush="<<has_flush<IReaperPitchShift><<'\n';
        std::ofstream modes(root/"modes.tsv");modes<<"mode\tsubmode\tengine\tsetting\n";
        for(int i=0;i<128;++i){const char* name=nullptr;if(!enum_mode(i,&name))break;if(!name)continue;
            modes<<i<<"\t-1\t"<<name<<"\t\n";
            for(int j=0;j<1024;++j){const char* sub=enum_sub(i,j);if(!sub)break;modes<<i<<'\t'<<j<<'\t'<<name<<'\t'<<sub<<'\n';}}
        modes.close();std::ofstream(root/"host-version.txt")<<app_version()<<'\n';
        const char* jobs=std::getenv("BOILED_NATIVE_JOBS");if(jobs&&*jobs){
            std::ifstream in(jobs);if(!in)throw std::runtime_error("jobs file absent");
            std::ofstream report(root/"native-renders.tsv");report<<"id\tengine\tsetting\tmode\tsubmode\tpitch_ratio\ttime_ratio\tformant_ratio\tinput_frames\toutput_frames\n";
            std::string line;while(std::getline(in,line)){if(line.empty()||line[0]=='#')continue;render(split(line),report);}}
        std::ofstream(root/"DONE.txt")<<"native host API completed\n";
    }catch(const std::exception& e){std::ofstream(root/"ERROR.txt")<<e.what()<<'\n';}
}
}
extern "C" REAPER_PLUGIN_DLL_EXPORT int REAPER_PLUGIN_ENTRYPOINT(REAPER_PLUGIN_HINSTANCE,reaper_plugin_info_t* rec){
    if(!rec)return 0;const char* dest=std::getenv("BOILED_NATIVE_DIR");if(!dest||!*dest)return 0;
    if(rec->caller_version!=REAPER_PLUGIN_VERSION)return 0;host=rec;root=dest;
    create_shift=reinterpret_cast<decltype(create_shift)>(rec->GetFunc("ReaperGetPitchShiftAPI"));
    enum_mode=reinterpret_cast<decltype(enum_mode)>(rec->GetFunc("EnumPitchShiftModes"));
    enum_sub=reinterpret_cast<decltype(enum_sub)>(rec->GetFunc("EnumPitchShiftSubModes"));
    app_version=reinterpret_cast<decltype(app_version)>(rec->GetFunc("GetAppVersion"));
    if(!create_shift||!enum_mode||!enum_sub||!app_version)return 0;
    rec->Register("timer",reinterpret_cast<void*>(timer));return 1;
}
