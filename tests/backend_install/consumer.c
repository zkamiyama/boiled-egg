#include <boiled_egg/backend.h>
#include <stddef.h>
_Static_assert(sizeof(boiledegg_backend_config)==48,"C ABI configuration size");
_Static_assert(offsetof(boiledegg_backend_config,initial_time_ratio)==28,"C ABI float offset");
_Static_assert(sizeof(boiledegg_backend_parameter_state)==32,"C ABI extension state size");
int main(void) {
    boiledegg_backend_info info={0};info.struct_size=sizeof(info);
    if(boiledegg_query_backend(BOILEDEGG_BACKEND_PHASE_VOCODER,&info))return 1;
    if((info.status==BOILEDEGG_BACKEND_EXPERIMENTAL)!=EXPECT_SPECTRAL)return 2;
    boiledegg_config c=boiledegg_default_config(48000,1);c.max_block_size=64;
    boiledegg_backend_config b=boiledegg_default_backend_config();
    b.io_contract=BOILEDEGG_IO_REALTIME;
    if(EXPECT_SPECTRAL) {
        b.backend_id=BOILEDEGG_BACKEND_PHASE_VOCODER;b.flags=BOILEDEGG_BACKEND_ALLOW_EXPERIMENTAL;
        b.formant_policy=BOILEDEGG_FORMANT_POLICY_HARMONIC;
    }
    boiledegg_result r;boiledegg_handle* h=boiledegg_create_backend(&c,&b,&r);
    if(!h || r)return 3;
    float samples[64]={0};const float* input[]={samples};float* output[]={samples};
    boiledegg_parameter_event event={sizeof(event),13,BOILEDEGG_PARAMETER_FORMANT_RATIO,1};
    if(EXPECT_SPECTRAL)event.value=0.75f;
    r=boiledegg_process_realtime(h,input,output,64,&event,1);
    boiledegg_backend_parameter_state state={0};state.struct_size=sizeof(state);
    if(!r)r=boiledegg_get_backend_parameter_state(h,&state);
    if(!r)r=boiledegg_set_backend_parameter_state(h,&state);
    boiledegg_destroy(h);return r?4:0;
}
