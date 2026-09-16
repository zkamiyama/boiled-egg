# C2 plugin integration contract — 2026-09-16

Roadmap #15 / #18. Base main c6cb312903006e3a1ca24c034c291ef0e8fc9d81.
Port only adapters/common, adapters/clap and adapters/vst3 from the tested
PR9 donor b5bda2f0cb83396fea7f828c902637e7dc858c4c. No src/include DSP changes,
research-tree import or historical patch application. Keep compiler opt-in for
the spectral SDK and explicit backend selection; new plugins default to WSOLA.

## User-visible change

One-voice Linux X11 editor, pitch/fine, independent formant/fine, Wet/Dry,
voice level, pan, bypass and explicit backend/quality/formant policy.
No multi-voice Add button, Windows/macOS/Wayland editor or live-low-latency claim.
Preserve plugin IDs, original pitch ID/range/normalization, and legacy CLAP16-byte
and VST3 12-byte state meaning. New saves use version2; older plugin binaries are
not claimed capable of reading new saves. Configuration changes take effect only
at host reactivation, never by allocating a new DSP in the audio callback.

## Tests fixed before migration

- Verify all src/include files exactly match main, and imported adapter files
  match the donor before any separately documented integration correction.
- Build actual CLAP and VST3 against current main SDK, ON and OFF; UI ON/OFF.
  Test loaded modules, not only a shared processor. VST3 official validator remains.
- Exercise state roundtrip/legacy migration, parameter IDs and normalization,
  sorted sample-offset events, unsupported combinations, null/zero-frame calls,
  latency reactivation and compensated Dry/Bypass. Retain failed tests.
- Verify default WSOLA output against main, and adopted processor output against
  donor on same-toolchain fixed grids; separate signal identity from sound quality.
- GCC/Clang C++20/23, ASan/UBSan, processing allocation checks and TSan where the
  execution environment supports it. Report unsupported/failed execution honestly.
- Check native GUI gestures, focus/hide/resize/timer lifetime under Xvfb; record an
  actual screenshot, not a mock. No manual commercial-DAW qualification is implied.
- Existing C1 SDK-only extraction checks are historical in their protected-adapter
  scope. Preserve SDK/ABI checks and make any C2 CI scope adjustment explicit;
  do not call changed adapters identical to old main.

Do not automatically merge research PRs or claim native-zplane/MOS improvement.
Publish coherent commits and a reviewable C2 PR; stable main is unchanged until
its own reviewed integration decision. A correct host migration need not wait
for new listener ratings. Any new defect discovered during the port is fixed in
a separate commit with a failing-before/passing-after regression.
