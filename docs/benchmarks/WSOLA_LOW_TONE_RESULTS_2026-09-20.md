# WSOLA low-tone configuration study: results — 2026-09-20 JST

Related #41/#19/#17, parent #15; PR #42. Base main
939270b9b26fa04e481f3f6feaae0e90102599c9, tree294d9bfdaf950bcbf277d8be246b73dcefc2c260.
Protocol08a46d42 precedes the screen. PR40 already integrated the separate
iterative offline PV research tool and recorded its rejection for generic product
promotion. This unit does not repeat that integration or merge old research branches.

## Decision

Retain an explicit finite-file offline research host of the actual unchanged
WSOLA C ABI and this calibrated configuration study. The long-window/wide-search
combination recovers the declared pure-tone criteria in84/84 tested cells, but
worsens transient location/width and reports much larger latency. **Do not make
it the default, label it a generic high-quality mode, or mark Issue41 fixed.**
No input classification, PV fallback, learned quality score or new backend ID.
All292 previous files remain unchanged; added host, study, tests, protocol,
result and workflow are separate. The DSP remains C++20/23 in the existing SDK;
Python is only a synchronous research host and measurement runner, not a new DSP.
No public ABI/state/parameter/plugin ID, latency contract, transport or GUI changes.

## Experiment actually executed

Four manual configs at48k/96k (window/search frames): default1024/128 and1536/192;
wide_only1024/255 and1536/383; long_only4096/128 and8192/192;
long_wide4096/960 and8192/1920. Time1, formantOff, mono, fixed FIFO262144.
The host allows48/96k normalized nonzero PCM16/float32 WAVs<=3seconds,
constant pitch[-12,+12] and explicit offline/research opt-in. Those are capability
bounds, not quality guarantees beyond the measured grid. No freeze/live/ramp,
stereo/formant preservation, asynchronous jobs, cancellation or full-length mix API.

10 generated0.75s families:41/61/83Hz with phase0/pi3,223Hz,
harmonic83, two Gaussian bursts, and burst+223Hz mixture. 2rates x2 host blocks
(32/64) x3 shifts(-12/0/+12) x4 configs =480 cells, each3 fresh handles.
Known61Hz phase0 reproduces Issue41; extensions are fixed synthetic exploratory
conditions, not independent natural-audio confirmation. The input is never
replaced with a generated ideal output by the host.

Original plan fcc0e3e1d3acdd8ddf0a761d0e76b60f28ed354176d0c2e1a6e0ab59ab41bab1
was registered before1440/1440 native runs in Issue41 comment5746348922.
A PCM-vs-container identity correction is explained below. Corrected plan
33787a0a599b0339c72dbe90308f8386743195c9fad2e3d706a3f6a0cc450ff8
was registered before the complete1440/1440 rerun in comment5746366059.
All480 cells have bit-identical stored float PCM in their3 repetitions;
all240 block-independent settings match between32/64. Every old/new paired
PCM and every acoustic metric matches1440/1440. All2880 actual WAVs match
their own retained receipts. No old timing is relabelled as a corrected-host run.

## Acoustic results: scoped properties, not naturalness ranks

Pure-tone pass requires <=5cent dominant-frequency error. Clean-tone pass adds
<=1dB target-amplitude error and <=1% unexplained energy. Identity cases remain
visible (28 per profile);84 includes block repetitions of the same acoustic
conditions, not84 independent source recordings.

|Configuration|Pitch pass /84|Clean-tone pass /84|Max abs cents|Max event position error ms|Max event width ms|
|---|---:|---:|---:|---:|---:|
|default|38|30|1202.672536|12.582954|6.541667|
|wide_only|44|32|3639.819809|15.394435|6.562500|
|long_only|36|36|267.622117|68.286116|22.125000|
|long_wide|84|84|0.264643|63.983776|50.072917|

long_wide's maximum amplitude error is0.00692531dB; maximum unexplained-energy
fraction0.001563696. In nonidentity pure-tone cells the clean counts are
2/56,4/56,8/56,56/56 respectively. Better frequency alone did not ensure a
clean signal in the other profiles. Harmonic and mixed results are retained
separately, never used to expand these pure-tone claims.

For the exact61Hz phase0/64block reproduction:

|Rate/shift|Default cents|Long+wide cents|
|---|---:|---:|
|48k/-12|103.793717|0.264643|
|48k/+12|-1202.672536|-0.128728|
|96k/-12|-43.342447|-0.078332|
|96k/+12|-1200.000852|-0.012369|

The long_wide arm violates the preregistered event stop16 times across8 cells
(counting both host block sizes). All16 include absolute position worsening>1ms;
8 also include width>1.20x default. At48k/-12 the first event moves from9.02ms
error to63.98ms; at96k/+12 the second-event width moves from5.27 to50.07ms.
No lag correction, alignment or gain fitting hides these failures. The original
burst width is3.5ms. A favorable pure-tone result cannot compensate for these
transient regressions. Mixed signals are not artificially decomposed by subtracting
separately processed audio. No natural-audio listening/MOS was performed.

## What the ablation does and does not establish

The default search radius is2.667ms at48k and2ms at96k; a61Hz half-period is
about8.197ms. Source inspection shows similarity search constrained to that
radius. Only the combined long/wide tested arm passed all declared pure-tone
criteria. This supports a window/search limitation for these inputs, not proof
that all WSOLA failures have one cause or that these values are optimal.
The public API limits search<window/2 and the current engine's startup also
requires search<=hop/(time*pitch). The host presets respect both; widening
arbitrarily is NOT a safe fix. This is not a complete factorial design because
the wide search used with the long window is unavailable for the default window.
No default validation or scheduler code was changed. A follow-up can examine
search availability/scheduling and transient anchoring separately, without
silently replacing the algorithm or retuning this confirmation screen.

