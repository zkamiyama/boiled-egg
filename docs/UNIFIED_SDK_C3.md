# Unified SDK C3 — 2026-09-19

Parent #33. User explicitly permits breaking old APIs, state and PCM identity,
provided the current VST3, CLAP and bilingual audition application keep working.
Do not confuse old boiled-egg compatibility with host-format compliance.

## Ordered work

1. #34: separate source ownership from DSP; one SDK library/build/install.
2. #35: converge frame synthesis and output-clock control; bounded live capture,
   hold and resume using the same DSP as file playback.
3. #36: migrate all three consumers to the common API and capability registry.
4. #37: qualify functionality, acoustic regressions and practical CPU budgets;
   remove obsolete duplicate engines/CLI dependencies from normal distribution.

This first branch starts from the reviewed bilingual app 918e636d, whose SDK is
main d8e835d6. It does not merge the app into main or declare C3 finished.

## First implementation contract

Build file transport inside libboiled_egg, compile the existing FFT source once
when both processing paths are present, and install C/RAII headers together.
Move the application's native binding to that library. Retire the separate
transport-library packaging target, not merely rename its artifact.

Extract prepared-file ownership and a non-owning sample view. Implement a bounded
rolling source and independent preallocated capture using that view. The rolling
writer validates a whole supplied batch before mutation. Reads distinguish known
boundary padding from future input and expired/overwritten history. A capture
remains valid as the ring overwrites old data; capture failure is transactional.
Single-owner access is explicit; these objects do not make concurrent writes safe.

Connect the file transport's spectral and time-domain sample reads to the new
source abstraction. Rolling/capture storage tests alone do NOT establish a working
live freeze effect: frame availability, scheduling, resume crossfades and host
latency still belong to #35. Native and streaming phase/WSOLA implementations
remain distinct until that step. One shared object is not full DSP convergence.

## Verification

C++20/23 GCC/Clang; ASan/UBSan; allocation checks after construction; independent
rolling/capture reference including wrap, overruns, future reads, empty input,
NaN/Inf and missing-range rejection. C11/RAII installed consumers exercise both
SDK entry points in the same library. Keep current host/app tests; add package
checks that reject a second transport library and shared-object fallback.
Use existing analytical freeze/range tests as regression, not new quality claims.
Old PCM identity may be useful diagnosis but is not the architectural acceptance
condition. Report all incomplete work and actual CI/local scope separately.
