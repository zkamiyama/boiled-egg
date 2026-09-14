// Included in the private engine's public section. Validation is observational:
// never advance the real DSP or publish targets when rejecting a batch.
boiledegg_result validate_ramps(const boiledegg_ramp_event* events,std::uint32_t count,
                               std::uint32_t frames,float pending_pitch) const noexcept {
    if(!timeline_.enabled())return BOILEDEGG_UNSUPPORTED_MODE;
    if(flushed_)return BOILEDEGG_END_OF_STREAM;
    if(count>BOILEDEGG_MAX_RAMP_EVENTS || (count&&!events) || frames>max_block_)
        return BOILEDEGG_INVALID_ARGUMENT;
    if(!std::isfinite(pending_pitch) || pending_pitch<.5f || pending_pitch>2.f ||
       double(time_ratio_)*pending_pitch>2.)return BOILEDEGG_UNSUPPORTED_MODE;
    std::uint32_t previous=0;
    for(std::uint32_t i=0;i<count;++i) {
        const auto& e=events[i];
        if(e.struct_size!=sizeof(e) || e.reserved[0] || e.reserved[1] ||
           e.curve>BOILEDEGG_RAMP_LOG_RATIO || !std::isfinite(e.value) ||
           (frames?e.sample_offset>=frames:e.sample_offset!=0) ||
           (i&&e.sample_offset<previous))return BOILEDEGG_INVALID_ARGUMENT;
        previous=e.sample_offset;
        if(e.parameter_id!=BOILEDEGG_PARAMETER_PITCH_RATIO &&
           e.parameter_id!=BOILEDEGG_PARAMETER_PITCH_SEMITONES)return BOILEDEGG_UNSUPPORTED_MODE;
        if(e.parameter_id==BOILEDEGG_PARAMETER_PITCH_SEMITONES && (e.value< -12.f||e.value>12.f))
            return BOILEDEGG_UNSUPPORTED_MODE;
        const float v=e.parameter_id==BOILEDEGG_PARAMETER_PITCH_SEMITONES?std::pow(2.f,e.value/12.f):e.value;
        if(v<.5f||v>2.f||double(time_ratio_)*v>2.)return BOILEDEGG_UNSUPPORTED_MODE;
    }
    return BOILEDEGG_OK;
}
boiledegg_result apply_ramp(const boiledegg_ramp_event& e) noexcept {
    // Only called after full batch validation by the audio owner.
    const float v=e.parameter_id==BOILEDEGG_PARAMETER_PITCH_SEMITONES?std::pow(2.f,e.value/12.f):e.value;
    pitch_ratio_=v;timeline_.ramp(v,e.duration_frames,e.curve);
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
