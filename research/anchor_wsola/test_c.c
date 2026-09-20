#include "anchor.h"
int main(void) {
    be_anchor_config c={sizeof(be_anchor_config),48000,1,0,1.0,16777216};
    be_anchor_info info={0};be_anchor_grain trace[1];float in[1]={.1f},out[1]={-1};
    /* Insufficient trace capacity is an error, not partial success. */
    return be_anchor_render(in,1,0,0,&c,out,trace,1,&info)==2 && out[0]==-1 ? 0 : 1;
}
