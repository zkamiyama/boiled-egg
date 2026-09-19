#!/usr/bin/env bash
# Compile consumers with installed headers/library ONLY, outside the source tree.
set -euo pipefail
build=$(cd "${1:?supply native build directory}" && pwd)
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT
cmake --install "$build" --prefix "$tmp/prefix"
# Use the actual installed libdir (lib or lib64), never a build fallback.
lib=$(find "$tmp/prefix" -type f -name libboiled_egg_transport.so -print -quit)
test -n "$lib"
libdir=$(dirname "$lib")
cat > "$tmp/c.c" <<'C'
#include <boiled_egg/transport.h>
int main(void){
  be_transport_config config=be_transport_default_config(48000,1);
  float input[32]={0},output[64]; int result=-1;
  be_transport* h=be_transport_create(&config,input,32,&result);
  if(!h || result) return 1;
  be_transport_info info={0};info.struct_size=sizeof info;
  be_transport_event hold={0,BE_T_SPEED,0,0,0};
  int failed=be_transport_render(h,output,64,&hold,1)||be_transport_get_info(h,&info);
  be_transport_destroy(h);
  return failed||info.output_frames!=64||info.source_position!=0;
}
C
cat > "$tmp/cpp.cpp" <<'CPP'
#include <boiled_egg/transport.hpp>
#include <array>
int main(){
  auto config=be_transport_default_config(48000,1);
  std::array<float,32> input{};std::array<float,64> output{};
  boiled_egg::file_transport h(config,input);auto moved=std::move(h);
  moved.render(output);
  return moved.info().output_frames!=64||h.render_nothrow(output)!=BE_T_INVALID;
}
CPP
"${CC:-cc}" -std=c11 "$tmp/c.c" -I"$tmp/prefix/include" -L"$libdir" -Wl,-rpath,"$libdir" -lboiled_egg_transport -o "$tmp/c"
"${CXX:-c++}" -std=c++20 "$tmp/cpp.cpp" -I"$tmp/prefix/include" -L"$libdir" -Wl,-rpath,"$libdir" -lboiled_egg_transport -o "$tmp/cpp"
"$tmp/c"
"$tmp/cpp"
echo 'Installed C11 and C++ RAII consumers: 2/2 passed'
