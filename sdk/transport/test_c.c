#include "transport.h"
int main(void){
  be_transport_config c=be_transport_default_config(48000,1);
  int result=-1;be_transport* h=be_transport_create(&c,0,0,&result);
  float y[32];be_transport_info info={0};info.struct_size=sizeof info;
  if(!h || result || be_transport_render(h,y,32,0,0) || be_transport_get_info(h,&info))return 1;
  be_transport_destroy(h);return info.output_frames!=32;
}
