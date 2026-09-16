#ifndef BOILED_EGG_PLUGIN_PITCH_CONTROLS_HPP
#define BOILED_EGG_PLUGIN_PITCH_CONTROLS_HPP
#include <boiled_egg/backend.h>
#include <algorithm>
#include <array>
#include <atomic>
#include <bit>
#include <cmath>
#include <cstdint>
#include <span>

namespace boiled_egg::plugin {
// Pitch index/CLAP ID/VST3 ID and normalization are kept from the old plugin.
enum Param:unsigned {Pitch,Fine,Formant,FormantFine,Wet,Dry,Volume,Pan,Bypass,Backend,Quality,Policy,Count};
struct Parameter {const char* name;const char* unit;float min,max,initial;bool stepped,automatable;};
inline constexpr std::array<Parameter,Count> parameters{{
 {"Pitch","st",-24,24,0,false,true},{"Fine tune","cents",-100,100,0,false,true},
 {"Formant","st",-12,12,0,false,true},{"Formant fine","cents",-100,100,0,false,true},
 {"Wet","",0,1,1,false,true},{"Dry","",0,1,0,false,true},{"Voice volume","dB",-24,12,0,false,true},
 {"Pan","",-1,1,0,false,true},{"Bypass","",0,1,0,true,true},
 {"Algorithm","",0,1,0,true,false},{"Quality","",0,2,0,true,false},{"Formant policy","",0,2,0,true,false}}};
using Values=std::array<float,Count>;
inline Values defaults() noexcept {Values v{};for(unsigned i=0;i<Count;++i)v[i]=parameters[i].initial;return v;}
inline bool valid_value(unsigned i,float v) noexcept {return i<Count&&std::isfinite(v)&&v>=parameters[i].min&&v<=parameters[i].max&&(!parameters[i].stepped||v==std::floor(v));}
inline float total_pitch(const Values& v) noexcept {return v[Pitch]+v[Fine]*.01f;}
inline float total_formant(const Values& v) noexcept {return v[Formant]+v[FormantFine]*.01f;}
inline bool spectral_available() noexcept {boiledegg_backend_info i{};i.struct_size=sizeof(i);return boiledegg_query_backend(1,&i)==BOILEDEGG_OK&&i.status==BOILEDEGG_BACKEND_EXPERIMENTAL;}
inline bool valid_values(const Values& v) noexcept {
 for(unsigned i=0;i<Count;++i)if(!valid_value(i,v[i]))return false;
 const float pitch=total_pitch(v),formant=total_formant(v);
 if(v[Backend]==1)return spectral_available()&&v[Quality]<=1&&std::abs(pitch)<=12&&std::abs(formant)<=12&&(v[Policy]!=0||formant==0);
 return v[Policy]==0&&formant==0&&std::abs(pitch)<=24;
}
inline bool same_configuration(const Values& a,const Values& b) noexcept {return a[Backend]==b[Backend]&&a[Quality]==b[Quality]&&a[Policy]==b[Policy];}
inline double normalize(unsigned i,float v) noexcept {return (double(v)-parameters[i].min)/(parameters[i].max-parameters[i].min);}
inline float denormalize(unsigned i,double v) noexcept {return float(parameters[i].min+v*(parameters[i].max-parameters[i].min));}
inline std::uint32_t clap_param_id(unsigned i) noexcept {return 0x42450001u+i;}
inline std::uint32_t vst_id(unsigned i) noexcept {return 1000u+i;}
inline bool clap_index(std::uint32_t id,unsigned& i) noexcept {i=id-0x42450001u;return i<Count;}
inline bool vst_index(std::uint32_t id,unsigned& i) noexcept {i=id-1000u;return i<Count;}
inline const char* choice(unsigned i,int value) noexcept {
 static constexpr const char* algorithms[]={"WSOLA","Spectral PV (preview)"};
 static constexpr const char* qualities[]={"General","Transient","Efficient"};
 static constexpr const char* policies[]={"Off","Harmonic / polyphonic","Monophonic"};
 if(i==Backend&&value>=0&&value<2)return algorithms[value];
 if(i==Quality&&value>=0&&value<3)return qualities[value];
 if(i==Policy&&value>=0&&value<3)return policies[value];
 if(i==Bypass)return value?"Bypassed":"Enabled";
 return "";
}
struct Event {std::uint32_t offset,index;float value;};
class Targets {
 static_assert(std::atomic<std::uint32_t>::is_always_lock_free);
 std::array<std::atomic<std::uint32_t>,Count> bits_{};
public:
 Targets() noexcept {store(defaults());}
 float get(unsigned i) const noexcept {return std::bit_cast<float>(bits_[i].load(std::memory_order_relaxed));}
 Values snapshot() const noexcept {Values v{};for(unsigned i=0;i<Count;++i)v[i]=get(i);return v;}
 void store(unsigned i,float v) noexcept {bits_[i].store(std::bit_cast<std::uint32_t>(v),std::memory_order_relaxed);}
 void store(const Values& v) noexcept {for(unsigned i=0;i<Count;++i)store(i,v[i]);}
};
// Versioned LE state. V1 CLAP used 16 bytes; V1 VST3 used 12. Both restore old
// WSOLA/Pitch-only semantics; no old preset silently changes its algorithm.
inline constexpr std::uint32_t state_magic=0x42454747u;
inline constexpr std::size_t state_size=16+4*Count;
inline std::uint32_t read_word(const std::uint8_t* p) noexcept {return std::uint32_t(p[0])|(std::uint32_t(p[1])<<8)|(std::uint32_t(p[2])<<16)|(std::uint32_t(p[3])<<24);}
inline void write_word(std::uint8_t* p,std::uint32_t v) noexcept {for(unsigned i=0;i<4;++i)p[i]=static_cast<std::uint8_t>(v>>(8*i));}
inline auto encode(const Values& v) noexcept {
 std::array<std::uint8_t,state_size> b{};write_word(b.data(),state_magic);write_word(b.data()+4,2);write_word(b.data()+8,state_size);write_word(b.data()+12,Count);
 for(unsigned i=0;i<Count;++i)write_word(b.data()+16+4*i,std::bit_cast<std::uint32_t>(v[i]));return b;
}
inline bool decode(std::span<const std::uint8_t> bytes,Values& out) noexcept {
 if(bytes.size()<12||read_word(bytes.data())!=state_magic)return false;
 Values v=defaults();const auto version=read_word(bytes.data()+4);
 if(version==1){if(bytes.size()!=12&&bytes.size()!=16)return false;if(bytes.size()==16&&read_word(bytes.data()+12))return false;
  v[Pitch]=std::bit_cast<float>(read_word(bytes.data()+8));}
 else if(version==2){if(bytes.size()!=state_size||read_word(bytes.data()+8)!=state_size||read_word(bytes.data()+12)!=Count)return false;
  for(unsigned i=0;i<Count;++i)v[i]=std::bit_cast<float>(read_word(bytes.data()+16+4*i));}
 else return false;
 if(!valid_values(v))return false;out=v;return true;
}
}
#endif
