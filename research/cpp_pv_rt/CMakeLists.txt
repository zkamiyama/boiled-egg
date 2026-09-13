cmake_minimum_required(VERSION 3.20)
project(boiled_egg_research_pv_rt VERSION 0.1.0 LANGUAGES C CXX)

option(BOILED_EGG_PV_RT_BUILD_TESTS "Build tests" ON)
option(BOILED_EGG_PV_RT_BUILD_CLI "Build CLI" ON)

add_library(boiled_egg_research_pv_rt STATIC
    src/fft.cpp
    src/profile.cpp
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

add_library(boiled_egg_research_multires_rt STATIC
    src/multires_rt.cpp
)
target_compile_features(boiled_egg_research_multires_rt PUBLIC cxx_std_20)
target_include_directories(boiled_egg_research_multires_rt
    PUBLIC "$<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>"
)
target_compile_options(boiled_egg_research_multires_rt PRIVATE
    $<$<CXX_COMPILER_ID:GNU,Clang>:-Wall;-Wextra;-Wpedantic;-Wconversion;-Wshadow>
)
target_link_libraries(boiled_egg_research_multires_rt PUBLIC boiled_egg_research_pv_rt)

if(BOILED_EGG_PV_RT_BUILD_CLI)
    add_executable(boiled_egg_pv_rt_cli src/main.cpp src/wav.cpp)
    target_compile_features(boiled_egg_pv_rt_cli PRIVATE cxx_std_20)
    target_include_directories(boiled_egg_pv_rt_cli PRIVATE include src)
    target_link_libraries(boiled_egg_pv_rt_cli PRIVATE boiled_egg_research_pv_rt)

    add_executable(boiled_egg_multires_rt_cli src/multires_main.cpp src/wav.cpp)
    target_compile_features(boiled_egg_multires_rt_cli PRIVATE cxx_std_20)
    target_include_directories(boiled_egg_multires_rt_cli PRIVATE include src)
    target_link_libraries(boiled_egg_multires_rt_cli PRIVATE boiled_egg_research_multires_rt)
endif()

if(BOILED_EGG_PV_RT_BUILD_TESTS)
    enable_testing()
    foreach(test fuzzy_test fuzzy_noalloc)
        add_executable(boiled_egg_${test} tests/${test}.cpp)
        target_compile_features(boiled_egg_${test} PRIVATE cxx_std_20)
        target_link_libraries(boiled_egg_${test} PRIVATE boiled_egg_research_pv_rt)
        add_test(NAME boiled_egg_${test} COMMAND boiled_egg_${test})
    endforeach()
    add_executable(boiled_egg_fuzzy_c_api tests/fuzzy_c_api.c)
    target_link_libraries(boiled_egg_fuzzy_c_api PRIVATE boiled_egg_research_pv_rt)
    add_test(NAME boiled_egg_fuzzy_c_api COMMAND boiled_egg_fuzzy_c_api)
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

    add_executable(boiled_egg_multires_rt_test tests/multires_test.cpp)
    target_compile_features(boiled_egg_multires_rt_test PRIVATE cxx_std_20)
    target_link_libraries(boiled_egg_multires_rt_test PRIVATE boiled_egg_research_multires_rt)
    add_test(NAME boiled_egg_multires_rt_test COMMAND boiled_egg_multires_rt_test)

    add_executable(boiled_egg_multires_rt_noalloc_test tests/multires_noalloc.cpp)
    target_compile_features(boiled_egg_multires_rt_noalloc_test PRIVATE cxx_std_20)
    target_link_libraries(boiled_egg_multires_rt_noalloc_test PRIVATE boiled_egg_research_multires_rt)
    add_test(NAME boiled_egg_multires_rt_noalloc_test COMMAND boiled_egg_multires_rt_noalloc_test)

    add_executable(boiled_egg_multires_rt_c_api_test tests/multires_c_api.c)
    target_link_libraries(boiled_egg_multires_rt_c_api_test PRIVATE boiled_egg_research_multires_rt)
    add_test(NAME boiled_egg_multires_rt_c_api_test COMMAND boiled_egg_multires_rt_c_api_test)
endif()

add_executable(boiled_egg_pv_rt_bench tests/bench.cpp)
target_compile_features(boiled_egg_pv_rt_bench PRIVATE cxx_std_20)
target_link_libraries(boiled_egg_pv_rt_bench PRIVATE boiled_egg_research_pv_rt)

add_executable(boiled_egg_pv_rt_formant_bench tests/formant_bench.cpp)
target_compile_features(boiled_egg_pv_rt_formant_bench PRIVATE cxx_std_20)
target_link_libraries(boiled_egg_pv_rt_formant_bench PRIVATE boiled_egg_research_pv_rt)

add_executable(boiled_egg_pv_rt_window_bench tests/window_bench.cpp)
target_compile_features(boiled_egg_pv_rt_window_bench PRIVATE cxx_std_20)
target_link_libraries(boiled_egg_pv_rt_window_bench PRIVATE boiled_egg_research_pv_rt)

add_executable(boiled_egg_multires_rt_bench tests/multires_bench.cpp)
target_compile_features(boiled_egg_multires_rt_bench PRIVATE cxx_std_20)
target_link_libraries(boiled_egg_multires_rt_bench PRIVATE boiled_egg_research_multires_rt)

if(CMAKE_SYSTEM_NAME STREQUAL "Linux")
    add_executable(boiled_egg_fuzzy_bench tests/fuzzy_bench.cpp)
    target_compile_features(boiled_egg_fuzzy_bench PRIVATE cxx_std_20)
    target_link_libraries(boiled_egg_fuzzy_bench PRIVATE boiled_egg_research_pv_rt)
endif()

if(BOILED_EGG_PV_RT_BUILD_TESTS)
    foreach(test features_test features_noalloc)
        add_executable(boiled_egg_${test} tests/${test}.cpp)
        target_link_libraries(boiled_egg_${test} PRIVATE boiled_egg_research_multires_rt)
        add_test(NAME boiled_egg_${test} COMMAND boiled_egg_${test})
    endforeach()
    add_executable(boiled_egg_features_c_api tests/features_c_api.c)
    target_link_libraries(boiled_egg_features_c_api PRIVATE boiled_egg_research_multires_rt)
    add_test(NAME boiled_egg_features_c_api COMMAND boiled_egg_features_c_api)
endif()

if(CMAKE_SYSTEM_NAME STREQUAL "Linux")
    add_executable(boiled_egg_features_bench tests/features_bench.cpp)
    target_link_libraries(boiled_egg_features_bench PRIVATE boiled_egg_research_multires_rt)
endif()

option(BOILED_EGG_DISABLE_SIMD "Force portable scalar kernels" OFF)
if(BOILED_EGG_DISABLE_SIMD)
    target_compile_definitions(boiled_egg_research_pv_rt PRIVATE BOILED_EGG_DISABLE_SIMD=1)
endif()
if(BOILED_EGG_PV_RT_BUILD_TESTS)
    foreach(test fft_slices execution_test execution_noalloc)
        add_executable(boiled_egg_${test} tests/${test}.cpp)
        target_link_libraries(boiled_egg_${test} PRIVATE boiled_egg_research_multires_rt)
        add_test(NAME boiled_egg_${test} COMMAND boiled_egg_${test})
    endforeach()
endif()

if(CMAKE_SYSTEM_NAME STREQUAL "Linux")
    add_executable(boiled_egg_execution_bench tests/execution_bench.cpp)
    target_link_libraries(boiled_egg_execution_bench PRIVATE boiled_egg_research_multires_rt)
endif()
