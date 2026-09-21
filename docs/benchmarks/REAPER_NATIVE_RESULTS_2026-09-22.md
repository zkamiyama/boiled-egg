# Actual REAPER-hosted elastique comparison — 2026-09-22 JST

Issue58, parents17/20/15. Base main1d01d9a59d4c2f6a9775dd9bc975195667639b4e,
tree ac208e780d0b3d8f0d83ff9d6d0f427d407e70bf. The complete337 existing files are
unchanged. This is an external-host adapter/evaluation addition, not new product
DSP, a costly research renderer, or a change to ABI/state/IDs/defaults/latency.

## Delivered outcome and limits

The complete REAPER application successfully produced270 actual vendor renders
per full run, compared with450 freshly built SDK CLI renders. This replaces the
previous absence of direct native vendor pitch outputs for this bounded scope.
It does NOT establish elastique parity, natural-voice MOS, commercial superiority,
or general Soloist/formant quality. quality_selection remains null.

REAPER reports7.80/linux-x86_64; its enumerated profiles are elastique3.3.3 Pro
Normal, Pro Preserve Formants (Most Pitches), and Soloist Monophonic. The version,
mode/submode names and IDs are checked through public APIs. The complete host is
run via its normal CLI/Lua/render action. The loaded maps show the actual
elastique3.so module. No proprietary module is called outside its host or copied
into the SDK. This is a REAPER integration result, not a bare zplane SDK benchmark.

The separately supplied ELASTIQUE_DEMO_3.4.5.zip contains a Windows EXE and was not
executed. Its version is not substituted for the actual REAPER3.3.3 result. Both
original archives were stored privately and fetched again with SHA256/size match;
no public sharing was added. Storage does not extend evaluation or redistribution
rights. The dedicated REAPER profile was kept across runs, with no license/trial
reset. Binaries and private Drive IDs are not part of the public repository.

## Preflight, fixed grid and provenance

Protocol40066e5edd24c59d79cee95a3938e3170db3a618 precedes the comparative grid.
The initial plan was registered in Issue58 comment5767608712:
`dbd7024ac8e656dcc58fde146260bb11be8db484f41ac3a059d53326727d66df`.
After a host-completion guard was added, a new plan was registered BEFORE the full
rerun in comment5767729011:
`5eb4f49ea5d6877173acd42d02f2a78c89af241c7bc0876d715755609beea3ba`.
DSP binaries, Lua rendering operations, input PCM, metrics and gates did not change.

Actual preflight:223Hz T1/0,+12,-12st and T2/.5 with pitch preserved,5 successful
FLOAT outputs with correct lengths and pitch within5cent. T1/0 exactly matches
input PCM. An intentionally wrong mode name fails before output. An earlier sink
format probe produced PCM16; it was rejected and the correct FLOAT format was
verified from decoded metadata. This was adapter calibration, not a changed
quality threshold. Initial logs and probe outputs are retained.

The scientific grid is5 declared synthetic families x48/96k x-12/0/+12st x8engines
x3repeats=720renders/240cells. Mono2seconds,time_ratio1. Families are61Hz pure tone,
harmonic-envelope F0=120/220 signals, two3500Hz Gaussian bursts, and61Hz plus the
same bursts. Full formulas/phases/timing are in the protocol. These are not
recorded speakers, independent natural clips or listener observations.

SDK profiles:WSOLA General Off; PV General Off/Harmonic/Monophonic; PV Transient
Off. Actual current CLI, block64 and explicit experimental opt-in. Vendor profiles
are exactly those named above, not auto-selected alternatives. Render gain1,
no FX/fades/dither/normalization/tail, exact source/project rate and bounds. Host
bounds define a finite offline result and can crop tail; do not treat this as
unbounded raw SDK output or infer a latency formula from the output length.

Both full runs completed720/720. All240cells have identical PCM across3repeats.
Initial/final720 PCM and all acoustic metric dictionaries match exactly. Every
saved WAV/receipt and270projects per run was read back; all720 metrics per run
were recomputed and matched. All90 vendor identity outputs per run equal the
original PCM exactly. Repetitions test reproducibility, not independent quality.
No successful-subset scoring, lag fitting, gain fitting, clipping or silent output
acceptance is used.

## Correctness and event observations

The61Hz pure-tone gate requires dominant-frequency error<=5cent, target-component
amplitude error<=1dB, and unexplained energy<=1%, in the middle1second. Frequency
search is unrestricted.6cells=2rates x3shifts;2are identity.

|Profile|Pure-tone three-gate passes/6|
|---|---:|
|REAPER Pro Normal|6|
|REAPER Pro Preserve Formants (Most Pitches)|6|
|REAPER Soloist Monophonic|2|
|SDK WSOLA General Off|2|
|SDK PV General Off|6|
|SDK PV General Harmonic|6|
|SDK PV General Monophonic|6|
|SDK PV Transient Off|6|

Do not infer Soloist vocal quality from a low pure sine. Its failure under this
specific input is retained, not replaced with Pro. At48k/-12, Soloist dominant
frequency is approximately1200.125cent above target; at+12 the frequency error is
1.234cent but the target amplitude is-5.5395dB and unexplained energy.52844. The
three gates detect different problems. No hidden cause is assigned to the vendor.
The WSOLA results reproduce an existing low-tone weakness under this new2second
phase.31 input; they are not relabelled copies of Issue41's older.75second fixture.

For48k,3500Hz Gaussian bursts,+12st, fixed highpass event measurements are:

