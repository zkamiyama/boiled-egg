#include "nsdgt.h"
int main(void) {
    be_nsg_config c={sizeof(c),16,1,1048576};
    be_nsg_frame f={0,3,0};double w[3]={0,1,0};float x[2]={.25f,-.125f};
    float coeff[32],out[2]={-99,-99};be_nsg_info info={0};
    if(be_nsg_analyze(&c,&f,1,w,3,x,1,coeff,16,&info)!=0)return 1;
    if(info.coefficient_count!=16)return 2;
    if(be_nsg_synthesize(&c,&f,1,w,3,coeff,16,out,1,&info)!=0)return 3;
    if(out[0]!=x[0] || out[1]!=x[1])return 4;
    return 0;
}
