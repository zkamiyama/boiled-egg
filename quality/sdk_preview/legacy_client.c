/* Compile with the PREVIOUS installed C headers and original shared library.
 * Execute this unchanged binary with each tested library using LD_LIBRARY_PATH.
 * Fingerprint planar samples in frame-major order, never padding bytes. */
#include <boiled_egg/boiled_egg.h>
#include <boiled_egg/backend.h>
#include <inttypes.h>
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#define N 12289u
#define CAP 257u
static void check(int ok, const char* why) { if (!ok) { fprintf(stderr,"%s\n",why); exit(1); } }
static uint64_t word(uint64_t h,uint32_t x) { return (h^x)*UINT64_C(1099511628211); }
static uint32_t bits(float x) { uint32_t v; memcpy(&v,&x,sizeof v); return v; }
static void append(uint64_t* h, float out[2][CAP],unsigned frames,unsigned channels) {
    for(unsigned i=0;i<frames;++i)for(unsigned ch=0;ch<channels;++ch) {
        check(isfinite(out[ch][i]),"nonfinite output"); *h=word(*h,bits(out[ch][i]));
    }
}
static void drain(boiledegg_handle* h,float out[2][CAP],unsigned channels,uint64_t* hash,unsigned* total) {
    float* p[]={out[0],out[1]};
    while(boiledegg_available(h)) {
        unsigned n=0;check(boiledegg_pull(h,p,CAP,&n)==BOILEDEGG_OK && n>0,"pull stalled");
        append(hash,out,n,channels);*total+=n;
    }
}
static void run(unsigned rate,unsigned channels,unsigned quality,unsigned io,unsigned scenario,unsigned block) {
    boiledegg_config c=boiledegg_default_config(rate,channels); c.max_block_size=CAP;
    boiledegg_profile_config p=boiledegg_default_profile();p.quality_mode=quality;
    boiledegg_result status=BOILEDEGG_OK;boiledegg_handle* h=boiledegg_create_ex(&c,&p,&status);
    check(h && status==BOILEDEGG_OK,"legacy create");
    const float pitches[]={1.f,.5f,2.f};const float times[]={1.f,.75f,1.25f};
    boiledegg_parameter_state state={sizeof state,io?1.f:times[scenario],pitches[scenario],0};
    check(boiledegg_set_parameter_state(h,&state)==BOILEDEGG_OK,"legacy state restore");
    boiledegg_runtime_info info={0};info.struct_size=sizeof info;
    check(boiledegg_get_runtime_info(h,&info)==BOILEDEGG_OK,"legacy runtime");
    boiledegg_backend_config backend=boiledegg_default_backend_config();
    check(boiledegg_get_backend_configuration(h,&backend)==BOILEDEGG_OK && backend.backend_id==BOILEDEGG_BACKEND_WSOLA,"legacy backend");
    /* Invalid batch must be atomic, including parameter-only calls. */
    boiledegg_parameter_event bad[]={ {sizeof bad[0],0,BOILEDEGG_PARAMETER_PITCH_RATIO,1.25f},
        {sizeof bad[0],0,BOILEDEGG_PARAMETER_PITCH_RATIO,NAN} };
    check(boiledegg_apply_parameter_events(h,bad,2)==BOILEDEGG_INVALID_ARGUMENT,"invalid batch accepted");
    check(boiledegg_get_pitch_ratio(h)==state.pitch_ratio,"invalid batch modified state");
    check(boiledegg_reset(h)==BOILEDEGG_OK,"legacy reset");
    const unsigned count=N+(io?info.realtime_latency_frames:0u);
    float* x[2]={calloc(count,sizeof(float)),calloc(count,sizeof(float))};check(x[0]&&x[1],"allocation");
    unsigned random=7919u;
    for(unsigned i=0;i<N;++i) {
        random=random*1664525u+1013904223u;
        x[0][i]=.11f*sinf(.0371f*(float)i)+.02f*((float)(random>>8u)/16777216.f-.5f);
        x[1][i]=-.375f*x[0][i]+.03f*cosf(.1013f*(float)i);
    }
    uint64_t hash=UINT64_C(1469598103934665603);unsigned total=0,pos=0;
    float out[2][CAP];float* dst[]={out[0],out[1]};
    while(pos<count) {
        unsigned n=block;if(n>count-pos)n=count-pos;
        const float* in[]={x[0]+pos,x[1]+pos};
        if(io) {
            boiledegg_parameter_event events[2];unsigned ec=0;
            const unsigned at[]={777u,4101u};
            if(scenario==1)for(unsigned i=0;i<2;++i)if(at[i]>=pos && at[i]<pos+n)
                events[ec++]=(boiledegg_parameter_event){sizeof events[0],at[i]-pos,BOILEDEGG_PARAMETER_PITCH_RATIO,i?1.5f:.75f};
            check(boiledegg_process_realtime(h,in,dst,n,events,ec)==BOILEDEGG_OK,"legacy realtime");
            append(&hash,out,n,channels);total+=n;pos+=n;
        } else {
            unsigned accepted=0;status=boiledegg_push(h,in,n,&accepted);
            check(status==BOILEDEGG_OK || status==BOILEDEGG_BUFFER_FULL,"legacy push");
            unsigned before=total;drain(h,out,channels,&hash,&total);
            check(accepted || total!=before,"stream stalled");pos+=accepted;
        }
    }
    if(!io) {
        check(boiledegg_flush(h)==BOILEDEGG_OK,"legacy flush");drain(h,out,channels,&hash,&total);
        check(boiledegg_is_drained(h),"legacy EOS");
        check(total==(unsigned)llround((double)N*state.time_ratio),"legacy duration");
    }
    state.struct_size=sizeof state;check(boiledegg_get_parameter_state(h,&state)==BOILEDEGG_OK,"legacy state snapshot");
    uint64_t metadata=UINT64_C(1469598103934665603);
    const unsigned values[]={info.sample_rate,info.channels,info.max_block_size,info.realtime_latency_frames,
        info.realtime_tail_frames,info.parameter_quantum_frames,info.capabilities,boiledegg_input_latency_frames(h),
        bits(state.time_ratio),bits(state.pitch_ratio),state.reserved,backend.backend_id,backend.quality_mode,
        backend.formant_policy,backend.io_contract,backend.flags};
    for(unsigned i=0;i<sizeof values/sizeof values[0];++i)metadata=word(metadata,values[i]);
    printf("%u,%u,%u,%u,%u,%u,%u,%" PRIu64 ",%" PRIu64 "\n",rate,channels,quality,io,scenario,block,total,hash,metadata);
    free(x[0]);free(x[1]);boiledegg_destroy(h);
}
int main(void) {
    check(boiledegg_abi_version()==BOILEDEGG_ABI_VERSION,"ABI version");
    printf("rate,channels,quality,io,scenario,block,frames,audio_hash,metadata_hash\n");
    const unsigned rates[]={44100,48000,88200,96000},blocks[]={32,257};
    for(unsigned r=0;r<4;++r)for(unsigned ch=1;ch<=2;++ch)for(unsigned q=0;q<3;++q)
    for(unsigned io=0;io<2;++io)for(unsigned s=0;s<3;++s)for(unsigned b=0;b<2;++b)
        run(rates[r],ch,q,io,s,blocks[b]);
    return 0;
}
