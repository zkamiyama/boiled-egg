// Public additive ramp entry points. This file is included after the original C
// functions so opaque-handle layout and unchanged realtime output logic stay in
// one translation unit. No allocation, locks, UI callbacks or hidden event queue.
static boiledegg_result ramp_batch_check(boiledegg_handle* h,const float* const* input,
    float* const* output,uint32_t frames,const boiledegg_ramp_event* e,uint32_t count,
    bool realtime,float pending_pitch) noexcept {
    if(frames>h->max_block_size || (frames && (!valid_planar_input(h,input) ||
        (realtime&&!valid_planar_output(h,output)))))return BOILEDEGG_INVALID_ARGUMENT;
    for(uint32_t ch=0;frames&&ch<h->channels;++ch)
        for(uint32_t i=0;i<frames;++i)if(!std::isfinite(input[ch][i]))return BOILEDEGG_INVALID_ARGUMENT;
    const auto r=h->engine.validate_ramps(e,count,frames,pending_pitch);
    if(r!=BOILEDEGG_OK)return r;
    const auto mode=load_mode(h);
    const bool incompatible=realtime?
        (h->backend.io_contract==BOILEDEGG_IO_STREAMING || mode==processing_mode::streaming):
        (h->backend.io_contract==BOILEDEGG_IO_REALTIME || mode==processing_mode::realtime);
    // Parameter-only calls do not select or change the I/O contract.
    if(frames&&incompatible)return BOILEDEGG_INVALID_STATE;
    return BOILEDEGG_OK;
}
static boiledegg_result ramp_apply(boiledegg_handle* h,const boiledegg_ramp_event& e) noexcept {
    const auto r=h->engine.apply_ramp(e);
    if(r==BOILEDEGG_OK) {
        const float v=e.parameter_id==BOILEDEGG_PARAMETER_PITCH_SEMITONES?std::pow(2.f,e.value/12.f):e.value;
        if(e.parameter_id==BOILEDEGG_PARAMETER_TIME_RATIO)store_ratio(h->requested_time_ratio_bits,v);
        else store_ratio(h->requested_pitch_ratio_bits,v);
    }
    return r;
}
boiledegg_result boiledegg_process_realtime_ramps(boiledegg_handle* h,const float* const* input,
    float* const* output,uint32_t frames,const boiledegg_ramp_event* e,uint32_t count) {
    if(!h)return BOILEDEGG_INVALID_ARGUMENT;
    const float pending=load_ratio(h->requested_pitch_ratio_bits);
    const auto checked=ramp_batch_check(h,input,output,frames,e,count,true,pending);
    if(checked!=BOILEDEGG_OK)return checked;
    if(frames&&!enter_mode(h,processing_mode::realtime))return BOILEDEGG_INVALID_STATE;
    auto r=(h->backend.flags&BOILEDEGG_BACKEND_CONTINUOUS_TIME)?BOILEDEGG_OK:h->engine.set_pitch_ratio(pending);if(r!=BOILEDEGG_OK)return r;
    r=h->engine.set_formant_ratio(load_ratio(h->requested_formant_ratio_bits));if(r!=BOILEDEGG_OK)return r;
    uint32_t cursor=0;boiledegg_result overall=BOILEDEGG_OK;
    for(uint32_t i=0;i<count;++i) {
        if(e[i].sample_offset>cursor) {
            r=process_realtime_chunk(h,input,output,cursor,e[i].sample_offset-cursor);
            if(r!=BOILEDEGG_OK&&r!=BOILEDEGG_REALTIME_UNDERRUN)return r;
            if(r!=BOILEDEGG_OK)overall=r;
            cursor=e[i].sample_offset;
        }
        r=ramp_apply(h,e[i]);if(r!=BOILEDEGG_OK)return r;
    }
    if(cursor<frames) {
        r=process_realtime_chunk(h,input,output,cursor,frames-cursor);
        if(r!=BOILEDEGG_OK)overall=r;
    }
    return overall;
}
boiledegg_result boiledegg_push_ramps(boiledegg_handle* h,const float* const* input,
    uint32_t frames,const boiledegg_ramp_event* e,uint32_t count,uint32_t* accepted) {
    if(!h||!accepted)return BOILEDEGG_INVALID_ARGUMENT;
    *accepted=0;
    const float pending=load_ratio(h->requested_pitch_ratio_bits);
    const auto checked=ramp_batch_check(h,input,nullptr,frames,e,count,false,pending);
    if(checked!=BOILEDEGG_OK)return checked;
    if(frames&&!enter_mode(h,processing_mode::streaming))return BOILEDEGG_INVALID_STATE;
    // On BUFFER_FULL with accepted=0, even offset-zero events remain unconsumed.
    if(frames&&!h->engine.can_accept_ramp_sample())return BOILEDEGG_BUFFER_FULL;
    auto r=(h->backend.flags&BOILEDEGG_BACKEND_CONTINUOUS_TIME)?BOILEDEGG_OK:h->engine.set_pitch_ratio(pending);if(r!=BOILEDEGG_OK)return r;
    r=h->engine.set_formant_ratio(load_ratio(h->requested_formant_ratio_bits));if(r!=BOILEDEGG_OK)return r;
    if(!frames) {
        for(uint32_t i=0;i<count;++i){r=ramp_apply(h,e[i]);if(r!=BOILEDEGG_OK)return r;}
        return BOILEDEGG_OK;
    }
    uint32_t index=0;
    for(uint32_t n=0;n<frames;++n) {
        if(!h->engine.can_accept_ramp_sample())return BOILEDEGG_BUFFER_FULL;
        while(index<count&&e[index].sample_offset==n) {
            r=ramp_apply(h,e[index++]);if(r!=BOILEDEGG_OK)return r;
        }
        for(uint32_t ch=0;ch<h->channels;++ch)h->input_ptrs[ch]=input[ch]+n;
        uint32_t used=0;r=h->engine.push(h->input_ptrs.data(),1,used);
        *accepted+=used;
        if(r!=BOILEDEGG_OK)return r;
        if(used!=1)return BOILEDEGG_INTERNAL_ERROR;
    }
    return BOILEDEGG_OK;
}
boiledegg_result boiledegg_get_automation_info(const boiledegg_handle* h,boiledegg_automation_info* info) {
    if(!h||!info||info->struct_size<sizeof(*info))return BOILEDEGG_INVALID_ARGUMENT;
    return h->engine.automation_info(*info);
}
