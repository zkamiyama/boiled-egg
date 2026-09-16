#include "pitch_processor.hpp"
#include <algorithm>
#include <cmath>
#include <limits>
namespace boiled_egg::plugin {
bool Processor::request(unsigned i,float v) noexcept {if(!valid_value(i,v))return false;auto next=targets.snapshot();next[i]=v;
 if(!valid_values(next)){error_code_.store(1);return false;}targets.store(i,v);error_code_.store(0);return true;}
bool Processor::request(const Values& v) noexcept {if(!valid_values(v)){error_code_.store(1);return false;}targets.store(v);error_code_.store(0);return true;}
unsigned Processor::predicted_latency() const noexcept {
 const auto v=targets.snapshot();if(v[Backend]==1){const unsigned scale=rate_>48000?2:1,n=(v[Quality]==0?2048:1024)*scale,h=256*scale;
  // Same conservative source-map bound as the SDK with minimum pitch .5.
  return (static_cast<unsigned>(std::ceil(double(n)/2+2.*h+(double(n)/2+24.)/.5+2.))+31u)&~31u;}
 unsigned window=rate_>=88200?1536:1024,search=window/8;
 if(v[Quality]==1){window=std::max(256u,window*3/4)&~1u;search=std::min(search,std::max(16u,window/8));}
 else if(v[Quality]==2)search=std::max(8u,search/2);
 return window+search+window/2;
}
bool Processor::activate(unsigned rate,unsigned max_block){
 if(active_||core_||rate<8000||rate>384000||!max_block||max_block>65536)return false;
 const auto v=targets.snapshot();if(!valid_values(v))return false;
 auto c=boiledegg_default_config(rate,2);c.max_block_size=std::min(max_block,1024u);
 auto b=boiledegg_default_backend_config();b.backend_id=unsigned(v[Backend]);b.quality_mode=unsigned(v[Quality]);b.formant_policy=unsigned(v[Policy]);b.io_contract=BOILEDEGG_IO_REALTIME;
 b.initial_pitch_ratio=std::exp2(total_pitch(v)/12.f);b.initial_formant_ratio=std::exp2(total_formant(v)/12.f);
 if(b.backend_id==1)b.flags=BOILEDEGG_BACKEND_ALLOW_EXPERIMENTAL|BOILEDEGG_BACKEND_CONTINUOUS_PITCH;
 boiledegg_result result{};auto* created=boiledegg_create_backend(&c,&b,&result);if(!created||result)return false;
 boiledegg_runtime_info runtime{};runtime.struct_size=sizeof(runtime);
 if(boiledegg_get_runtime_info(created,&runtime)){boiledegg_destroy(created);return false;}
 try {dry_history_.assign(2u*std::max(1u,runtime.realtime_latency_frames),0.f);dry_scratch_.assign(2u*c.max_block_size,0.f);zero_.assign(c.max_block_size,0.f);}
 catch(...){boiledegg_destroy(created);throw;}
 core_=created;rate_=rate;max_block_=max_block;core_block_=c.max_block_size;runtime_=runtime;configuration_=audio_=v;
 position_=0;fault_=false;active_=true;mix_frames_=std::max(1u,rate/200u);mix_remaining_=0;
 if(!apply(v)){deactivate();return false;}mix_=mix_target_;mix_remaining_=0;return true;
}
void Processor::deactivate() noexcept {boiledegg_destroy(core_);core_=nullptr;active_=false;fault_=false;}
bool Processor::reset() noexcept {
 if(!core_)return false;auto v=needs_restart()?audio_:targets.snapshot();if(!valid_values(v))return false;
 if(!apply(v)||boiledegg_reset(core_))return false;
 std::fill(dry_history_.begin(),dry_history_.end(),0.f);position_=0;fault_=false;mix_=mix_target_;mix_remaining_=0;error_code_.store(0);return true;
}
bool Processor::apply(const Values& v) noexcept {
 if(boiledegg_set_pitch_semitones(core_,total_pitch(v))||boiledegg_set_formant_semitones(core_,total_formant(v)))return false;
 const float bypass=v[Bypass],wet=v[Wet]*(1.f-bypass)*std::pow(10.f,v[Volume]/20.f),dry=v[Dry]*(1.f-bypass)+bypass;
 const std::array<float,4> next{wet*std::min(1.f,1.f-v[Pan]),wet*std::min(1.f,1.f+v[Pan]),dry,dry};
 if(next!=mix_target_){mix_target_=next;mix_remaining_=mix_frames_;for(unsigned i=0;i<4;++i)mix_step_[i]=(next[i]-mix_[i])/float(mix_frames_);}
 audio_=v;return true;
}
bool Processor::segment(const float* const* in,float* const* out,unsigned offset,unsigned count) noexcept {
 for(unsigned base=0;base<count;base+=core_block_){const unsigned n=std::min(core_block_,count-base);const float* source[2]{};float* output[2]{};
  for(unsigned ch=0;ch<2;++ch){source[ch]=in?in[ch]+offset+base:zero_.data();output[ch]=out[ch]+offset+base;}
  const auto L=runtime_.realtime_latency_frames;
  for(unsigned i=0;i<n;++i){const auto slot=static_cast<std::size_t>((position_+i)%std::max(1u,L));for(unsigned ch=0;ch<2;++ch){
   dry_scratch_[std::size_t(ch)*core_block_+i]=L?dry_history_[std::size_t(ch)*L+slot]:source[ch][i];
   dry_history_[std::size_t(ch)*std::max(1u,L)+slot]=source[ch][i];}}
  const auto status=boiledegg_process_realtime(core_,source,output,n,nullptr,0);
  if(status!=BOILEDEGG_OK){error_code_.store(2);fault_=true;return false;}
  for(unsigned i=0;i<n;++i){if(mix_remaining_){for(unsigned k=0;k<4;++k)mix_[k]=mix_remaining_==1?mix_target_[k]:mix_[k]+mix_step_[k];--mix_remaining_;}
   for(unsigned ch=0;ch<2;++ch)output[ch][i]=mix_[ch]*output[ch][i]+mix_[ch+2]*dry_scratch_[std::size_t(ch)*core_block_+i];}
  position_+=n;
 }return true;
}
bool Processor::process(const float* const* in,float* const* out,unsigned n,std::span<const Event> events) noexcept {
 if(!core_||!active_||fault_||n>max_block_||events.size()>256||(n&&!out))return false;
 if(n){for(unsigned ch=0;ch<2;++ch){if(!out[ch]||(in&&!in[ch]))return false;if(in)for(unsigned i=0;i<n;++i)if(!std::isfinite(in[ch][i]))return false;}}
 // One bounded snapshot, no spinning on UI publications. A state restore can
 // span several atomic stores; retain the last valid audio configuration until
 // a consistent compatible snapshot is visible. Timestamped events below are
 // still validated strictly and transactionally, never silently discarded.
 auto start=targets.snapshot();if(!valid_values(start)||!same_configuration(start,configuration_))start=audio_;
 auto validation=start;unsigned previous=0;
 for(std::size_t i=0;i<events.size();){const auto offset=events[i].offset;if((n?offset>=n:offset!=0)||offset<previous)return false;previous=offset;
  do{const auto& e=events[i];if(e.index>=Count||!parameters[e.index].automatable||!valid_value(e.index,e.value))return false;validation[e.index]=e.value;++i;}while(i<events.size()&&events[i].offset==offset);
  if(!valid_values(validation))return false;
 }
 if(!apply(start))return false;
 unsigned cursor=0;std::size_t event=0;
 while(event<events.size()){
  const auto at=events[event].offset;if(at>cursor&&!segment(in,out,cursor,at-cursor))return false;cursor=at;auto next=audio_;
  const auto begin=event;do{next[events[event].index]=events[event].value;++event;}while(event<events.size()&&events[event].offset==at);
  if(!apply(next))return false;for(auto i=begin;i<event;++i)targets.store(events[i].index,events[i].value);
 }
 if(cursor<n&&!segment(in,out,cursor,n-cursor))return false;
 error_code_.store(0);return true;
}
const char* Processor::error() const noexcept {switch(error_code_.load()){case 1:return "Unsupported combination: PV +/-12 st; WSOLA formants Off";case 2:return "Audio underflow/error: reset required";default:return "";}}
}
