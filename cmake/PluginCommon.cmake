# Shared one-voice processor/editor. Keep SDK-only builds independent of hosts.
if(NOT TARGET boiled_egg_plugin_common)
  add_subdirectory("${CMAKE_CURRENT_LIST_DIR}/../adapters/common"
                   "${CMAKE_BINARY_DIR}/adapters/common")
endif()
# This include can run from both sibling adapter scopes.
get_target_property(plugin_definitions boiled_egg_plugin_common INTERFACE_COMPILE_DEFINITIONS)
set(BOILED_EGG_PLUGIN_HAS_UI OFF)
if("BOILED_EGG_PLUGIN_X11=1" IN_LIST plugin_definitions)
  set(BOILED_EGG_PLUGIN_HAS_UI ON)
endif()
