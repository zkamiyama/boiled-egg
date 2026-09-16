# Roadmap C1: SDK-only preview integration — 2026-09-16

Base: stable main da66001ea2381a938f227a36fe0319d0dc429945.
Donor: verified integrated-stereo checkpoint bddc2eca9f0a2c9a801914df75dd34b76bed83e9
(PR28; subsequent 3ce9f3e0 is documentation only).

## Scope fixed before integration tests

Integrate only the public C/C++ spectral preview, its continuous pitch/time
controls and tests. Do not merge the research PR chain wholesale. Copy the donor
runtime/header bytes; keep all main adapter sources, plugin IDs/state/UI, WSOLA
kernel, profile implementation, legacy boiled_egg.h and existing evaluation
pipeline unchanged. GUI/host feature migration from PR9 is a separate C2 step.
The new spectral backend remains compile-time OFF and per-instance opt-in, with
its experimental capability status and current supported range. This is code
integration of a qualified numerical repair, not general acoustic promotion.

Do not add phase-gradient/edge/HPSS/transient research folders or old experimental
patches to main. Existing main research files are preserved unchanged. Private
PV support code is not installed in the public SDK and unsupported modes remain
rejected. Source selection must be explicit and machine checked.

## Acceptance (unchanged thresholds)

- Preserve old public structures/enums and all old dynamic symbols. Compile C11
  and C++ clients against the PREVIOUS headers and execute the same binaries
  with original, candidate-OFF and candidate-ON libraries. Compare complete
  deterministic legacy operation histories, runtime information, parameter state,
  invalid-operation behavior and default backend configuration. Same-toolchain
  output fingerprints are required; do not infer cross-compiler bit identity.
- All candidate src/include bytes equal the already verified donor. Compare 156
  static/dynamic preview histories to a same-toolchain donor build. New tests
  must reject missing, duplicated and changed records, not silently shrink grids.
- Direct GCC/Clang C++20/23 ON, OFF, static, address/undefined/thread sanitizer,
  allocation-free processing, installed C/C++ consumers and unchanged CLAP/VST3
  host CI. Build the current checkout, not only a separately patched dependency.
- Retain existing duration/pitch/alias/low-tone/stereo/ramp checks. Previous CPU
  evidence is inherited and not relabeled as a fresh benchmark. If runtime source
  is unchanged and integration replay agrees, no arbitrary DSP retuning is needed.
- Preserve main evaluation tools and anonymous-listening protocol. New ratings,
  native-zplane results or perceptual-model predictions are not generated here.

Keep this main-based PR in draft until the stated checks complete. A merge, if
made, enables no experimental processing by default and makes no general
sound-quality or portable realtime guarantee. Do not close broad roadmap B/C/D,
Issue1/2, or all historical research PRs merely because C1 passes.
