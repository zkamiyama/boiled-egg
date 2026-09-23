#ifndef BOILED_EGG_PV_RING_INDEX_HPP
#define BOILED_EGG_PV_RING_INDEX_HPP
#include <cassert>
#include <cstddef>
#include <cstdint>

namespace boiled_egg::research::detail {
// Internal only: engine::next_capacity constructs all four ring capacities.
// Positions are unsigned; pv_get rejects negative/out-of-range indices first.
// This is exact unsigned modulo, not an approximation or a new ring policy.
constexpr std::size_t ring_index(std::uint64_t position, std::size_t capacity) noexcept {
    assert(capacity != 0 && (capacity & (capacity - 1U)) == 0);
    return static_cast<std::size_t>(position & (capacity - 1U));
}
}
#endif
