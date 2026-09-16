#include <boiled_egg/automation.h>
#include <stddef.h>
_Static_assert(sizeof(boiledegg_ramp_event)==32,"fixed event stride");
_Static_assert(offsetof(boiledegg_ramp_event,value)==20,"C field layout");
int main(void){
    boiledegg_config c=boiledegg_default_config(48000,1);c.max_block_size=32;
    boiledegg_backend_config b=boiledegg_default_backend_config();
    boiledegg_result status;
    boiledegg_handle* h=boiledegg_create_backend(&c,&b,&status);
    boiledegg_automation_info i={0};i.struct_size=sizeof(i);
    if(!h||status)return 1;
    if(boiledegg_get_automation_info(h,&i)!=BOILEDEGG_UNSUPPORTED_MODE)return 2;
    if(boiledegg_process_realtime_ramps(h,NULL,NULL,0,NULL,0)!=BOILEDEGG_UNSUPPORTED_MODE)return 3;
    boiledegg_destroy(h);return 0;
}
