#include <boiled_egg/boiled_egg.hpp>
#include <array>
#include <cmath>
#include <cstring>
#include <iostream>
#include <limits>
#include <stdexcept>
#include <vector>
static void check(bool ok,const char* why) { if(!ok)throw std::runtime_error(why); }
static std::vector<float> render(boiled_egg::engine& e) {
    std::array<float,64> in{},out{};const float* ip[]={in.data()};float* op[]={out.data()};
    std::vector<float> y;
    auto drain=[&]{while(e.available()){const auto n=e.pull(op,64);check(n>0,"progress");y.insert(y.end(),out.begin(),out.begin()+n);}};
    for(unsigned i=0;i<190;++i){for(unsigned n=0;n<64;++n)in[n]=.2f*std::sin(.049f*float(i*64+n));unsigned p=0;
        while(p<64){const float* src[]={in.data()+p};const auto n=e.push(src,64-p);p+=n;drain();check(n>0,"input progress");}}
    e.flush();for(unsigned i=0;i<10000&&!e.drained();++i)drain();drain();check(e.drained(),"drain completes");return y;
}
int main(){try{
    auto c=boiledegg_default_config(48000,1);c.max_block_size=64;
    auto b=boiledegg_default_backend_config();
    boiledegg_backend_info info{};info.struct_size=sizeof(info);
    check(boiledegg_query_backend(0,&info)==BOILEDEGG_OK && info.status==BOILEDEGG_BACKEND_STABLE,"WSOLA available");
    check(info.formant_policy_mask==1 && (info.feature_flags&BOILEDEGG_BACKEND_DYNAMIC_PITCH),"truthful features");
    check(boiledegg_query_backend(1,&info)==BOILEDEGG_OK,"known spectral ID");
    if(info.status==BOILEDEGG_BACKEND_UNAVAILABLE)check(!info.feature_flags && !info.quality_mode_mask,"absent backend not advertised");
    auto before=info;check(boiledegg_query_backend(123,&info)==BOILEDEGG_INVALID_ARGUMENT,"unknown ID");
    check(!std::memcmp(&info,&before,sizeof(info)),"bad query no mutation");
    // Only a size prefix exists: catches accidental reads of later fields.
    uint32_t tiny=sizeof(uint32_t);
    check(boiledegg_validate_backend_config(reinterpret_cast<boiledegg_config*>(&tiny),&b)==BOILEDEGG_INVALID_ARGUMENT,"tiny audio");
    check(boiledegg_validate_backend_config(&c,reinterpret_cast<boiledegg_backend_config*>(&tiny))==BOILEDEGG_INVALID_ARGUMENT,"tiny backend");
    check(boiledegg_query_backend(0,reinterpret_cast<boiledegg_backend_info*>(&tiny))==BOILEDEGG_INVALID_ARGUMENT,"tiny output");
    check(boiledegg_validate_backend_config(nullptr,&b)==BOILEDEGG_INVALID_ARGUMENT,"null input");
    for(unsigned quality:{0u,1u,2u})for(float pitch:{.5f,1.f,2.f}) {
        b=boiledegg_default_backend_config();b.quality_mode=quality;b.initial_pitch_ratio=pitch;b.initial_time_ratio=1.25f;
        auto p=boiledegg_default_profile();p.quality_mode=quality;
        boiled_egg::engine old(c,p);old.set_pitch_ratio(pitch);old.set_time_ratio(1.25f);
        boiled_egg::engine selected(c,b);check(selected.backend_configuration().quality_mode==quality,"selection metadata");
        check(render(old)==render(selected),"legacy vs explicit selection samples differ");
        selected.reset();check(selected.pitch_ratio()==pitch && selected.time_ratio()==1.25f,"reset retains targets");
    }
    b=boiledegg_default_backend_config();
    for(unsigned policy:{1u,2u}){b.formant_policy=policy;
        check(boiledegg_validate_backend_config(&c,&b)==BOILEDEGG_UNSUPPORTED_MODE,"no silent formant fallback");}
    b=boiledegg_default_backend_config();b.quality_mode=BOILEDEGG_QUALITY_MONOPHONIC;
    check(boiledegg_validate_backend_config(&c,&b)==BOILEDEGG_UNSUPPORTED_MODE,"quality and formant policy differ");
    b=boiledegg_default_backend_config();b.flags=2;check(boiledegg_validate_backend_config(&c,&b)==BOILEDEGG_INVALID_ARGUMENT,"unknown flags");
    b.flags=0;b.reserved[1]=1;check(boiledegg_validate_backend_config(&c,&b)==BOILEDEGG_INVALID_ARGUMENT,"reserved");
    b.reserved[1]=0;b.version=2;check(boiledegg_validate_backend_config(&c,&b)==BOILEDEGG_INVALID_ARGUMENT,"unknown version");
    b.version=1;b.initial_pitch_ratio=std::numeric_limits<float>::quiet_NaN();
    check(boiledegg_validate_backend_config(&c,&b)==BOILEDEGG_INVALID_ARGUMENT,"nonfinite");
    b=boiledegg_default_backend_config(); b.io_contract=BOILEDEGG_IO_REALTIME;b.initial_time_ratio=2;
    check(boiledegg_validate_backend_config(&c,&b)==BOILEDEGG_UNSUPPORTED_MODE,"fixed IO requires time1");
    b.initial_time_ratio=1;boiled_egg::engine fixed(c,b);
    check(boiledegg_set_time_ratio(fixed.native_handle(),2)==BOILEDEGG_UNSUPPORTED_MODE,"fixed contract restricts pre-start setters");
    float x[64]{},y[64]{};const float* in[]={x};float* out[]={y};uint32_t accepted=0;
    check(boiledegg_push(fixed.native_handle(),in,64,&accepted)==BOILEDEGG_INVALID_STATE,"explicit fixed contract");
    check(fixed.process_realtime_nothrow(in,out,64)==BOILEDEGG_OK,"fixed works");
    b.io_contract=BOILEDEGG_IO_STREAMING;boiled_egg::engine stream(c,b);
    check(stream.process_realtime_nothrow(in,out,64)==BOILEDEGG_INVALID_STATE,"explicit streaming contract");
    stream.reset();check(stream.push(in,64)==64,"stream works after rejected mode");
    struct Extended {boiledegg_backend_config base;uint32_t tail[4];};
    Extended ext{boiledegg_default_backend_config(),{3,4,5,6}};ext.base.struct_size=sizeof(ext);
    boiled_egg::engine future(c,ext.base);
    check(boiledegg_get_backend_configuration(future.native_handle(),&ext.base)==BOILEDEGG_OK && ext.tail[0]==3 && ext.tail[3]==6,"tail preserved");
    auto legacy_profile=boiledegg_default_profile();legacy_profile.formant_mode=BOILEDEGG_FORMANT_PRESERVE;
    check(!boiledegg_profile_is_supported(&legacy_profile),"legacy unsupported stays unsupported");
    std::cout<<"backend inventory, strict validation, 9 exact routing comparisons, sized records and IO contracts passed\n";
}catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}}
