// Native engine discovery only. Ordinary licensed/evaluation REAPER, no bypass.
// This extension deliberately does not guess across SDK streaming API versions.
#define read_wav reaper_sdk_unused_read_wav
#include "reaper_plugin.h"
#undef read_wav
#include <cstdlib>
#include <filesystem>
#include <fstream>
#include <string>
namespace {
reaper_plugin_info_t* host{};
bool (*enum_mode)(int,const char**){};
const char* (*enum_sub)(int,int){};
const char* (*app_version)(){};
std::filesystem::path root;
void timer(){
    host->Register("-timer",reinterpret_cast<void*>(timer));
    std::filesystem::create_directories(root);
    std::ofstream modes(root/"modes.tsv");modes<<"mode\tsubmode\tengine\tsetting\n";
    for(int i=0;i<128;++i){const char* name=nullptr;if(!enum_mode(i,&name))break;if(!name)continue;
        modes<<i<<"\t-1\t"<<name<<"\t\n";
        for(int j=0;j<1024;++j){const char* sub=enum_sub(i,j);if(!sub)break;modes<<i<<'\t'<<j<<'\t'<<name<<'\t'<<sub<<'\n';}}
    modes.close();std::ofstream(root/"host-version.txt")<<app_version()<<'\n';
    std::ofstream(root/"api-capabilities.txt")<<"api_version="<<REAPER_PITCHSHIFT_API_VER<<"\nphase=discovery_only\n";
    std::ofstream(root/"DONE.txt")<<"Native mode discovery complete; no audio rendered\n";
}
}
extern "C" REAPER_PLUGIN_DLL_EXPORT int REAPER_PLUGIN_ENTRYPOINT(REAPER_PLUGIN_HINSTANCE,reaper_plugin_info_t* rec){
    if(!rec)return 0;const char* dest=std::getenv("BOILED_NATIVE_DIR");if(!dest||!*dest)return 0;
    if(rec->caller_version!=REAPER_PLUGIN_VERSION)return 0;host=rec;root=dest;
    enum_mode=reinterpret_cast<decltype(enum_mode)>(rec->GetFunc("EnumPitchShiftModes"));
    enum_sub=reinterpret_cast<decltype(enum_sub)>(rec->GetFunc("EnumPitchShiftSubModes"));
    app_version=reinterpret_cast<decltype(app_version)>(rec->GetFunc("GetAppVersion"));
    if(!enum_mode||!enum_sub||!app_version)return 0;
    rec->Register("timer",reinterpret_cast<void*>(timer));return 1;
}
