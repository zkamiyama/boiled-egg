#ifndef BOILED_EGG_WORK_SEQUENCE_HPP
#define BOILED_EGG_WORK_SEQUENCE_HPP
#include <coroutine>
#include <exception>
#include <utility>

namespace boiled_egg::research::detail {
// One persistent coroutine frame, allocated once during engine construction.
// The infinite producer yields true after a bounded slice, false at a frame
// boundary. No task, thread, future, queue or coroutine is created by process().
class work_sequence {
public:
    struct promise_type {
        bool more = false;
        work_sequence get_return_object() noexcept {
            return work_sequence{std::coroutine_handle<promise_type>::from_promise(*this)};
        }
        std::suspend_always initial_suspend() noexcept { return {}; }
        std::suspend_always final_suspend() noexcept { return {}; }
        std::suspend_always yield_value(bool value) noexcept { more=value; return {}; }
        void return_void() noexcept {}
        void unhandled_exception() noexcept { std::terminate(); }
    };
    work_sequence() noexcept = default;
    explicit work_sequence(std::coroutine_handle<promise_type> h) noexcept : handle_(h) {}
    work_sequence(work_sequence&& x) noexcept : handle_(std::exchange(x.handle_,{})) {}
    work_sequence& operator=(work_sequence&& x) noexcept {
        if(this!=&x) { if(handle_)handle_.destroy(); handle_=std::exchange(x.handle_,{}); }
        return *this;
    }
    work_sequence(const work_sequence&)=delete;
    ~work_sequence(){ if(handle_)handle_.destroy(); }
    bool step() noexcept { handle_.resume(); return handle_.promise().more; }
private:
    std::coroutine_handle<promise_type> handle_{};
};
}
#endif
