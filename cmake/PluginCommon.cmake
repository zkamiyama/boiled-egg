# Shared one-voice processor/editor. Keep SDK-only builds independent of hosts.
if(NOT TARGET boiled_egg_plugin_common)
  add_subdirectory("${CMAKE_CURRENT_LIST_DIR}/../adapters/common"
                   "${CMAKE_BINARY_DIR}/adapters/common")
endif()
