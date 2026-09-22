// Whole public push+drain service / realtime callback measurements, not kernel estimates.
#include <boiled_egg/boiled_egg.h>
#include <algorithm>
#include <chrono>
#include <cmath>
#include <cstdint>
#include <cstring>
#include <iostream>
#include <stdexcept>
#include <vector>
using Clock=std::chrono::steady_clock;
void need(bool ok){if(!ok)throw std::runtime_error("cost probe API failure");}
int main(){try{
    std::cout<<"rate,block,io,time,pitch,repeat,calls,created_us,mean_us,warm_mean_us,p99_us,max_us,over_period,flush_us,output\n";
    for(unsigned rate:{48000u,96000u})for(unsigned block:{32u,64u})for(unsigned io:{0u,1u})for(unsigned state=0;state<5;++state)for(unsigned rep=0;rep<3;++rep){
        const float times[]={1.f,1.f,.25f,.5f,2.f},pitches[]={1.f,.25f,1.f,.5f,2.f},rtp[]={.25f,.5f,1.f,2.f,4.f};
        float t=io?1.f:times[state],p=io?rtp[state]:pitches[state];
        auto cfg=boiledegg_default_config(rate,2);cfg.max_block_size=block;
        auto start=Clock::now();boiledegg_result rc;auto* h=boiledegg_create(&cfg,&rc);need(h && rc==BOILEDEGG_OK);
        double create_us=std::chrono::duration<double,std::micro>(Clock::now()-start).count();
        need(boiledegg_set_time_ratio(h,t)==BOILEDEGG_OK && boiledegg_set_pitch_ratio(h,p)==BOILEDEGG_OK);
        const unsigned n=rate/2,iterations=(n+block-1)/block;
        std::vector<double> elapsed;elapsed.reserve(iterations+1);
        float left[64],right[64],ol[1024],orr[1024];const float* in[]={left,right};float* out[]={ol,orr};
        uint64_t total=0;double flush_us=0;
        for(unsigned pos=0;pos<n;pos+=block){unsigned count=std::min(block,n-pos);
            for(unsigned i=0;i<count;++i){left[i]=float(int(((pos+i)*73u)%1021u)-510)/2048.f;right[i]=.5f*left[i];}
            unsigned made=0;start=Clock::now();
            if(io){need(boiledegg_process_realtime(h,in,out,count,nullptr,0)==BOILEDEGG_OK);made=count;}
            else{unsigned accepted=0;need(boiledegg_push(h,in,count,&accepted)==BOILEDEGG_OK && accepted==count);
                while(boiledegg_available(h)){unsigned got=0;need(boiledegg_pull(h,out,1024,&got)==BOILEDEGG_OK && got);made+=got;}}
            elapsed.push_back(std::chrono::duration<double,std::micro>(Clock::now()-start).count());
            // Output counting is outside the measured callback; correctness is tested separately.
            total+=made;
        }
        if(!io){start=Clock::now();need(boiledegg_flush(h)==BOILEDEGG_OK);unsigned guard=0;
            while(!boiledegg_is_drained(h)){need(++guard<10000);unsigned got=0;need(boiledegg_pull(h,out,1024,&got)==BOILEDEGG_OK);total+=got;}flush_us=std::chrono::duration<double,std::micro>(Clock::now()-start).count();}
        boiledegg_destroy(h);
        double sum=0,warm=0;unsigned late=0;const double period=1e6*block/rate;
        for(size_t i=0;i<elapsed.size();++i){sum+=elapsed[i];if(i>=8)warm+=elapsed[i];if(elapsed[i]>period)++late;}
        std::sort(elapsed.begin(),elapsed.end());
        std::cout.precision(17);std::cout<<rate<<','<<block<<','<<io<<','<<t<<','<<p<<','<<rep<<','<<elapsed.size()<<','<<create_us<<','<<sum/elapsed.size()<<','<<warm/(elapsed.size()-8)<<','<<elapsed[size_t(.99*(elapsed.size()-1))]<<','<<elapsed.back()<<','<<late<<','<<flush_us<<','<<total<<'\n';
    }
    return 0;
}catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}}
