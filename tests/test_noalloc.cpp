#include <boiled_egg/boiled_egg.h>
#include <atomic>
#include <cstdlib>
#include <new>
#include <vector>

static std::atomic<unsigned long long> allocations{0};

void* operator new(std::size_t n) {
    allocations.fetch_add(1, std::memory_order_relaxed);
    if (void* p = std::malloc(n)) return p;
    throw std::bad_alloc();
}
void operator delete(void* p) noexcept { std::free(p); }
void operator delete(void* p, std::size_t) noexcept { std::free(p); }
void* operator new[](std::size_t n) {
    allocations.fetch_add(1, std::memory_order_relaxed);
    if (void* p = std::malloc(n)) return p;
    throw std::bad_alloc();
}
void operator delete[](void* p) noexcept { std::free(p); }
void operator delete[](void* p, std::size_t) noexcept { std::free(p); }

int main() {
    auto cfg = boiledegg_default_config(48000, 2);
    cfg.max_block_size = 256;
    boiledegg_result rr{};
    boiledegg_handle* h = boiledegg_create(&cfg, &rr);
    if (!h || rr != BOILEDEGG_OK) return 1;

    std::vector<float> l(256, 0.1f), r(256, -0.1f), ol(1024), orr(1024);
    const float* in[2] = {l.data(), r.data()};
    float* out[2] = {ol.data(), orr.data()};

    for (int i=0;i<16;++i) {
        uint32_t a=0,p=0;
        if (boiledegg_push(h,in,256,&a)!=BOILEDEGG_OK || a!=256) return 2;
        while(boiledegg_available(h)) if(boiledegg_pull(h,out,1024,&p)!=BOILEDEGG_OK) return 3;
    }
    const auto before=allocations.load(std::memory_order_relaxed);
    for (int i=0;i<500;++i) {
        if (boiledegg_set_time_ratio(h, 0.8f + 0.4f * float(i%17)/16.0f) != BOILEDEGG_OK) return 4;
        if (boiledegg_set_pitch_semitones(h, -7.0f + 14.0f * float(i%19)/18.0f) != BOILEDEGG_OK) return 5;
        uint32_t a=0,p=0;
        auto x=boiledegg_push(h,in,256,&a);
        if ((x!=BOILEDEGG_OK && x!=BOILEDEGG_BUFFER_FULL) || a==0) return 6;
        while(boiledegg_available(h)) if(boiledegg_pull(h,out,1024,&p)!=BOILEDEGG_OK) return 7;
    }
    const auto after=allocations.load(std::memory_order_relaxed);
    boiledegg_destroy(h);
    return before==after ? 0 : 8;
}
