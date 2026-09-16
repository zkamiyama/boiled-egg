#pragma once
#include <boiled_egg/boiled_egg.h>
namespace boiled_egg::detail {
// Private exception type; never throw a public enum across internal translation
// units, because its RTTI can otherwise leak into the shared-library exports.
struct BackendConstructionError { boiledegg_result status; };
}
