# Offline CLI input preflight correction — 2026-09-20 JST

PR #40 / #19. Read together with OFFLINE_PV_RESULTS_2026-09-20.md, whose
acoustic numbers and process timings are explicitly attached to the original
plan/binary. They are not relabelled as measurements of this corrected binary.
Final repeated-grid comparison and exact HEAD/CI identities are recorded in
PR #40's final review and the retained experiment artifact.

## Real negative result and correction

The reused `tools/wav_io.cpp` reader can accept a truncated data chunk, leaving
zero-initialized bytes where data was missing. A safe bounded reproduction removed
64 bytes from the generated48k low-tone WAV while retaining its original header.
The pre-correction offline CLI returned0 and wrote a rendered WAV/report. This
was not a malformed header experiment requiring a multi-gigabyte allocation.
The input, old binary/source, command, output and report are retained.

Correction3533aec4 adds a bounded RIFF preflight to the NEW offline CLI only,
before invoking that reader. It checks exact RIFF length/type, every chunk's
file bounds including padding, duplicate/missing format or data, supported
sample format/rate/channels, consistent block alignment/byte rate, sample
boundaries, nonempty data and maximum30-second duration. A declared huge chunk
cannot reach the reused reader for an unchanged input file. It does not change
the common reader or certify other CLIs, and assumes the supplied file is not
concurrently replaced/modified between validation and use.

The identical truncated fixture now returns2, writes `status=blocked`, and
leaves no output.wav. Test addition ebc9926b includes7 malformed-file cases:
truncation, wrong RIFF length, huge declared chunk, partial sample, duplicate
data, duplicate format and missing format. Existing zero/NaN/stereo/rate/options/
no-overwrite cases remain. Core DSP, fixed magnitudes, phase update, resampler,
window/hop, iteration count, input grid and quality-stop thresholds are unchanged.

## Executed before corrected acoustic rerun

- All46 scoped Python tests pass, skip0 (previous45 plus1 method containing7
  malformed-WAV subcases). Pre-original-screen calibration remains41, not46.
- Corrected GCC20/GCC23/Clang20/Clang23/ASan+UBSan builds each pass5 core CTests
  and3 real CLI test methods, including malformed-file rejection.
- The unchanged SDK and old MR had complete26/26 and6/6 runs. A later20-second
  container-limited inventory attempt stopped after23/26 and is retained as
  incomplete, not successful. Subsequent inventory/JUnit-checked complete runs
  passed26/26 and6/6. No acoustic screen process was lost in this interruption.

## Corrected run is independently identified, not a new quality tuning pass

The corrected plan was registered BEFORE execution in Issue19 comment5746073214:
`07e7dd6415995cc569c25efbfc28e29c20a636ad09f519be8ceccbda2235eb41`.
It binds the rebuilt executable and changed CLI source. It retains every original
210 setting and3 repetitions for630 new whole-file runs. The previous plan
`acfdc09efada0a3e31937f70a5f0fad7f363ed48c07711d642ede62e2f8c0dfb`
and its630 actual outputs remain separately preserved. New run completion,
per-output byte comparison and new process timings must be read from their own
receipts; the old timing table is not a measurement of the new binary.

The existing32-iteration transient-width rejection and WSOLA low-tone Issue #41
must not be erased by this input repair. No candidate tuning on these fixtures,
no synthetic-to-MOS conversion and no product high-quality certification follows.
The offline renderer remains an explicit finite-file research mode, not an
SDK/GUI default. All278 previous project files remain untouched.
