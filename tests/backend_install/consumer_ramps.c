#include <boiled_egg/automation.h>
#include <math.h>
#include <stddef.h>
_Static_assert(sizeof(boiledegg_ramp_event)==32,"installed ramp event ABI");
_Static_assert(offsetof(boiledegg_ramp_event,value)==20,"installed ramp value offset");

static int exercise(int streaming) {
    boiledegg_config c=boiledegg_default_config(48000,1);c.max_block_size=32;
    boiledegg_backend_config b=boiledegg_default_backend_config();
    b.io_contract=streaming?BOILEDEGG_IO_STREAMING:BOILEDEGG_IO_REALTIME;
    if(EXPECT_SPECTRAL) {
        b.backend_id=BOILEDEGG_BACKEND_PHASE_VOCODER;
        b.flags=BOILEDEGG_BACKEND_ALLOW_EXPERIMENTAL|BOILEDEGG_BACKEND_CONTINUOUS_PITCH;
        if(streaming)b.flags|=BOILEDEGG_BACKEND_CONTINUOUS_TIME;
    }
    boiledegg_result status;boiledegg_handle* h=boiledegg_create_backend(&c,&b,&status);
    if(!h||status)return 1;
    int failure=0;
    float x[32]={0},y[2048]={0};const float* in[]={x};float* out[]={y};
    boiledegg_ramp_event event={sizeof(event),0,
        streaming?BOILEDEGG_PARAMETER_TIME_RATIO:BOILEDEGG_PARAMETER_PITCH_RATIO,64,
        streaming?BOILEDEGG_RAMP_LINEAR_RATIO:BOILEDEGG_RAMP_LOG_RATIO,
        streaming?2.0f:1.5f,{0,0}};
    uint32_t used=0;
    for(unsigned i=0;i<2;++i) {
        if(streaming)status=boiledegg_push_ramps(h,in,32,i?NULL:&event,i?0:1,&used);
        else status=boiledegg_process_realtime_ramps(h,in,out,32,i?NULL:&event,i?0:1);
        if(!EXPECT_SPECTRAL) {
            failure=status==BOILEDEGG_UNSUPPORTED_MODE?0:2;
            goto done;
        }
        if(status||(streaming&&used!=32)){failure=3;goto done;}
    }
    boiledegg_automation_info info={0};info.struct_size=sizeof(info);
    status=boiledegg_get_automation_info(h,&info);
    if(status||info.input_frames!=64||info.pitch_remaining_frames||info.time_remaining_frames) {
        failure=4;goto done;
    }
    if(streaming) {
        /* Sum of post-tick T_i=1+i/64 is 96.5; EOS rounds to 97 frames. */
        if(fabs(info.output_position-96.5)>1e-12||info.effective_time_ratio!=2.){failure=5;goto done;}
        if(boiledegg_flush(h)){failure=6;goto done;}
        unsigned total=0;
        while(boiledegg_available(h)) {
            uint32_t n=0;
            if(boiledegg_pull(h,out,2048,&n)||!n){failure=7;goto done;}
            total+=n;
        }
        if(total!=97||!boiledegg_is_drained(h))failure=8;
    } else if(info.effective_pitch_ratio!=1.5||info.output_position!=64.)failure=9;
done:
    boiledegg_destroy(h);return failure;
}
int main(void){int result=exercise(0);return result?result:exercise(1);}
