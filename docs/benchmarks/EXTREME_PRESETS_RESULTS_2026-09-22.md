# E3 extreme/preset baseline results — 2026-09-22 JST

Issue60/58/17/15; duration defect separated into Issue62. Base main
6f3ed4508a1c0123539f2e32b8fd37dd8ebdb168. This completes the first comparison unit
of the approved plan, NOT DSP range expansion or an objective victory claim.
Existing345 files, product ABI/state/IDs/latency/defaults/DSP/GUI/transport and the
old primary comparison/Most-only study are unchanged. No heavy iterative DSP.

## Preregistration, split and actual execution

Protocol201a460f27f1194251042d25955f3faa61d1332a precedes new audio measurements.
Plan a757cfe29ab69cd85726726f618654e8cb1aa48d8076d4fd7bb34306a03af706 was registered
in Issue60 comment5769373002 before the development stage. It identifies14 input
WAVs, all measured source, SDK/vendor binaries and linked SDK dependencies.
Fresh unchanged SDK ELF SHA256218abecb11273524ad41e42c97d93a7b88889c2a536ab6c74dee1a65ffb63cb8.

The real supplied REAPER7.80/linux-x86_64 re-enumerated all seven Pro Preserve
presets of elastique3.3.3. Original archives matched their previous hashes.
Preflight11 positive renders cover7 preservation names and Pro Normal at pitch
+/-24 and time.25/4;1 false submode was rejected without audio. An initial inventory
probe concatenated a nil mode name and errored; its script/log were retained and
the probe fixed before calibration. License/evaluation data were not deleted.
The archived Windows3.4.5 demo was not run. Private modules were not called directly.

Development uses120/220Hz harmonic families from the old study. Confirmation uses
97/311Hz, a different envelope/phase as declared in the protocol. These are small
synthetic source groups, not natural speech, different people or independent MOS.
Metrology calibration uses analytical signals, not confirmation engine outputs.

|Stage|Requests|Completed audio|SDK unavailable|Execution failures|
|---|---:|---:|---:|---:|
|Development presets|432|384|48|0|
|Confirmation presets|432|384|48|0|
|Boundaries|792|585|180|27|
|Total|1656|1353|276|27|

All552 unique requested cells have identical status/PCM across3 repetitions.
Repetitions are not independent quality observations. Boundary integrity_pass is
false because27 accepted SDK requests fail. Unsupported rows remain in the full
denominator. all_requested_rendered is false in every stage; never call this
1656 successful renders. No unavailable condition receives a quality score.

PRESETS covers time1 and shifts-24/-12/+12/+24 at48/96k, all7Pro presets and two
SDK PV General policies. BOUNDARIES covers the protocol's11 operations,3families,
2rates and Pro Normal/SDK WSOLA/PV General/PV Transient, not all7presets at every
TSM ratio. There is no8x, stereo, dynamic-control, formant-shift or freeze result.

## Frozen setting selection and confirmation

Selection SHA256962a8a1808c8c573af948491fed3c821ab53d0a4831cd5b78988315808d7b0dd
was registered in comment5769403404 BEFORE confirmation audio was rendered.
For each pitch, the protocol minimizes mean preserved-envelope dB-RMSE over the
2development sources/2rates, using repeat0. It selects one vendor preset and one
available SDK policy, not one setting per confirmation clip. Selection is a
metrology exercise, not a shipped automatic classifier or recommended Hz mapping.

|Shift|Frozen Pro preset|Frozen SDK policy|Confirmation Pro mean RMSE|SDK mean RMSE|SDK smaller/paired cells|
|---|---|---|---:|---:|---|
|-24|Lowest|unavailable|15.162612|not measured|not comparable|
|-12|Low|Monophonic|17.914743|7.050207|2/4|
|+12|Lowest|Monophonic|10.936327|9.209482|2/4|
|+24|Higher|unavailable|12.852076|not measured|not comparable|

