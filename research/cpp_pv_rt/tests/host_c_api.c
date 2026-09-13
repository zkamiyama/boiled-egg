#include "boiled_egg_research_host.h"
#include <stddef.h>
_Static_assert(sizeof(boiledegg_research_host_config)==44,"C config layout");
_Static_assert(sizeof(boiledegg_research_host_event)==16,"C event layout");
_Static_assert(offsetof(boiledegg_research_host_event,formant_ratio)==8,"C event offset");
int main(void){
    boiledegg_research_host_config c=boiledegg_research_host_default_config(48000,1,32);
    boiledegg_research_pv_rt_result result;
    boiledegg_research_host_handle* h=boiledegg_research_host_create(&c,&result);
    float a[32]={0};float* out[]={a};
    if(!h || result || !boiledegg_research_host_latency_frames(h))return 1;
    if(boiledegg_research_host_request_formant(h,1.2f))return 2;
    if(boiledegg_research_host_process(h,NULL,out,32,NULL,0))return 3;
    if(boiledegg_research_host_reset(h))return 4;
    boiledegg_research_host_destroy(h);return 0;
}
