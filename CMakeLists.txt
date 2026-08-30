cmake_minimum_required(VERSION 3.20)
project(boiled_egg VERSION 0.1.2 LANGUAGES C CXX)

option(BOILED_EGG_BUILD_SHARED "Build shared library" ON)
option(BOILED_EGG_BUILD_TESTS "Build tests" ON)
option(BOILED_EGG_BUILD_TOOLS "Build CLI tools" ON)
option(BOILED_EGG_BUILD_BENCH "Build benchmarks" ON)
option(BOILED_EGG_BUILD_CLAP "Build the CLAP reference plugin adapter" OFF)
option(BOILED_EGG_SANITIZE "Enable ASan/UBSan" OFF)
option(BOILED_EGG_THREAD_SANITIZE "Enable ThreadSanitizer" OFF)

set(CMAKE_CXX_STANDARD 20 CACHE STRING "C++ standard (20 or 23)")
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)
set(CMAKE_C_STANDARD 11)
set(CMAKE_C_STANDARD_REQUIRED ON)

if(BOILED_EGG_SANITIZE AND BOILED_EGG_THREAD_SANITIZE)
  message(FATAL_ERROR "ASan/UBSan and ThreadSanitizer must use separate builds")
endif()
if(BOILED_EGG_SANITIZE AND NOT MSVC)
  add_compile_options(-fsanitize=address,undefined -fno-omit-frame-pointer)
  add_link_options(-fsanitize=address,undefined)
endif()
if(BOILED_EGG_THREAD_SANITIZE AND NOT MSVC)
  add_compile_options(-fsanitize=thread -fno-omit-frame-pointer)
  add_link_options(-fsanitize=thread)
endif()

set(BOILED_EGG_SOURCES
    src/boiled_egg.cpp
    src/engine.cpp
)

if(BOILED_EGG_BUILD_SHARED)
  add_library(boiled_egg SHARED ${BOILED_EGG_SOURCES})
else()
  add_library(boiled_egg STATIC ${BOILED_EGG_SOURCES})
endif()
add_library(boiled_egg::boiled_egg ALIAS boiled_egg)

target_include_directories(boiled_egg
  PUBLIC
    $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
    $<INSTALL_INTERFACE:include>
  PRIVATE src
)
target_compile_features(boiled_egg PUBLIC cxx_std_20)
target_compile_definitions(boiled_egg PRIVATE BOILED_EGG_BUILDING_LIBRARY=1)
set_target_properties(boiled_egg PROPERTIES CXX_VISIBILITY_PRESET hidden VISIBILITY_INLINES_HIDDEN YES)

if(MSVC)
  target_compile_options(boiled_egg PRIVATE /W4 /permissive-)
else()
  target_compile_options(boiled_egg PRIVATE -Wall -Wextra -Wpedantic -Wconversion -Wshadow)
endif()

if(BOILED_EGG_BUILD_TOOLS)
  add_executable(boiled_egg_cli tools/boiled_egg_cli.cpp tools/wav_io.cpp)
  target_link_libraries(boiled_egg_cli PRIVATE boiled_egg::boiled_egg)
  target_include_directories(boiled_egg_cli PRIVATE tools)
endif()

if(BOILED_EGG_BUILD_BENCH)
  add_executable(boiled_egg_bench bench/boiled_egg_bench.cpp)
  target_link_libraries(boiled_egg_bench PRIVATE boiled_egg::boiled_egg)
endif()

if(BOILED_EGG_BUILD_TESTS)
  enable_testing()
  add_executable(boiled_egg_tests tests/test_core.cpp)
  target_link_libraries(boiled_egg_tests PRIVATE boiled_egg::boiled_egg)
  add_test(NAME boiled_egg_tests COMMAND boiled_egg_tests)

  add_executable(boiled_egg_c_abi_test tests/test_c_abi.c)
  target_link_libraries(boiled_egg_c_abi_test PRIVATE boiled_egg::boiled_egg)
  set_target_properties(boiled_egg_c_abi_test PROPERTIES LINKER_LANGUAGE CXX)
  add_test(NAME boiled_egg_c_abi_test COMMAND boiled_egg_c_abi_test)

  add_executable(boiled_egg_noalloc_test tests/test_noalloc.cpp)
  target_link_libraries(boiled_egg_noalloc_test PRIVATE boiled_egg::boiled_egg)
  add_test(NAME boiled_egg_noalloc_test COMMAND boiled_egg_noalloc_test)

  add_executable(boiled_egg_stress_test tests/test_stress.cpp)
  target_link_libraries(boiled_egg_stress_test PRIVATE boiled_egg::boiled_egg)
  add_test(NAME boiled_egg_stress_test COMMAND boiled_egg_stress_test)

  add_executable(boiled_egg_resampler_alias_test tests/test_resampler_alias.cpp)
  target_link_libraries(boiled_egg_resampler_alias_test PRIVATE boiled_egg::boiled_egg)
  add_test(NAME boiled_egg_resampler_alias_test COMMAND boiled_egg_resampler_alias_test)

  add_executable(boiled_egg_block_consistency_test tests/test_block_consistency.cpp)
  target_link_libraries(boiled_egg_block_consistency_test PRIVATE boiled_egg::boiled_egg)
  add_test(NAME boiled_egg_block_consistency_test COMMAND boiled_egg_block_consistency_test)

  find_package(Threads REQUIRED)
  add_executable(boiled_egg_threading_test tests/test_threading.cpp)
  target_link_libraries(boiled_egg_threading_test PRIVATE boiled_egg::boiled_egg Threads::Threads)
  add_test(NAME boiled_egg_threading_test COMMAND boiled_egg_threading_test)

  add_executable(boiled_egg_daw_host_test tests/test_daw_host.cpp)
  target_link_libraries(boiled_egg_daw_host_test PRIVATE boiled_egg::boiled_egg)
  add_test(NAME boiled_egg_daw_host_test COMMAND boiled_egg_daw_host_test)
endif()

if(BOILED_EGG_BUILD_CLAP)
  add_subdirectory(adapters/clap)
endif()

include(GNUInstallDirs)
include(CMakePackageConfigHelpers)
configure_package_config_file(
  cmake/boiled_eggConfig.cmake.in
  ${CMAKE_CURRENT_BINARY_DIR}/boiled_eggConfig.cmake
  INSTALL_DESTINATION ${CMAKE_INSTALL_LIBDIR}/cmake/boiled_egg
)
write_basic_package_version_file(
  ${CMAKE_CURRENT_BINARY_DIR}/boiled_eggConfigVersion.cmake
  VERSION ${PROJECT_VERSION}
  COMPATIBILITY SameMajorVersion
)
install(TARGETS boiled_egg
  EXPORT boiled_eggTargets
  LIBRARY DESTINATION ${CMAKE_INSTALL_LIBDIR}
  ARCHIVE DESTINATION ${CMAKE_INSTALL_LIBDIR}
  RUNTIME DESTINATION ${CMAKE_INSTALL_BINDIR}
)
install(DIRECTORY include/ DESTINATION ${CMAKE_INSTALL_INCLUDEDIR})
install(EXPORT boiled_eggTargets
  FILE boiled_eggTargets.cmake
  NAMESPACE boiled_egg::
  DESTINATION ${CMAKE_INSTALL_LIBDIR}/cmake/boiled_egg
)

install(FILES
  ${CMAKE_CURRENT_BINARY_DIR}/boiled_eggConfig.cmake
  ${CMAKE_CURRENT_BINARY_DIR}/boiled_eggConfigVersion.cmake
  DESTINATION ${CMAKE_INSTALL_LIBDIR}/cmake/boiled_egg
)
