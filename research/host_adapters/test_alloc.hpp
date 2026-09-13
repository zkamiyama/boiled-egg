#ifndef BOILED_EGG_LAB_TEST_ALLOC_HPP
#define BOILED_EGG_LAB_TEST_ALLOC_HPP
#include <atomic>
#include <cstdlib>
#include <new>
inline std::atomic<unsigned> allocations{0};inline bool count_allocations=false;
void* operator new(std::size_t n){if(count_allocations)++allocations;if(auto p=std::malloc(n?n:1))return p;throw std::bad_alloc();}
void* operator new[](std::size_t n){return ::operator new(n);}
void operator delete(void* p)noexcept{std::free(p);}void operator delete[](void* p)noexcept{std::free(p);}
void operator delete(void* p,std::size_t)noexcept{std::free(p);}void operator delete[](void* p,std::size_t)noexcept{std::free(p);}
void* operator new(std::size_t n,std::align_val_t a){if(count_allocations)++allocations;void* p=nullptr;if(posix_memalign(&p,static_cast<std::size_t>(a),n?n:1))throw std::bad_alloc();return p;}
void* operator new[](std::size_t n,std::align_val_t a){return ::operator new(n,a);}
void operator delete(void* p,std::align_val_t)noexcept{std::free(p);}void operator delete[](void* p,std::align_val_t)noexcept{std::free(p);}
void operator delete(void* p,std::size_t,std::align_val_t)noexcept{std::free(p);}void operator delete[](void* p,std::size_t,std::align_val_t)noexcept{std::free(p);}
#endif
