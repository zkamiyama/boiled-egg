#include "boiled_egg_research_features.h"
#include <math.h>
#include <stddef.h>
_Static_assert(BOILEDEGG_RESEARCH_PV_RT_ABI_VERSION == 2, "PV ABI unchanged");
_Static_assert(BOILEDEGG_RESEARCH_MULTIRES_RT_ABI_VERSION == 1, "multires ABI unchanged");
_Static_assert(sizeof(boiledegg_research_pv_rt_config) == 68, "PV config layout unchanged");
_Static_assert(sizeof(boiledegg_research_multires_rt_config) == 56, "multires layout unchanged");
int main(void) {
    boiledegg_research_features f = boiledegg_research_default_features();
    boiledegg_research_pv_rt_config c = boiledegg_research_pv_rt_default_config(96000,1,32);
    boiledegg_research_multires_rt_config m = boiledegg_research_multires_rt_default_config(96000,1,32);
    boiledegg_research_pv_rt_result r;
    boiledegg_research_pv_rt_handle* h;
    boiledegg_research_multires_rt_handle* b;
    c.formant_mode=1;m.formant_mode=1;
    f.timing_policy=BOILEDEGG_RESEARCH_TIMING_CENTERED;f.rate_policy=BOILEDEGG_RESEARCH_RATE_SCALED;
    f.initial_formant_ratio=0.75f;
    h=boiledegg_research_pv_rt_create_ex(&c,&f,&r);
    b=boiledegg_research_multires_rt_create_ex(&m,&f,&r);
    if(!h || !b)return 1;
    if(boiledegg_research_pv_rt_get_formant_ratio(h)!=.75f)return 2;
    if(boiledegg_research_pv_rt_set_formant_ratio(h,NAN)!=BOILEDEGG_RESEARCH_PV_RT_INVALID_ARGUMENT)return 3;
    if(boiledegg_research_pv_rt_get_formant_ratio(h)!=.75f)return 4;
    if(boiledegg_research_multires_rt_set_formant_ratio(b,2.0f))return 5;
    if(boiledegg_research_multires_rt_get_formant_ratio(b)!=2.0f)return 6;
    if(boiledegg_research_pv_rt_flush(h) || boiledegg_research_multires_rt_flush(b))return 7;
    if(boiledegg_research_pv_rt_set_formant_ratio(h,1)!=BOILEDEGG_RESEARCH_PV_RT_ALREADY_FLUSHED)return 8;
    boiledegg_research_pv_rt_destroy(h);boiledegg_research_multires_rt_destroy(b);
    if(boiledegg_research_pv_rt_create_ex(&c,NULL,&r)!=NULL)return 9;
    c.formant_mode=0;
    if(boiledegg_research_pv_rt_create_ex(&c,&f,&r)!=NULL)return 10;
    if(boiledegg_research_pv_rt_set_formant_ratio(NULL,1)!=BOILEDEGG_RESEARCH_PV_RT_INVALID_ARGUMENT)return 11;
    return 0;
}
