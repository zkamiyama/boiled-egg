# Audition Lab integration gates — 2026-09-19

Review base: app/pyside6-audition-lab at 918e636d00c0add24a6ac34544b49d5f152f2356.
Main reference: d8e835d60e364f11dabbe9a23a531cdb29016b29. Issue31 / PR32.

This change prepares the standalone application and separate experimental file
transport for main, not promotion of a replacement audio backend. Existing
src/include/adapters/eval/research files and the default root build must remain
unchanged. The main SDK and plugins must not depend on PySide6 or this transport.

Before review-ready status:
- Reproduce then repair recoverable export/publication errors, cancellation and
  shutdown behavior. Never leave a newly published WAV without its required
  receipt after a failed SDK operation. Never delete pre-existing files.
- Keep the Qt event loop responsive during cancellation/shutdown. Do not remove
  temporary files while an owner thread or subprocess is still using them.
- Refresh audio devices by stable device identity; unplugging the selected device
  must not silently route audio to a different device. Preserve loaded source.
- Run independent worker/GUI negative tests and all existing bilingual tests.
- Exercise real Qt audio routing with an isolated software loopback where possible,
  with captured PCM checks. This is NOT verification of a DAC, speakers or latency.
- Verify native compiler20/23, address/undefined and independent-owner thread
  instrumentation, installed C11/C++ use, existing main regressions, held-tone and
  speed-range diagnostics, and relocated packaged execution.
- Keep complete results, failed attempts, exact source/package identities and
  original numerical thresholds. Mark readiness only for the measured scope.

Still separate from this integration: physical DAC/device acceptance, all
historical research methods ported to native freeze, natural-music subjective
promotion, Windows/macOS packaging and live-input retention policy. These remain
open work and must not be claimed complete or silently replaced by one method.
The shipping mode list must say six new native modes plus five existing SDK
profiles; external research WAV playback is not execution of those algorithms.
