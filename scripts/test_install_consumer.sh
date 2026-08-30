#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BUILD="${1:-$ROOT/build/release}"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
PREFIX="$TMP/prefix"

cmake --install "$BUILD" --prefix "$PREFIX" >/dev/null
mkdir -p "$TMP/consumer"
cat > "$TMP/consumer/CMakeLists.txt" <<'CMAKE'
cmake_minimum_required(VERSION 3.20)
project(boiled_egg_consumer LANGUAGES C CXX)
find_package(boiled_egg CONFIG REQUIRED)
add_executable(c_consumer main.c)
target_link_libraries(c_consumer PRIVATE boiled_egg::boiled_egg)
add_executable(cpp_consumer main.cpp)
target_link_libraries(cpp_consumer PRIVATE boiled_egg::boiled_egg)
CMAKE
cat > "$TMP/consumer/main.c" <<'C'
#include <boiled_egg/boiled_egg.h>
int main(void) {
    boiledegg_config c = boiledegg_default_config(48000, 2);
    c.max_block_size = 64;
    boiledegg_result r = BOILEDEGG_OK;
    boiledegg_handle *h = boiledegg_create(&c, &r);
    if (!h || r != BOILEDEGG_OK) return 1;
    boiledegg_runtime_info info = {0}; info.struct_size = sizeof(info);
    if (boiledegg_get_runtime_info(h, &info) != BOILEDEGG_OK || info.realtime_latency_frames == 0) return 2;
    float l[64] = {0}, rr[64] = {0}; const float *in[2] = {l, rr}; float *out[2] = {l, rr};
    if (boiledegg_process_realtime(h, in, out, 64, 0, 0) != BOILEDEGG_OK) return 3;
    boiledegg_destroy(h);
    return boiledegg_abi_version() == BOILEDEGG_ABI_VERSION ? 0 : 4;
}
C
cat > "$TMP/consumer/main.cpp" <<'CPP'
#include <boiled_egg/boiled_egg.hpp>
#include <array>
int main() {
    auto cfg = boiledegg_default_config(48000, 2); cfg.max_block_size = 64;
    boiled_egg::engine e(cfg);
    auto info = e.runtime_info();
    std::array<float,64> l{}, r{}; const float *in[2] = {l.data(), r.data()}; float *out[2] = {l.data(), r.data()};
    auto ev = boiled_egg::parameter_event::pitch_semitones(32, 2.0f);
    e.process_realtime(in, out, 64, std::span<const boiled_egg::parameter_event>(&ev, 1));
    return info.realtime_latency_frames > 0 ? 0 : 1;
}
CPP
cmake -S "$TMP/consumer" -B "$TMP/build" -G Ninja -DCMAKE_PREFIX_PATH="$PREFIX" >/dev/null
cmake --build "$TMP/build" >/dev/null
"$TMP/build/c_consumer"
"$TMP/build/cpp_consumer"
echo "installed C and C++ consumer smoke tests OK"
