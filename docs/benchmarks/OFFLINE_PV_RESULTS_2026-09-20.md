# Offline PV research screen: results — 2026-09-20 JST

Related #19/#17, parent #15; PR #40. Base main
`8143a19b1a7681cc0815b3f14a5c20694f2b052f`, tree
`fb60d486ee2117485ad2d853b840006dda51bc2a`.
Protocol `8216e43ac59aa6acf6875cd23c66d3daaea71606` precedes acoustic measurement.
Local plan SHA256 `acfdc09efada0a3e31937f70a5f0fad7f363ed48c07711d642ede62e2f8c0dfb`
was registered in Issue19 comment5745961341 before execution. This is a fixed,
exploratory synthetic screen, not an independent confirmation dataset.

## Decision

Accept only an isolated, explicitly opted-in **offline research tool** and its
calibrated comparison evidence. **Reject promotion of the fixed-window iterative
candidate to a product high-quality mode.** Keep the real-time SDK, public ABI,
state/IDs/latency/tail/default WSOLA/spectral opt-in, plugins, transport and app
unchanged. All278 pre-existing files are byte-identical in the local scope check.
The old MR branch is a separately built control, not merged back into main.

32 iterations fail the predeclared burst-width stop condition in2 cells.
8 iterations avoid those particular paired stops but still have large absolute
transient errors and close-tone residual regressions. Passing a paired check
against a bad seed is not sufficient for product qualification. Both remain
research-only. `quality_selection=null`; no new MOS or predictor was used.

## Actual implementation and controls

New C++20/23 `research/offline_pv` implements a whole-file centered PV seed and
fixed-magnitude Griffin-Lim-style reanalysis/overlap-add refinement, with explicit
0/8/32 iteration selection. FFT4096/hop256 at48k, FFT8192/hop512 at96k. Our
centered65-position Blackman-windowed sinc performs final pitch resampling;
intermediate duration is T*p. This is an engineering combination, NOT SELEBI,
not a reproduction of the current SDK spectral backend, and not learned DSP.
It reuses the existing FFT and WAV reader/writer without modifying them.

The initial interface accepts mono48/96k, formantOff, constant T0.5–2 and pitch
+/-12st, up to30 seconds subject to512MiB estimated work budget and24MB input
file cap. Those are parser/capability bounds, NOT quality certification of that
entire space. This acoustic screen is only T1 and pitches-12/0/+12. There is no
live/freeze/automation/stereo/formant-preservation support. It is a synchronous
CLI, not yet an asynchronous offline product job API, GUI tab, or public C ABI.

Seven actual paths were exercised: current SDK WSOLA General, PV General,
PV Transient; historical native MR from
`dd04c9388443ff3358af34b85ca5a5c880f45e71`; new offline0/8/32.
Legacy115 source hashes and tree9ce604004156f1f15ce1b5464f8cd27f0e3b04fb were
verified via workflow artifact10593647173. Its low1024/256+high512/192,
6500Hz complementary crossover,129tap configuration was preserved at both rates,
exactly as that code implements it, rather than silently rate-scaling or using
the unrelated Python multiresolution mix. This matters when interpreting96k.

## Complete grid and execution

5 generated0.75-second fixtures (61Hz tone,223Hz harmonic stack,997/1031Hz close
pair, two4000Hz Gaussian-windowed bursts, burst+223Hz mixture) x48/96k x
-12/0/+12st x7 paths =210 cells. Each cell had3 serial fresh-process complete
renders, totaling630/630. All210 cells produced identical float WAV bytes in
all3 repetitions. Input/output metadata, finite/nonempty/nonzero output and
exact output length passed throughout. **Execution success is not quality success.**

Stationary diagnostics use0.15–0.60 seconds. Joint sinusoid projections measure
amplitude and unexplained energy but never alter output gain or align its lag.
The61Hz case uses an unrestricted dominant spectral peak, not a search window
forced near the target. Burst centroids and5–95% energy widths use fixed+/-80ms
windows, retaining raw position error and outside+/-10ms energy. The mixed
fixture has raw peak/RMS checks only: no invented component isolation by
subtracting differently processed signals. All raw WAVs remain available.

