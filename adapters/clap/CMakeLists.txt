include(FetchContent)

set(CLAP_BUILD_TESTS OFF CACHE BOOL "" FORCE)
FetchContent_Declare(
  clap
  GIT_REPOSITORY https://github.com/free-audio/clap.git
  GIT_TAG 1.2.10
  GIT_SHALLOW TRUE
)
FetchContent_MakeAvailable(clap)

add_library(boiled_egg_clap MODULE boiled_egg_clap.cpp)
target_link_libraries(boiled_egg_clap PRIVATE boiled_egg::boiled_egg clap)
target_compile_features(boiled_egg_clap PRIVATE cxx_std_20)
set_target_properties(boiled_egg_clap PROPERTIES
  PREFIX ""
  OUTPUT_NAME "boiled_egg"
  CXX_VISIBILITY_PRESET hidden
  VISIBILITY_INLINES_HIDDEN YES
)

if(CMAKE_SYSTEM_NAME STREQUAL "Linux" OR CMAKE_SYSTEM_NAME STREQUAL "Windows")
  set_target_properties(boiled_egg_clap PROPERTIES SUFFIX ".clap")
elseif(CMAKE_SYSTEM_NAME STREQUAL "Darwin")
  set_target_properties(boiled_egg_clap PROPERTIES BUNDLE TRUE BUNDLE_EXTENSION clap)
endif()

if(CMAKE_SYSTEM_NAME STREQUAL "Linux")
  target_link_options(boiled_egg_clap PRIVATE -Wl,-z,defs)
endif()

if(BOILED_EGG_BUILD_TESTS AND UNIX AND NOT APPLE)
  add_executable(boiled_egg_clap_smoke test_clap_smoke.cpp)
  target_link_libraries(boiled_egg_clap_smoke PRIVATE clap ${CMAKE_DL_LIBS})
  target_compile_features(boiled_egg_clap_smoke PRIVATE cxx_std_20)
  add_test(NAME boiled_egg_clap_smoke
           COMMAND boiled_egg_clap_smoke $<TARGET_FILE:boiled_egg_clap>)
endif()
