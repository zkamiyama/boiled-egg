if(CMAKE_VERSION VERSION_LESS 3.25)
  message(FATAL_ERROR "BOILED_EGG_BUILD_VST3 requires CMake 3.25+ (VST SDK 3.8 requirement)")
endif()

include(FetchContent)

# VST SDK 3.8.0 (official Steinberg commit, 2025-10-20). Keep examples and
# VSTGUI disabled; validator/moduleinfotool are still provided by the SDK and
# are used automatically by smtg_add_vst3plugin when enabled.
set(SMTG_ENABLE_VST3_PLUGIN_EXAMPLES OFF CACHE BOOL "" FORCE)
set(SMTG_ENABLE_VST3_HOSTING_EXAMPLES OFF CACHE BOOL "" FORCE)
set(SMTG_ENABLE_VSTGUI_SUPPORT OFF CACHE BOOL "" FORCE)
set(SMTG_CREATE_PLUGIN_LINK OFF CACHE BOOL "" FORCE)
set(SMTG_RUN_VST_VALIDATOR ON CACHE BOOL "" FORCE)
set(SMTG_CREATE_MODULE_INFO ON CACHE BOOL "" FORCE)

FetchContent_Declare(
  vst3sdk
  GIT_REPOSITORY https://github.com/steinbergmedia/vst3sdk.git
  GIT_TAG 9fad9770f2ae8542ab1a548a68c1ad1ac690abe0
  GIT_SUBMODULES_RECURSE TRUE
)
FetchContent_MakeAvailable(vst3sdk)
smtg_enable_vst3_sdk()

set(boiled_egg_vst3_sources
  boiled_egg_vst3.cpp
  ${vst3sdk_SOURCE_DIR}/public.sdk/source/vst/vstsinglecomponenteffect.cpp
  ${vst3sdk_SOURCE_DIR}/public.sdk/source/vst/vstsinglecomponenteffect.h
)

smtg_add_vst3plugin(boiled_egg_vst3
  PACKAGE_NAME "boiled egg"
  SOURCES_LIST ${boiled_egg_vst3_sources}
)
target_link_libraries(boiled_egg_vst3 PRIVATE boiled_egg::boiled_egg sdk)
target_compile_features(boiled_egg_vst3 PRIVATE cxx_std_20)