## Current/legacy comparison: scoped deficits, not naturalness rankings

| Path |61Hz pitch criterion <=5cents,6 cases|Maximum absolute dominant-frequency error(cents)|Maximum burst-centroid error(ms)|Maximum5–95% width(ms)|
|---|---:|---:|---:|---:|
|SDK WSOLA General|2/6|1202.672536|12.582954|6.541667|
|SDK PV General|6/6|0.003703|0.006567|20.135417|
|SDK PV Transient|6/6|0.003579|0.008275|10.479167|
|Historical native MR|4/6|702.840637|10.665975|10.479167|
|Offline0|6/6|0.001147|45.287765|69.854167|
|Offline8|6/6|0.025324|42.537335|43.541667|
|Offline32|6/6|0.083148|13.539329|43.500000|

Widths/positions above include both isolated events and all6 rate/pitch
configurations per path. The unmodified fixture's energy width is3.5ms. A width
alone is not a unique ideal waveform or full naturalness score; it must be read
with position, spectral distortion and raw audio.

The current Transient control reduces this screen's worst width versus General
while retaining the tested low-tone frequency accuracy. It is not universally
better spectrally: median unexplained stationary energy across12 nonidentity
stationary cells is1.274753e-5 for General and3.811044e-4 for Transient. Do not
collapse different signals and metrics into a universal winner.

WSOLA fails the61Hz nonidentity frequency criterion in all4 tested cases.
At+12st the target is122Hz but dominant peaks remain near61Hz; at48k there are
also similarly strong peaks near126.5Hz and183Hz. Raw spectra were cross-checked
with a separately evaluated denser FFT and retained in the local evidence.
This is a concrete, pre-existing SDK defect/limitation to investigate, not a
regression caused by this PR (SDK files are unchanged), and not proof of its
cause. No silent switch to PV is proposed. Old MR has2/6 failures, both at96k
nonidentity, plus raw timing errors. Its unscaled historical windows and old
implementation are explicit confounders; no present-day product regression is
inferred from that historical path.

## More computation does not imply better quality

For both iterative variants all20 NONIDENTITY cells reduce the algorithm's own
magnitude-residual objective versus iteration0. Median reduction is40.425899%
for8 and56.167014% for32. Identity cells are separately retained: their tiny
roundoff-level residuals are not evidence of useful optimization progress.

Independent stationary unexplained-energy improvement occurs in8/12 cells for8
and6/12 for32. Both worsen all4 close-tone cases versus iteration0;32 also
worsens harmonic downshift at both rates. For example,48k61Hz upshift amplitude
error improves from-1.96845dB at0 to-0.000327dB at8, but this does not compensate
for transient regressions elsewhere.

The predeclared burst0 width failures for32 iterations:

|Rate/pitch|Iteration0 width(ms)|Iteration32 width(ms)|Width ratio|Own residual0 ->32|
|---|---:|---:|---:|---:|
|48k/-12st|6.979167|38.000000|5.4448|0.778990 ->0.563896|
|96k/-12st|6.958333|31.927083|4.5883|0.779208 ->0.562404|

Both exceed the predeclared1.20 ratio. Position can improve while width gets
worse; average-error cancellation must not erase the failure. The0/8 seeds
already have about45.3/42.5ms worst centroid error, whereas current product PV
controls are below0.009ms on these two-event fixtures. Therefore even8, which
has no paired-stop cell, is not a suitable product promotion on this evidence.
No threshold or renderer parameter was tuned after these results.

Inference for the next experiment: a long-window fixed target magnitude and
unanchored phase seed are insufficient for reliable transient localization;
merely repeating magnitude consistency is not a solution. This is a hypothesis
for a separate variable-window/phase-localization experiment, not a demonstrated
causal decomposition. SELEBI's nonstationary, percussion-localized magnitude
construction is related context, but was not implemented or validated here.

## Offline performance (not callback capacity)

Each number below is the median across30 settings of each setting's median of3
whole-file process wall times. Files are0.75sec. Process creation, WAV I/O and
OS scheduling are included; this is not isolated kernel CPU, hardware-cold cache,
continuous callback completion, or the real-time80% capacity gate.