Each mean covers only2confirmation families x2rates. Across the eight common
+/-12 cases, SDK has a smaller declared envelope error in4/8. Large vendor errors
on some clips strongly affect means. These values must NOT be presented as general
SDK superiority, quality probability, MOS or clinical confidence intervals.

For comparison, Pro Most's confirmation means are7.376243/8.915341/12.634724/
16.483818dB for-24/-12/+12/+24. The development-selected preset is worse than Most
on both downward shifts in the aggregate, and better on the upward shifts. Do not
reselect after seeing this. Full7preset curves and posthoc per-cell minima are
saved separately; those minima are diagnostic and were not used for frozen choices.

48k examples show why a single score cannot decide quality:
- confirm97/-12: selected Pro Low envelope3.84410dB versus SDK Monophonic7.30250dB,
  but unexplained energy0.26373 versus0.000274. Smaller envelope error does not erase
  the different residual behavior.
- confirm311/-12: selected Pro Low22.90979dB versus Most8.06357dB and posthoc High
  5.38603dB. SDK is6.43102dB. The fixed selection does not generalize uniformly.
- confirm311/+24 has only TWO harmonics in the fixed250-3500Hz score band. This
  sparse diagnostic is not a complete recovered formant envelope.

Metrics use joint sine/cosine projection at actual fractional frequencies, rather
than rounding to FFT bins. Frequencies above.45*rate are explicitly excluded.
No fitted gain or lag alters PCM. The prescribed continuous envelope is a synthetic
engineering target; it does not establish the vendor's intended vocal model.

## Boundary observations and the accepted-but-failed distinction

|Engine|Pure-tone passes/22requested|Pure outputs completed|Unavailable pure cells|Failed pure cells|
|---|---:|---:|---:|---:|
|Pro Normal|22/22|22|0|0|
|SDK WSOLA General|2/22|19|0|3|
|SDK PV General Off|12/22|12|10|0|
|SDK PV Transient Off|12/22|12|10|0|

The2WSOLA passes are identity at2rates. Each PV passes all12 AVAILABLE pure cells,
but has no output in10cells; it cannot be called22/22. This is one61Hz synthetic
tone, not broad instrument coverage. Current PV limits remain time.5-2/pitch+/-12
and time*pitch_ratio<=2, including rejection of time2/+12. No product limit changed.

48k isolated-burst examples (first event):
|Operation|Engine|Centroid error ms|5-95%width ms|Event-energy error dB|
|---|---|---:|---:|---:|
|time4,pitch0|Pro Normal|-5.6093|25.1667|+2.9508|
|time4,pitch0|SDK WSOLA|-41.8486|32.3125|+4.7320|
|time1,pitch+24|Pro Normal|-0.5568|0.9375|+1.8921|
|time1,pitch+24|SDK WSOLA|-10.4622|8.0833|+4.5328|
|time.25,pitch0|Pro Normal|-1.3507|4.2708|-23.6499|
|time1.5,pitch-5|Pro Normal|-0.2289|4.8125|+0.1527|
|time1.5,pitch-5|SDK PV General|+0.0036|6.0000|-0.1131|

Pro's small width at strong compression is accompanied by major attenuation.
This is not credited as a clean transient win. Centroid is not onset. The oracle
moves centers by time ratio, locally resamples carrier/width by pitch, and retains
peak amplitude. It is a predeclared property for these Gaussian bursts, not the
unique ideal for all audio. Same highpass is applied to output and oracle. Mixed
highpass/lowpass measurements are diagnostics, not perfect source separation.

## New correctness defect: Issue62

At48k and2seconds, SDK WSOLA accepts time.25/pitch1, time1/pitch.25 and
time.5/pitch.5, but its CLI exits1 with `exact duration mismatch; output not
published`. Three families x3repeats give27 failures; do not relabel them unsupported.

