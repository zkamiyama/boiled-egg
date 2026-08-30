cmake_minimum_required(VERSION 3.20)
project(boiled_egg_research_pv_rt VERSION 0.1.0 LANGUAGES C CXX)

option(BOILED_EGG_PV_RT_BUILD_TESTS "Build tests" ON)
option(BOILED_EGG_PV_RT_BUILD_CLI "Build CLI" ON)

add_library(boiled_egg_research_pv_rt STATIC
    src/fft.cpp
    src/pv_rt.cpp
)
target_compile_features(boiled_egg_research_pv_rt PUBLIC cxx_std_20)
target_include_directories(boiled_egg_research_pv_rt
    PUBLIC "$<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>"
    PRIVATE "${CMAKE_CURRENT_SOURCE_DIR}/src"
)
target_compile_options(boiled_egg_research_pv_rt PRIVATE
    $<$<CXX_COMPILER_ID:GNU,Clang>:-Wall;-Wextra;-Wpedantic;-Wconversion;-Wshadow>
)

if(BOILED_EGG_PV_RT_BUILD_CLI)
    add_executable(boiled_egg_pv_rt_cli src/main.cpp src/wav.cpp)
    target_compile_features(boiled_egg_pv_rt_cli PRIVATE cxx_std_20)
    target_include_directories(boiled_egg_pv_rt_cli PRIVATE include src)
    target_link_libraries(boiled_egg_pv_rt_cli PRIVATE boiled_egg_research_pv_rt)
endif()

if(BOILED_EGG_PV_RT_BUILD_TESTS)
    enable_testing()
    add_executable(boiled_egg_pv_rt_test tests/test.cpp)
    target_compile_features(boiled_egg_pv_rt_test PRIVATE cxx_std_20)
    target_link_libraries(boiled_egg_pv_rt_test PRIVATE boiled_egg_research_pv_rt)
    add_test(NAME boiled_egg_pv_rt_test COMMAND boiled_egg_pv_rt_test)

    add_executable(boiled_egg_pv_rt_noalloc_test tests/noalloc.cpp)
    target_compile_features(boiled_egg_pv_rt_noalloc_test PRIVATE cxx_std_20)
    target_link_libraries(boiled_egg_pv_rt_noalloc_test PRIVATE boiled_egg_research_pv_rt)
    add_test(NAME boiled_egg_pv_rt_noalloc_test COMMAND boiled_egg_pv_rt_noalloc_test)

    add_executable(boiled_egg_pv_rt_c_api_test tests/c_api.c)
    target_link_libraries(boiled_egg_pv_rt_c_api_test PRIVATE boiled_egg_research_pv_rt)
    add_test(NAME boiled_egg_pv_rt_c_api_test COMMAND boiled_egg_pv_rt_c_api_test)
endif()

add_executable(boiled_egg_pv_rt_bench tests/bench.cpp)
target_compile_features(boiled_egg_pv_rt_bench PRIVATE cxx_std_20)
target_link_libraries(boiled_egg_pv_rt_bench PRIVATE boiled_egg_research_pv_rt)