## Latency, work and memory: not a real-time claim

The actual SDK metadata reports these numbers for either tested host block:

|Config|Rate|Input lookahead frames|Reported realtime latency/tail frames|
|---|---:|---:|---:|
|default|48000|1152 (24ms)|1664 (34.667ms)|
|default|96000|1728 (18ms)|2496 (26ms)|
|long_wide|48000|5056 (105.333ms)|7104 (148ms)|
|long_wide|96000|10112 (105.333ms)|14208 (148ms)|

These are queries of the chosen configuration, not measured realtime playback
or a change to the product default's advertised latency. Offline buffering
removes a callback deadline, not time-position errors inside the rendered file.

Corrected-run per-cell3-render median times, summarized across120 cells/profile:

|Config|Median of cell medians ms|Maximum cell median ms|
|---|---:|---:|
|default|8.8891|18.8886|
|wide_only|9.5506|19.7234|
|long_only|8.9373|19.0021|
|long_wide|13.4812|31.0656|

Paired long_wide/default median ratio1.3768,max3.2870. Timing includes fresh handle
construction, full Python/native push/pull and destruction, excludes WAV I/O and
measurement. It includes Python overhead and is not the kernel's cost or a
callback80%/1.25x gate. First cold handle construction41.177ms is separately
recorded, not combined with warm results. Full measurement-process peakRSS126056KiB
includes Python/numerical libraries/results and is not owned-instance memory.
Three configured mono rings alone hold3MiB of float storage; shared resampler,
other scratch, library/allocator and host arrays are additional. No hard-RT or
no-allocation qualification follows from this experiment.

## Tests and actual failures retained

Final48/48 unique Python tests, skip0:11 new host/calibration methods plus37
existing assessor/import/fixed-predictor/comparison tests. Frequency oracles and
50cent faults,10ms position fault, added non-target energy, zero/NaN, malformed
RIFF/chunks, unsupported modes/rates, hash mismatch, no-overwrite, grid omissions,
and event-stop counterexamples are exercised. Required real binaries missing is
an error, not a skip. The real default backend CLI matches host PCM6/6. Reset,
recreation and32/64/1024 partition controls also pass.

Fresh unchanged spectral-ON SDK: full inventory/JUnit-checked CTest26/26,skip0.
An initial call-limit interruption stopped after21/26 and is retained as incomplete;
a subsequent complete run (parallel4) took16.95s. No runtime change requires a
new full DSP compiler/sanitizer matrix here; no unexecuted GUI/DAW/physical/OS or
installed-package tests are claimed as new passes.

Two evaluation mistakes were corrected, not concealed as audio improvements:
1. Before the screen, requiring input-bit identity at pitch0 failed on existing
   float overlap rounding (max~1.49e-8). The test now bounds error by2float32eps
   times input peak. Reset, repetition and CLI PCM equality remain exact.
2. Original1440-run screen exited2 because WAV full SHA was called PCM identity.
   22/480 cells differed only at byte60, the PEAK chunk timestamp in those WAVs;
   decoded PCM was identical. The corrected scorer keeps original container SHA
   AND canonical stored float32 little-endian PCM SHA. A timestamp-only mutation
   passes PCM identity; a sample mutation fails. This test raises47 to48. Neither
   change adjusts acoustic thresholds, DSP, configuration, inputs or algorithms.

## Identity and reproduction

Unchanged measured library SHA256:
218abecb11273524ad41e42c97d93a7b88889c2a536ab6c74dee1a65ffb63cb8.
Final host SHA256: f89c3ca8db883ffbd64c9aa1d8bfc0d03f9fd153070dbbbf8bb3b1a666b4b29d.
Final study SHA256: 564cab44eea96b35eef9698a325cbfa70ac5b70bd98d8f01d34b57986aa639d2.
Final test SHA256: 5dad7eaeb26fa124d6fa9e9b3f785291f139639b37cbde6fdadb0174a0a3def6.
Corrected summary SHA256: 6f1883cdcbfa4160420538d29657fdf85cbe2d1d8534751ba01ceb193b4f095b.

Build in a directory OUTSIDE the source tree and keep evidence outside it too:

```sh
cmake -S . -B /tmp/be-wsola-build -DCMAKE_BUILD_TYPE=Release -DBOILED_EGG_ENABLE_EXPERIMENTAL_SPECTRAL=ON
cmake --build /tmp/be-wsola-build -j2
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 PYTHONPATH=eval
python eval/wsola_low_tone_study.py prepare --library /tmp/be-wsola-build/libboiled_egg.so --output /tmp/be-wsola-plan
# Register the printed SHA before measurement; do not reuse the local SHA above.
python eval/wsola_low_tone_study.py run --plan /tmp/be-wsola-plan/plan.json --plan-sha256 REGISTERED_SHA --output /tmp/be-wsola-results
```

Individual explicit research render:

```sh
python eval/wsola_offline.py input.wav NEW_OUTPUT_DIRECTORY --execution offline --allow-experimental --profile long_wide --pitch-semitones 12 --block 64 --library /tmp/be-wsola-build/libboiled_egg.so --library-sha256 ACTUAL_LIBRARY_SHA
```

This host loads only an explicitly supplied trusted built library; a hash records
identity, not authenticity or safety of arbitrary executable code. No model/audio
uploads are needed. Exact final CI/review/merge and downloadable artifacts are
recorded in PR42 and latest Issue comments. CI uses its own hashes/timings and
must not be relabelled as the local run. #41/#19/#17/#15 remain unfinished.
