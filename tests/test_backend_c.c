#include <boiled_egg/backend.h>
#include <stddef.h>
_Static_assert(sizeof(boiledegg_backend_config)==48,"config layout");
_Static_assert(sizeof(boiledegg_backend_info)==80,"info layout");
_Static_assert(offsetof(boiledegg_backend_config,initial_time_ratio)==28,"float layout");
_Static_assert(BOILEDEGG_ABI_VERSION==1,"legacy ABI unchanged");
int main(void) {
    boiledegg_config c=boiledegg_default_config(48000,1);
    boiledegg_backend_config b=boiledegg_default_backend_config();
    boiledegg_backend_info i={0};i.struct_size=sizeof(i);
    boiledegg_result r=BOILEDEGG_INTERNAL_ERROR;
    if(boiledegg_query_backend(BOILEDEGG_BACKEND_WSOLA,&i)||i.status!=BOILEDEGG_BACKEND_STABLE)return 1;
    if(boiledegg_validate_backend_config(&c,&b))return 2;
    boiledegg_handle* h=boiledegg_create_backend(&c,&b,&r);
    if(!h||r)return 3;
    boiledegg_destroy(h);return 0;
}
