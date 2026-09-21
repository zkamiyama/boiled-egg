# E1: existing SDK installation portability — 2026-09-21 JST

Related #56/#20/#15, PR57. Base main2a65a0da25ac4a3d9cfa920d90524a16fbb4319b,
tree ca347e119c5517fa34d8a80cdf7e1f641d27479c. The user paused heavy DSP research.
No new research algorithm, optimization experiment or unqualified NRT mode is
introduced. Unmerged research remains separate; no Google Drive writes.

## Fixed defect and scope

The old public export macro emitted `__declspec(dllimport)` for a Windows static
client. A C11 Windows-target assembly probe confirmed an `__imp_boiledegg_abi_version`
reference even with a proposed static flag. The new `BOILED_EGG_STATIC` branch
suppresses import/export decoration for static builds, and CMake exports the
`BOILED_EGG_STATIC=1` PUBLIC usage requirement. The probe now calls the direct
symbol for static clients and still emits the import reference for shared clients.
This local cross-target assembly check alone is not a native Windows link/run test.

Only CMakeLists.txt and the export-macro section of the public header are modified.
All functions, structs, enums, IDs, ABI/state, DSP implementation, presets,
latency/tail, plugins, GUI and transport retain their original contents/semantics.
There are326 entirely unchanged old files and8 additions (336 total). The public
header changes preprocessing/link decoration, not the C binary calling contract.
Source snapshots and exact tree comparisons verify that no rejected research patch
was accidentally applied.

## Installed-consumer gate

The stdlib Python driver installs to a new prefix and moves it to another path
containing spaces. It verifies file hashes, absence of the old prefix, absence of
build paths in installed metadata, imported target kind and static definitions.
Consumers are copied to an independent source directory and use only installed
public headers/libraries. Loader override variables are removed; Windows uses the
moved bin directory in this process's PATH, not a global environment change.

A negative temporarily removes the actual installed library. CMake must fail for
that missing file rather than silently finding another SDK. The library is restored
in a finally clause. A valid package then builds/runs exactly5 unique enabled tests:
3 existing backend/state/ramp contracts and2 new C11/RAII PCM tests. Inventory and
JUnit must agree, with no skip, missing binary or zero-test success. New output
folders only; existing evidence is never overwritten. Reports retain command
returncodes, logs, package hashes, platform and explicit hardware/DAW=false.

The new PCM tests use8192 nonzero, exactly representable samples,48/96k,32/64-frame
partitions, full push/pull/flush, preserved length and reset/repeat identity. The C
client also verifies right=.5*left, and C++ verifies move-only RAII/state access.
Energy is checked independently so an all-zero output cannot pass proportionality.
This is not an acoustic-quality or realistic long-session performance test.

## Actual local validation

|Configuration|Fresh SDK tests|Relocated consumer tests|Missing-library negative|
|---|---:|---:|---|
|static spectral OFF|13/13|5/5|rejected as expected|
|static spectral ON|26/26|5/5|rejected as expected|
|shared spectral OFF|13/13|5/5|rejected as expected|
|shared spectral ON|26/26|5/5|rejected as expected|

All counts are inventory/JUnit checked,skip0. Across these four packages the C/RAII
fixtures performed64 full nonzero renders in total. Maximum printed C error is
1.4901161193847656e-8; stereo proportional error0; reset outputs match exactly.
The C++ printed error rounds to1.49012e-8. These are unity numerical errors, not
pitch-shift quality or a claim of cross-compiler bit identity.

New8 Python controls plus6 existing CTest/scope-gate controls pass14/14,skip0.
Initially one negative test mocked subprocess.run broadly enough to intercept
platform.platform()'s `uname` call. Its original failure is retained; the test now
isolates platform discovery. No production test condition or DSP tolerance changed.

A separate clean baseline rebuild used the same environment andRelease settings.
All four output library files are byte-identical before/after, not just PCM-close:

|Library|SHA256, both baseline and new|
|---|---|
|shared OFF|aead137325bcb7e627a0e4371d9adea057b2c182fc867122848b1ef074b1bce8|
|shared ON|218abecb11273524ad41e42c97d93a7b88889c2a536ab6c74dee1a65ffb63cb8|
|static OFF|3a2044ed617ec9233176647a1b15d6d06c6561adf21a0f20fbe05ea363f6fbb7|
|static ON|e5a48d031d9e3006ca5a12af3adf882fb50a4f873be483d22f1c23c8c92f8fad|

Both shared export-surface checks pass. Therefore this Linux build's runtime DSP
and processing cost are unchanged. No benchmark extrapolation to other hardware
or new hard-realtime claim is made.

## Native platform CI and evidence boundaries

At code checkpoint29abb1e1a92d795e3aa009c926258a3227a119d1, the new PR workflow
35561985614 completed all12 native jobs: Linux ubuntu-24.04,Windows windows-2022,
macOS macos-14, each shared/static x spectral ON/OFF. Every job built the SDK,
ran8 portable gate controls, relocated the package and ran5 consumers plus the
missing-library negative. This is actual native execution, not just a YAML plan
or cross-compilation. The final reviewed HEAD and its required workflows/artifact
verification are recorded in PR57 and the latest Issue56 comment; this earlier
checkpoint is not relabelled as a later run.

The new workflow intentionally disables SDK tests/tools/bench for the package
build and then builds the5 independent installed tests. Existing SDK regression
workflows are separate; the local full13/26 inventories are also separate. It does
not pretend to execute the whole SDK, DAW or physical audio suite on every OS.
Receipts identify native platform/compiler and installed binaries. Binaries and
PCM are not asserted identical across operating systems.

## Review and remaining product work

The new, unrelated packaging code was accepted by the normal GitHub write tools.
The previously blocked research payload was not retried or encoded through a
workaround. One transfer used a not-yet-existing blob and was rejected with422;
a manual uncommitted header transcription was corrected before commit/ref update.
Each final remote tree was matched to the locally tested source; no bad header
was committed. These transfer errors are not DSP or CI failures.

Research Issues45–47 and52–55 are paused, not marked completed; candidate promotion
48/49 is on hold. Default WSOLA defect41 remains open. The next E/#20 work is
existing-host/device/application validation, not making the costly candidates a
new default. Linux X11/CLAP/VST3 prior results remain historical; this task does not
add Windows/macOS editors, certify manual DAW operation, physical DACs, unplug
recovery, prolonged playback, signing/notarization or redistribution rights.

See docs/SDK_INSTALLATION.md for commands and the separate PDC-mix/live-monitor/
offline-clip contracts. Project licensing is not assigned by this change. The
read-only evidence bundle includes source hashes, patches, actual local binaries,
logs, negative controls and downloaded CI receipts; no old quality-grid execution
is counted as a new result.
