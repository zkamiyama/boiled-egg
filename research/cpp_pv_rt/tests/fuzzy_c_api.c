#include "boiled_egg_pv_rt.h"
#include <math.h>
int main(void){
    unsigned mode;
    for(mode=BOILEDEGG_RESEARCH_PV_RT_FUZZY;mode<=BOILEDEGG_RESEARCH_PV_RT_FUZZY_NOISE;++mode){
        boiledegg_research_pv_rt_config c=boiledegg_research_pv_rt_default_config(48000,1,64);
        boiledegg_research_pv_rt_result result;
        boiledegg_research_pv_rt_handle* h;
        float input[64]={0},output[512];const float* in[1]={input};float* out[1]={output};
        unsigned i,total=0;
        c.mode=mode;c.fft_size=1024;c.analysis_hop=256;c.initial_pitch_ratio=2.0f;
        h=boiledegg_research_pv_rt_create(&c,&result);if(!h||result)return 1;
        input[16]=0.5f;
        for(i=0;i<20;++i){if(boiledegg_research_pv_rt_push(h,in,64))return 2;
            while(boiledegg_research_pv_rt_available(h))total+=boiledegg_research_pv_rt_pull(h,out,512);}
        if(boiledegg_research_pv_rt_flush(h))return 3;
        while(boiledegg_research_pv_rt_available(h))total+=boiledegg_research_pv_rt_pull(h,out,512);
        if(total!=1280)return 4;
        boiledegg_research_pv_rt_destroy(h);
    }
    return 0;
}
