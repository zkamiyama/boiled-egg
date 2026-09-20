#include "phase.h"
int main(void){
    be_phase_config c={sizeof(c),16,2,1,2.0,1e-6,20260920,1048576};
    int64_t centers[2]={0,4};float input[64]={0},output[64]={0};int32_t trace[18];double dt[18],df[18];be_phase_info info={0};
    if(be_phase_process(&c,centers,2,input,32,output,32,trace,dt,df,18,&info))return 1;
    for(int i=0;i<64;++i)if(output[i]!=0)return 1;
    return 0;
}