|Profile|First/second centroid error ms|First/second5-95% width ms|Raw peak|
|---|---|---|---:|
|Pro Normal|+1.185/+1.184|4.458/4.458|.180006|
|Pro Preserve Most Pitches|+4.319/+4.325|24.104/24.063|.024983|
|Soloist Monophonic|+.484/+1.128|3.438/5.583|.179940|
|SDK PV General Off|+.001/+.015|10.938/10.938|.089793|
|SDK PV Transient Off|+.008/-.006|6.417/6.458|.176207|

Pro Normal has the tighter width than the two SDK Off profiles here; the SDK has
smaller absolute centroid offsets. Width alone must not hide energy differences.
A Gaussian high-frequency burst is not a voice-formant test; applying preservation
to it need not be an appropriate production choice. No fallback disables the
requested policy. Centroid is not onset; mixture high/lowpass diagnostics are not
perfect isolated stems. No general event-quality winner is selected.

## Synthetic formant diagnostics, not a vocal MOS ranking

The harmonic input is generated from a continuous envelope E(f) with centers650,
1200,2500Hz. The Off target moves the harmonic frequencies while keeping their
amplitudes. The retained-envelope target evaluates E at the new frequencies.
Both are explicit engineering targets. Measure30 harmonic components at exact
integerHz over one second; report absolute dB-RMSE on the preregistered bins,
without fitted gain. Detuning, spurious components and envelope error can affect
these diagnostics; the unexplained-energy field is retained separately.

Mean absolute-amplitude dB-RMSE against the retained-envelope target over8
nonidentity cells (2F0 x2rates x2shifts):

|Profile|Retained-target RMSE dB|
|---|---:|
|Pro Normal|10.1821|
|Pro Preserve Formants (Most Pitches)|7.3987|
|Soloist Monophonic|14.4231|
|SDK WSOLA General Off|21.1120|
|SDK PV General Off|7.7790|
|SDK PV General Harmonic|5.6557|
|SDK PV General Monophonic|5.5705|
|SDK PV Transient Off|7.8704|

Pro Preserve improves this target against Pro Normal in6/8cells. Each SDK General
preservation policy also improves against SDK General Off in6/8cells. Harmonic
beats the selected Pro Preserve preset in5/8cells, Monophonic in6/8. These limited
results do not establish voice or polyphonic superiority. Only one Pro preserve
preset is tested; its design target need not equal either SDK policy.

Important failure examples remain: at48k,vowel120,+12, Soloist retained-target
RMSE31.3387dB and unexplained harmonic energy.98244; atvowel220,+12 the same profile
has5.8796dB/.001027. The strong source dependence prevents generalizing either
example to real singers. Atvowel220,+12, SDK Harmonic has6.5247dB while SDK Off has
5.2739dB: enabling preservation does not always improve this constructed target.
The source is not a natural voice; no phonation, consonants, breath, vibrato or
rapid F0 transition is represented. New MOS is0, no model was invoked.

## Execution, failure controls and cost boundaries

Local final tests:32unique Python methods (12new+20existing contract tests),skip0.
Independent controls cover analytical preserved/off envelopes, wrong octave,
zero/nonfinite/missing/wrong-length audio,10ms event delay, missing event, PCM16,
unknown mode, overwrites, incomplete/duplicate grid and malformed receipts.
Fresh unchanged spectral-ON SDK:26/26CTest,inventory/JUnit checked,skip0.

Review found that a nonzero REAPER process exit could be ignored if individually
valid outputs remained. The first actual run had exit0 and270/270completion, so
its sound was not invalidated. The final guard requires a successful process and
exact integer batch counts; fault controls reject nonzero/missing/incomplete/
bool/float counts. Old source/plan/output are preserved, and all720were rerun after
the guard instead of relabelling earlier measurements. Old calibration had31tests;
the final count is32. Scientific operations/thresholds were not adjusted to results.

REAPER wall time is a host-render action, while SDK wall time includes a fresh CLI
process and its setup. They are different timing scopes, not engine CPU rankings,
callback80% tests or realtime qualifications. A physical JACK device was absent;
offline renders still completed. Host dependency maps were captured and251loaded
files fingerprinted AFTER the run; this is useful provenance but not a pre-run
lock of every OS/library dependency. Key executables/modules were pre-run hashed.

## Identity and delivery

Final local summary SHA256:
42e4b873de0515f9ce6bd7ced16d0b0f65bb2ad855fb727f110e27ad000cd519
SDK CLI SHA256:
a399900d923349f3fc74b98be068dcbc2d20c8ca1d8beafa9aff3fdbdce16d12
SDK library SHA256:
218abecb11273524ad41e42c97d93a7b88889c2a536ab6c74dee1a65ffb63cb8
REAPER executable SHA256:
d11d5b62ee54697e08e19aa36d29ee0d057605831eef0bae4ede28d3fd317557
Loaded elastique3 module SHA256:
d6356e6bba7034bcb412710bd2d5fd3981f0c4309b865ac5c55be57468df4b0b

Measured source is337unchanged files plus4 adapter/test files. Later protocol,
README, workflow and this results file add documentation/CI, not measured DSP.
Final remote/source/CI/review identities are recorded in the PR and Issue58.
Vendor-free CI runs only32calibration tests per Python version, NOT REAPER or the
720comparison. Actual local vendor outputs are the separate evidence above.

Reuse instructions are in quality/vendor_reaper/README.md. Binaries stay in the
user's private archive with the original terms; project evidence excludes them.
Next bounded work is actual permitted vocal/phrase material and other explicit
preserve presets, plus host conditions/pitch trajectories/stereo as separate
contracts. The Windows3.4.5 demo remains unexecuted. Heavy DSP research is not
silently resumed, and no benchmark result licenses a new default or closes broad
quality Issue17, roadmap15, or the existing WSOLA issue41.
