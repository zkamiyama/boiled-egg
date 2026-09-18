#include "dsp/audio_source.hpp"
#include <atomic>
#include <cstdlib>
#include <iostream>
#include <new>
#include <random>
#include <thread>
using namespace boiled_egg::dsp;
static thread_local bool watch=false;
static std::atomic<unsigned> allocations=0;
void* operator new(std::size_t n){if(watch)++allocations;if(auto* p=std::malloc(n?n:1))return p;throw std::bad_alloc();}
void* operator new[](std::size_t n){return ::operator new(n);}
void operator delete(void* p) noexcept{std::free(p);}void operator delete[](void* p) noexcept{std::free(p);}
void operator delete(void* p,std::size_t) noexcept{std::free(p);}void operator delete[](void* p,std::size_t) noexcept{std::free(p);}
void* operator new(std::size_t n,std::align_val_t a){if(watch)++allocations;const auto size=static_cast<std::size_t>(a);void* p=nullptr;if(posix_memalign(&p,size,n?n:1))throw std::bad_alloc();return p;}
void* operator new[](std::size_t n,std::align_val_t a){return ::operator new(n,a);}
void operator delete(void* p,std::align_val_t) noexcept{std::free(p);}void operator delete[](void* p,std::align_val_t) noexcept{std::free(p);}
void operator delete(void* p,std::size_t,std::align_val_t) noexcept{std::free(p);}void operator delete[](void* p,std::size_t,std::align_val_t) noexcept{std::free(p);}
static void require(bool ok,const char* message){if(!ok)throw std::runtime_error(message);}
static void file_test(){
    std::vector<float> x{1,-.375F,2,-.75F};prepared_source file(x,2);x[0]=99;
    auto v=file.view();require(v.read(0,0).value==1,"source copy ownership");
    require(v.read(-1,0).state==sample_state::padding && v.read(2,1).state==sample_state::padding,"file padding");
    require(v.read(1,2).state==sample_state::invalid,"channel bounds");
    prepared_source empty({},2);require(empty.view().read(0,0).state==sample_state::padding,"empty file");
    bool rejected=false;try{prepared_source bad(std::vector<float>{NAN},1);}catch(const std::invalid_argument&){rejected=true;}
    require(rejected,"nonfinite constructor");
    rejected=false;try{rolling_source bad(0,1);}catch(const std::invalid_argument&){rejected=true;}
    require(rejected,"zero capacity");
    rejected=false;try{rolling_source bad(4,0);}catch(const std::invalid_argument&){rejected=true;}
    require(rejected,"zero channels");
}
static std::uint64_t ring_test(){
    std::uint64_t checks=0;std::mt19937 rng(260919);
    for(auto capacity:{1U,7U,64U,257U})for(auto channels:{1U,2U,8U}){
        rolling_source ring(capacity,channels);std::vector<float> history;
        const auto bytes=ring.owned_bytes();
        for(unsigned iteration=0;iteration<50;++iteration){
            const auto count=rng()%(2*capacity+3);
            std::vector<float> batch(count*channels);
            for(float& v:batch)v=static_cast<float>(int(rng()%2001)-1000)/1000.F;
            const auto old_size=history.size()/channels;
            history.insert(history.end(),batch.begin(),batch.end());
            watch=true;auto result=ring.append(batch);watch=false;
            require(result.status==source_write_status::ok && result.accepted==count,"batch accounting");
            const auto size=history.size()/channels;
            const auto first=size>capacity?size-capacity:0;
            const auto old_first=old_size>capacity?old_size-capacity:0;
            require(result.discarded==first-old_first && ring.discarded_frames()==first,"discard accounting");
            auto view=ring.view();
            require(view.first()==static_cast<std::int64_t>(first) && view.end()==static_cast<std::int64_t>(size),"view range");
            for(std::size_t at=first;at<size;++at)for(unsigned ch=0;ch<channels;++ch){
                watch=true;auto sample=view.read(static_cast<std::int64_t>(at),ch);watch=false;
                require(sample.state==sample_state::ready && sample.value==history[at*channels+ch],"independent history");++checks;
            }
            require(view.read(static_cast<std::int64_t>(size),0).state==sample_state::future,"future != silence");
            if(first)require(view.read(static_cast<std::int64_t>(first-1),0).state==sample_state::expired,"expired != silence");
            require(view.read(-1,0).state==sample_state::padding,"startup padding");
            std::vector<float> bad(channels*2,1.F);bad.back()=iteration%2?INFINITY:NAN;
            watch=true;auto invalid=ring.append(bad);watch=false;
            require(invalid.status==source_write_status::invalid && ring.view().end()==view.end(),"invalid append clock");
            for(std::size_t at=first;at<size;++at)for(unsigned ch=0;ch<channels;++ch)
                require(ring.view().read(static_cast<std::int64_t>(at),ch).value==history[at*channels+ch],"invalid append storage");
            require(ring.owned_bytes()==bytes,"bounded ring storage");
        }
        watch=true;ring.reset();watch=false;
        require(ring.view().end()==0 && ring.view().read(0,0).state==sample_state::future && ring.discarded_frames()==0,"reset visibility");
    }
    return checks;
}
static void capture_test(){
    rolling_source ring(8,2);captured_source held(4,2);
    std::vector<float> data(16);for(unsigned i=0;i<16;++i)data[i]=float(i);
    require(ring.append(data).accepted==8,"prime ring");
    const auto bytes=held.owned_bytes();
    watch=true;auto status=held.capture(ring.view(),2,4);watch=false;
    require(status==source_write_status::ok,"capture ready");
    for(auto first:{-1,7,9}){
        watch=true;status=held.capture(ring.view(),first,4);watch=false;
        require(status!=source_write_status::ok,"invalid/missing capture rejection");
        require(held.view().first()==2 && held.view().end()==6,"transactional capture metadata");
        for(int i=2;i<6;++i)for(unsigned ch=0;ch<2;++ch)
            require(held.view().read(i,ch).value==data[unsigned(i)*2+ch],"transactional capture samples");
    }
    for(unsigned repeat=0;repeat<10000;++repeat){watch=true;auto write=ring.append(data);watch=false;require(write.accepted==8,"continued input");}
    require(ring.view().read(2,0).state==sample_state::expired,"rolling history overwritten");
    require(held.view().read(2,0).value==4 && held.owned_bytes()==bytes,"independent bounded capture");
    require(held.view().read(6,0).state==sample_state::outside_capture,"capture bound");
    require(held.capture(ring.view(),2,4)==source_write_status::missing_range,"expired capture rejected");
    require(held.capture(ring.view(),0,0)==source_write_status::invalid,"empty capture rejected");
    require(held.capture(ring.view(),std::numeric_limits<std::int64_t>::max(),4)==source_write_status::invalid,"capture clock overflow");
    prepared_source short_file(std::vector<float>{.25F,-.25F},2);
    require(held.capture(short_file.view(),0,4)==source_write_status::ok,"known file padding capture");
    require(held.view().read(1,1).value==0,"padding is captured as zero");
}
static void independent_threads(){
    std::atomic<bool> ok=true;
    auto run=[&](float value){
        rolling_source ring(13,1);captured_source held(7,1);std::vector<float> input(19,value);
        watch=true;
        for(unsigned i=0;i<2000;++i){
            auto w=ring.append(input);
            auto status=held.capture(ring.view(),ring.view().end()-7,7);
            if(w.accepted!=19 || status!=source_write_status::ok || held.view().read(held.view().first(),0).value!=value)ok=false;
        }
        watch=false;
    };
    std::thread a(run,.1F),b(run,-.4F);a.join();b.join();require(ok,"independent owners");
}
int main(){try{file_test();auto checks=ring_test();capture_test();independent_threads();
    require(allocations==0,"processing allocated");
    std::cout<<checks<<" exact reference samples; transactional append/capture; future/expired distinction; independent owners; zero processing allocations\n";
}catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}}