|Path|Median wall seconds|Max setting median seconds|Maximum process RSS(KiB)|
|---|---:|---:|---:|
|Offline0|0.165792|0.365296|27828|
|Offline8|0.490622|1.217996|27888|
|Offline32|1.342863|3.774849|27812|

Nonidentity paired setting cost ratios to0 have medians2.40155x for8 and6.48916x
for32. Estimated owned work peaks at34,112,660bytes on this short grid, separately
from RSS. These observations do not establish memory use on long files or other
hosts. All630 raw wall/user/system/RSS measurements are retained, not just the
best times. No new SDK real-time capacity claim is made.

## Tests, errors and provenance

- GCC14.2 C++20/23 and Clang17 C++20/23 each5/5 CTests.
- Clang ASan+UBSan/leak checking5/5. Single-thread-only CLI; no TSan claim.
- Unchanged freshly built spectral-ON SDK26/26, exact historical research6/6.
- Python41/41 before acoustic execution (8 new+33 reused);4 post-run stopping-rule
  tests bring final scoped total45/45, skip0. Do not label the later4 as pre-run.
- Zero output, wrong50cent pitch,10ms offset, added tone, duplicate/incomplete
  grid and real CLI unsupported/silent/nonfinite/overwrite cases are calibrated.
- The5-test CTest inventories are checked with existing run_ctest.py against
  enabled unique tests and JUnit actual status, not success from a zero-test run.

No acoustic process failed or timed out. An unsupported container streaming
request failed before launching work; the actual complete run used a logged
child process. It is not counted as an acoustic trial. A missing standard header
was corrected before the frozen build/plan; all measured binaries retain their
original identity. There was no post-measurement DSP correction or retuning.
The post-run assessor was added to apply already fixed thresholds and has its
own source hash. An intermediate assessor differed only by local placement of
the stop-list calculation; both assessments have identical substantive values,
and both scripts/reports are retained rather than relabelled.

Measured local renderer SHA256:
`0061f032dc3995965750344d0e32aace4afeb3b23cd60bcbef39357c51a89bb7`.
Measurement script SHA256:
`22561e1b1ac87250e95b2b37ab9e6f86f8cb56fa5dbc47973f861ae87dc4980c`.
Raw summary SHA256:
`4c80333b4acf3c21742a64cc3723443bee21655d68e33b2f2a5d6b1c47b7bfde`.
Final assessor SHA256:
`d93d58248b308d2e55438f4cb8870326626449859ac20802046565a7a68df1c3`.

Local Python3.13.5,NumPy2.3.5,SciPy1.17.0,SoundFile0.13.1. Source snapshot is
reconstructed from verified archive; its local Git snapshot commit is not the
remote main commit. CI creates its own plan/binary/environment/timing hashes;
those must not be relabelled as the local run. Final HEAD/CI/merge and downloaded
artifact checks are recorded in the PR's final review and latest Issue comments.

## Remaining work and references

First prioritize the measured WSOLA low-tone frequency failure with a separately
preregistered regression/fix unit; recheck algorithms without automatic fallback.
For PV, confirm transient spreading on independently fixed fixtures and actual
natural material before selecting a variable-window/phase-localization design.
The5 synthetic families do not replace natural-audio validation. Formant Off
results are not Harmonic/Monophonic results; mono is not linked stereo. Dynamic
control,48/96k small-block realtime capacity,physical hosts and distribution remain
separate. The offline job API needs explicit execution class, duration/work budget,
cancellation/error receipts and progress; no public ABI is assigned by this study.

Primary context (not a claim of reproducing all methods):
- Griffin and Lim, Signal estimation from modified short-time Fourier transform,
  IEEE TASSP32(2),1984, DOI10.1109/TASSP.1984.1164317.
- Driedger and Mueller, A Review of Time-Scale Modification of Music Signals,
  Applied Sciences6(2)57,2016: https://www.mdpi.com/2076-3417/6/2/57
- Akaishi, Holighaus and Yatabe, SELEBI, arXiv2602.16421v1:
  https://arxiv.org/abs/2602.16421

Research branches #11/#13/#14 and their negative results remain history, not a
mandatory merge chain. Neither parent roadmap nor broad research issues are
completed by this bounded screen.
