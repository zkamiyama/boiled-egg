#ifndef BOILED_EGG_PLUGIN_TEST_ALLOCATIONS_HPP
#define BOILED_EGG_PLUGIN_TEST_ALLOCATIONS_HPP
#include <atomic>
#include <cstdlib>
#include <new>
// Exported by loaded-module test executables, never installed in the SDK.
inline bool counting_allocations=false;
inline std::atomic<unsigned> allocation_count{0};
void* operator new(std::size_t n){if(counting_allocations)++allocation_count;if(auto p=std::malloc(n?n:1))return p;throw std::bad_alloc();}
void* operator new[](std::size_t n){return ::operator new(n);}
void operator delete(void* p) noexcept {std::free(p);}void operator delete[](void* p) noexcept {std::free(p);}
void operator delete(void* p,std::size_t) noexcept {std::free(p);}void operator delete[](void* p,std::size_t) noexcept {std::free(p);}
void* operator new(std::size_t n,std::align_val_t a){if(counting_allocations)++allocation_count;void* p=nullptr;if(posix_memalign(&p,std::size_t(a),n?n:1))throw std::bad_alloc();return p;}
void* operator new[](std::size_t n,std::align_val_t a){return ::operator new(n,a);}
void operator delete(void* p,std::align_val_t) noexcept {std::free(p);}void operator delete[](void* p,std::align_val_t) noexcept {std::free(p);}
void operator delete(void* p,std::size_t,std::align_val_t) noexcept {std::free(p);}void operator delete[](void* p,std::size_t,std::align_val_t) noexcept {std::free(p);}
void* operator new(std::size_t n,const std::nothrow_t&) noexcept {try{return ::operator new(n);}catch(...){return nullptr;}}
void* operator new[](std::size_t n,const std::nothrow_t&) noexcept {try{return ::operator new[](n);}catch(...){return nullptr;}}
void operator delete(void* p,const std::nothrow_t&) noexcept {::operator delete(p);}void operator delete[](void* p,const std::nothrow_t&) noexcept {::operator delete[](p);}
void* operator new(std::size_t n,std::align_val_t a,const std::nothrow_t&) noexcept {try{return ::operator new(n,a);}catch(...){return nullptr;}}
void* operator new[](std::size_t n,std::align_val_t a,const std::nothrow_t&) noexcept {try{return ::operator new[](n,a);}catch(...){return nullptr;}}
void operator delete(void* p,std::align_val_t a,const std::nothrow_t&) noexcept {::operator delete(p,a);}void operator delete[](void* p,std::align_val_t a,const std::nothrow_t&) noexcept {::operator delete[](p,a);}
#endif
