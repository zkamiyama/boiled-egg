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
    boiledegg_result r = BOILEDEGG_OK;
    boiledegg_handle* h = boiledegg_create(&c, &r);
    if (!h || r != BOILEDEGG_OK) return 1;
    boiledegg_destroy(h);
    return 0;
}
C

cat > "$TMP/consumer/main.cpp" <<'CPP'
#include <boiled_egg/boiled_egg.hpp>
int main() {
    boiled_egg::engine e(48000, 2);
    return e.input_latency_frames() > 0 ? 0 : 1;
}
CPP

cmake -S "$TMP/consumer" -B "$TMP/build" -G Ninja -DCMAKE_PREFIX_PATH="$PREFIX" >/dev/null
cmake --build "$TMP/build" >/dev/null
"$TMP/build/c_consumer"
"$TMP/build/cpp_consumer"
