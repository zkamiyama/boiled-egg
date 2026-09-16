# Private spectral implementation provenance

`SOURCE_SHA256SUMS` records the **original import** for the static spectral
preview. It is intentionally not relabeled as a manifest of the subsequently
modified implementation. These headers and research symbols are private and are
not installed as a second public SDK.

The continuous-pitch feature adds `pitch_timeline.hpp` and changes `pv_rt.cpp`,
`pv_execution.inc` and `boiled_egg_research_execution.h` to connect the common
input-time map to immediate/cooperative synthesis and resampling. The public
wrapper enables it only with explicit continuous-pitch consent. The existing
static path is retained. The original import was taken from the previously
validated research implementation, not a third-party pitch-shift binary.

Current tree/file hashes are recorded by the validation workflow and the dated
evidence bundle. Do not run the original-import checksum file and then claim
that this edited kernel is byte-identical to the import. Same-kernel routing
tests establish wrapper consistency, not independent acoustic correctness.

See `docs/DYNAMIC_PITCH_EDITOR.md` and the dated validation report for contracts,
limitations, source checkpoints and test evidence.
