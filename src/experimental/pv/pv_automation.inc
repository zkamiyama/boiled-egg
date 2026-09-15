// Included in the private engine's public section. Validation uses copies of
// value states; rejecting a batch cannot change DSP, mailboxes, or output.
boiledegg_result enable_time_automation() noexcept {
    if(!timeline_.enabled()||scheduled_||real_input_frames_)return BOILEDEGG_UNSUPPORTED_MODE;
    variable_time_=true;return BOILEDEGG_OK;
}
boiledegg_result validate_ramps(const boiledegg_ramp_event* events,std::uint32_t count,
                               std::uint32_t frames,float pending_pitch) const noexcept {
    if(!timeline_.enabled())return BOILEDEGG_UNSUPPORTED_MODE;
    if(flushed_)return BOILEDEGG_END_OF_STREAM;
    if(count>BOILEDEGG_MAX_RAMP_EVENTS || (count&&!events) || frames>max_block_)
        return BOILEDEGG_INVALID_ARGUMENT;
    auto p=timeline_.plan();
    if(!variable_time_) {
        if(!std::isfinite(pending_pitch)||pending_pitch<.5f||pending_pitch>2.f)
            return BOILEDEGG_UNSUPPORTED_MODE;
        if(p.pitch.target!=pending_pitch)p.pitch.start(pending_pitch,real_input_frames_?std::max(1U,sample_rate_/100U):0U,0);
    }
    const auto safe=[](const automation_plan& a) noexcept {
        return std::max(a.pitch.value,a.pitch.target)*std::max(a.time.value,a.time.target)<=2.;
    };
    if(!safe(p))return BOILEDEGG_UNSUPPORTED_MODE;
    // Validate layout and units first; no partially executed events on failure.
    for(std::uint32_t i=0;i<count;++i) {
        const auto& e=events[i];
        if(e.struct_size!=sizeof(e)||e.reserved[0]||e.reserved[1]||e.curve>BOILEDEGG_RAMP_LOG_RATIO||
           !std::isfinite(e.value)||(frames?e.sample_offset>=frames:e.sample_offset!=0)||
           (i&&e.sample_offset<events[i-1U].sample_offset))return BOILEDEGG_INVALID_ARGUMENT;
        if(e.parameter_id!=BOILEDEGG_PARAMETER_PITCH_RATIO&&e.parameter_id!=BOILEDEGG_PARAMETER_PITCH_SEMITONES&&
           e.parameter_id!=BOILEDEGG_PARAMETER_TIME_RATIO)return BOILEDEGG_UNSUPPORTED_MODE;
        if(e.parameter_id==BOILEDEGG_PARAMETER_TIME_RATIO&&!variable_time_)return BOILEDEGG_UNSUPPORTED_MODE;
        if(e.parameter_id==BOILEDEGG_PARAMETER_PITCH_SEMITONES&&(e.value< -12.f||e.value>12.f))return BOILEDEGG_UNSUPPORTED_MODE;
        const float v=e.parameter_id==BOILEDEGG_PARAMETER_PITCH_SEMITONES?std::pow(2.f,e.value/12.f):e.value;
        if(v<.5f||v>2.f)return BOILEDEGG_UNSUPPORTED_MODE;
    }
    // <=max_block input ticks plus <=256 events, independent of ramp duration.
    std::uint32_t cursor=0,i=0;
    while(i<count) {
        const auto offset=events[i].sample_offset;
        while(cursor<offset){p.pitch.tick();p.time.tick();++cursor;}
        do {
            const auto& e=events[i++];
            const float v=e.parameter_id==BOILEDEGG_PARAMETER_PITCH_SEMITONES?std::pow(2.f,e.value/12.f):e.value;
            auto& ramp=e.parameter_id==BOILEDEGG_PARAMETER_TIME_RATIO?p.time:p.pitch;
            ramp.start(v,e.duration_frames,e.curve,true);
        }while(i<count&&events[i].sample_offset==offset);
        if(!safe(p))return BOILEDEGG_UNSUPPORTED_MODE;
    }
    return BOILEDEGG_OK;
}
boiledegg_result apply_ramp(const boiledegg_ramp_event& e) noexcept {
    // Only called after full validation; same-offset groups may have temporary
    // incompatible endpoints, but no input ticks occur until the group ends.
    const float v=e.parameter_id==BOILEDEGG_PARAMETER_PITCH_SEMITONES?std::pow(2.f,e.value/12.f):e.value;
    if(e.parameter_id==BOILEDEGG_PARAMETER_TIME_RATIO) {
        time_ratio_=v;timeline_.time_ramp(v,e.duration_frames,e.curve);
    }else {pitch_ratio_=v;timeline_.ramp(v,e.duration_frames,e.curve);}
    explicit_automation_=true;return BOILEDEGG_OK;
}
boiledegg_result automation_info(boiledegg_automation_info& i) const noexcept {
    if(!timeline_.enabled())return BOILEDEGG_UNSUPPORTED_MODE;
    const auto& p=timeline_.plan();
    i={sizeof(i),BOILEDEGG_AUTOMATION_VERSION,real_input_frames_,expected_output_frames_,expected_pv_frames_,
       p.pitch.value,p.time.value,static_cast<float>(p.pitch.target),static_cast<float>(p.time.target),
       p.pitch.remaining,p.time.remaining};
    return BOILEDEGG_OK;
}
