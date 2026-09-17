# C2 host integration contract — 2026-09-17

Roadmap #15 / #18. Base main c6cb312903006e3a1ca24c034c291ef0e8fc9d81 already
contains the opt-in spectral SDK. Reuse only adapters/common, adapters/clap and
adapters/vst3 from the previously verified f8e5ef2cbce84f396597860a408b4a3084796115
snapshot. Do not merge the research branch or change src/include DSP/API files.

## Scope

Connect the existing one-voice Linux X11 editor and shared processor to current
main. Preserve plugin class/descriptor IDs, original pitch parameter IDs and
normalization, and version1 state loading with WSOLA semantics. Add explicit
pitch fine/formant/fine, wet/dry, wet volume/pan, bypass, backend/quality/policy
controls and version2 state. Backend/quality/policy changes require host
reactivation; no audio-callback DSP construction. Wet/dry/bypass share declared
latency. Spectral build default OFF and per-instance opt-in remain.

## Gates fixed before validation

- All src/include files remain byte-identical to main. No new audio algorithm.
- Build actual CLAP and VST3 modules, load them through their ABI, exercise
  automation, legacy/new state, restart/latency and GUI lifecycle.
- Preserve legacy pitch-only waveform behavior in an independent main-SDK
  comparison, not merely by reading matching constants. Record any differences.
- UI edits must bracket host gestures and propagate reconfiguration requests;
  a restart does not allocate in process. Invalid batches/states must not leave
  partial mutations. No silent backend substitution when preview is unavailable.
- Existing/current no-allocation and block-size tests, GCC/Clang C++20/23,
  ASan/UBSan and thread checks where supported; report unavailable checks rather
  than claiming success. Exercise preview ON/OFF and UI/headless configurations.
- Actual X11 interaction, Steinberg validator and installed SDK regressions.
- New tests must fail when their diagnosed defect is restored, when practical.

Do not claim manual DAW qualification, Windows/macOS/Wayland UI, multiple voices,
new listening responses, perceptual predictor inference or native-zplane results.
C2 is host feature integration, not broad acoustic promotion. Keep stable main
unchanged until the reviewable integration passes its tests. Historical donor
results are not new measurements. Preserve meaningful progress in small commits.
