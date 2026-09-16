include(${CMAKE_CURRENT_LIST_DIR}/../../cmake/PluginCommon.cmake)
if(CMAKE_VERSION VERSION_LESS 3.25)
  message(FATAL_ERROR "BOILED_EGG_BUILD_VST3 requires CMake 3.25+ (VST SDK 3.8 requirement)")
endif()

include(FetchContent)

# VST SDK 3.8.0, pinned donor dependency. Validator is not disabled.
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
target_link_libraries(boiled_egg_vst3 PRIVATE boiled_egg_plugin_common sdk)
target_compile_features(boiled_egg_vst3 PRIVATE cxx_std_20)

if(BOILED_EGG_BUILD_TESTS AND CMAKE_SYSTEM_NAME STREQUAL "Linux")
  add_executable(boiled_egg_vst3_pitch_test test_vst3_pitch_ui.cpp
    ${vst3sdk_SOURCE_DIR}/public.sdk/source/common/memorystream.cpp
    ${vst3sdk_SOURCE_DIR}/public.sdk/source/vst/hosting/module.cpp
    ${vst3sdk_SOURCE_DIR}/public.sdk/source/vst/hosting/module_linux.cpp)
  target_link_libraries(boiled_egg_vst3_pitch_test PRIVATE boiled_egg_plugin_common sdk_hosting sdk ${CMAKE_DL_LIBS})
  target_link_options(boiled_egg_vst3_pitch_test PRIVATE -Wl,--export-dynamic)
  set(pitch_bundle "${CMAKE_BINARY_DIR}/VST3/Release/boiled egg.vst3")
  add_test(NAME boiled_egg_vst3_pitch_test COMMAND boiled_egg_vst3_pitch_test "${pitch_bundle}")
  if(BOILED_EGG_PLUGIN_HAS_UI)
    find_program(XVFB_RUN xvfb-run)
    if(XVFB_RUN)
      add_test(NAME boiled_egg_vst3_editor_test COMMAND ${XVFB_RUN} -a $<TARGET_FILE:boiled_egg_vst3_pitch_test> "${pitch_bundle}" --ui)
    endif()
  endif()
endif()