A separate public-C-ABI diagnostic (unchanged binary, no trimming or zero-fill)
measured counts BEFORE and AFTER flush:
|time|pitch ratio|target frames|before flush|after flush|excess|
|---|---|---:|---:|---:|---:|
|.25|1|24000|24044|24044|44|
|1|.25|96000|96176|96176|176|
|.5|.5|48000|48088|48088|88|

Excess samples were already delivered before EOF. At input1152, delivered counts
492/1968/984 exceed the then-accepted time budgets288/1152/576. The same2second
96k tests end at the correct length but also temporarily exceed accepted budgets.
The resampler limits produced_total only after flushing is true; preventing premature
release is the next bounded repair candidate. The CLI's refusal correctly exposes
the problem. No fix was silently applied to this baseline, and Issue41 pitch
accuracy remains a different unresolved defect. Six direct-ABI raw outputs/counts
are retained as post-screen diagnostic evidence, not extra benchmark wins.

## Tests, provenance and acceptance

Local45 unique Python tests pass,skip0 (13new+32existing). Fresh unchanged spectral
SDK26CTest passes with inventory/JUnit validation. A timed-out earlier CTest log is
retained but not counted. The initial calibration's arbitrary3-harmonic minimum
rejected confirm311/+24; before measuring any engine outputs, the gate was changed
to require a nonempty measurement band and the actual count is reported. Frequency
band, target formula and score were not tuned to audio results. Old test log/source
remain available. Other negative controls cover missing/duplicate grids, all-zero
output, fractional harmonics, gain faults, false unsupported, unavailable selection,
invalid preset, existing project and confirmation-as-development misuse.

Every stored completed WAV/receipt/project and every unavailable/failed record is
read back. Metrology is recomputed once per completed cell;3-repeat PCM identity
covers duplicate observations. Boundary failures remain failures in that readback.
Final exactHEAD CI, artifact/source checks and review/merge identities are recorded
in PR61 and latest Issue60 comments. CI contains no vendor executable or vendor run.

Measured3new Python files match their remote Git blobs exactly. Original345 source
files remain unchanged. Documentation/workflow added after local plan preparation
are not retroactively claimed as measured source. Final CI has its own full source
snapshot. Source, input, SDK/vendor versions, settings and measurement results stay
separate; host action time is not comparable to SDK CLI startup or callback cost.
No physical device, DAW automation, natural voice, MOS or hard-RT claim is made.

## Reproduction and next bounded work

Build the unchanged SDK as in quality/vendor_reaper/README.md. Use a persistent
REAPER configuration under valid evaluation/license terms, not a normal user project.
Store build/evidence outside source. Commands use new output directories:

```sh
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
python quality/vendor_reaper/extreme_study.py prepare --reaper /path/REAPER/reaper --sdk /path/build/boiled_egg_backend_cli --out /path/plan
# Register the printed plan SHA before running.
python quality/vendor_reaper/extreme_study.py run --plan /path/plan/plan.json --sha PLAN_SHA --profile /path/persistent/reaper.ini --out /path/development --stage development
python quality/vendor_reaper/extreme_study.py select --summary /path/development/summary.json --out /path/selection.json
# Register the selection SHA before confirmation.
python quality/vendor_reaper/extreme_study.py run --plan /path/plan/plan.json --sha PLAN_SHA --profile /path/persistent/reaper.ini --out /path/confirmation --stage confirmation --selection /path/selection.json --selection-sha SELECTION_SHA
python quality/vendor_reaper/extreme_study.py run --plan /path/plan/plan.json --sha PLAN_SHA --profile /path/persistent/reaper.ini --out /path/boundary --stage boundary
```

The current boundary command exits2 because of genuine SDK failures; do not rewrite
its status to get a green quality report. First repair Issue62 with compatibility,
no-allocation and cost gates, then measure low-cost input-range/preservation options
and separately expand PV capability. Public input-range presets and PV+/-24/time4
support are NOT delivered by this comparison PR. Heavy multiwindow/iterative DSP
research stays paused. Vendor originals are already privately archived; no duplicate
Drive writes or public redistribution were performed.
