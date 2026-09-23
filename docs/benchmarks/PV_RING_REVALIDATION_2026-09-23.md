# PV ring optimization: integration revalidation — 2026-09-23 JST

Related #69/#67/#15, PR70. This resumes the already-open PR70 instead of
reimplementing PR64/68 or duplicating the ring-address patch. Base main is
b972e0355ae656a74fb3fb1b1a99429f1668a5e4. The measured candidate is
83eb69d110531f76ab75a8eff21ee6680a6a8592, tree
adba328aa5bcfffbc2553b34ebcff9a105b7c5ef. This document is the only subsequent
source addition; no executable source, input, measurement code or threshold was
changed between the two runs below.

## Exact scope reviewed

All four ring capacities come from next_capacity and are positive powers of two
within the validated construction limits. The18 changed addresses are unsigned;
negative/out-of-live-range sample checks are unchanged and precede conversion.
The mask helper is the exact unsigned modulo identity, not a float approximation.
Float equations, FFT/window/hop, resampling taps/order, allocation/state fields,
coroutine yield points, work budgets, ABI/state/IDs/defaults/latency/tail are
unchanged. Runtime changes are two files plus one private header. At the measured
HEAD,380 of384 old files are unchanged,4 are modified and10 are added. Source
contracts still validate the complete immutable predecessor chain and retain
old-client/export/complete-grid comparisons; they are not wildcard exceptions.

## CI evidence actually downloaded and read back

PR workflow35867075086 artifact10752896099:
SHA256 0e44bd43fd5bcc22cf8b59ddf925b2f88364834c6397e1317bb0118120e9edef.
Verified ZIP CRC,394 source hashes and reconstructed Git tree,16 input files,
192 stored outputs and192 receipts,96 exact before/after PCM and acoustic-value
pairs. This is readback of the existing CI execution, not a new quality experiment.
CI's synthetic merge a7f63d3f0b1040b030c5f82fdac424159237deb0 has the same tree.

Compatibility artifact10751924735:
SHA256 e0786d8a89c98aca0555b9f0664a8bc361733b448f8f2ec5d9d6fa7f78b5ba6a.
Verified394 source identities,19 internal evidence hashes, old C288 xOFF/ON,
old C++12 xOFF/ON and156 donor/current preview comparisons from actual CSVs.
The five native artifacts10753190630/10753135680/10753290104/10752716195/10752895881
were downloaded, their published SHA256/CRC checked, and each JUnit confirmed13
unique executed tests and zero skips (GCC/Clang20/23 and ASan/UBSan).

## Fresh local build and two complete cost runs

Restored and verified the exact base and candidate source trees, then rebuilt both
with GCC14.2/Release. New local checks:13/13 CTest, comparator8/8, audit20/20, skip0.
These are separate from earlier work's compiler matrices and full SDK tests.
Python3.13.5/NumPy2.3.5, fixedCPU0. The existing renderer and fixtures are unchanged.

Before measurement, plan9ae7f98554987b37af766018a80554ed7c25d6490f6908a948ad4a1d2f5918a0
was registered in Issue69 comment5796233148. Same two-second input,64 settings
(48/96k xmono/stereo x32/64 x+/-12 xstream/fixed-I/O xdetail0/1), both libraries,
three repetitions:384 renders per run. Old/new order alternates. No parallel build
was running. All callback durations and actual final-short-block periods remain.

|Complete run|Median cost ratio|Maximum ratio|Faster settings|All-setting cost goal|
|---|---:|---:|---:|---|
|First|0.81493354|1.35840852|57/64|FAIL:1 setting above1.25|
|Confirmation|0.81008614|1.14734606|58/64|PASS|

Ratios compare each setting's three-repetition median service time/input-block
count. The first run's failure is48k/stereo/block32/-12/stream/detail0. Its exit2
and all outputs/timing are retained. Before the second run, comment5796308577
recorded the failure and the decision to repeat the WHOLE384 grid once. No failing
subset was selectively retried; no best repetitions were pooled. Input, source,
ELFs, affinity, repeat count and goals(median<=1.0, each<=1.25) are identical.
The successful confirmation does not turn the first failure into a pass, nor does
it prove that every deployment has a1.25x worst-setting bound. No further tuning
or extra selection run was performed.

Streaming median ratios:0.81888585(first),0.83127360(confirmation).
Fixed-I/O median ratios:0.81286008(first),0.79628332(confirmation).
All768 outputs and768 receipts were read back,384 before/after PCM+metadata pairs
match, and the384 corresponding outputs match between complete runs. Both shared
libraries export the same39 symbols. No quality, gain, length or latency tradeoff
was introduced by this optimization in these tests.

Old ELF:a60c258b92b3816c164bc5baac86fe135ba72115b7565ad663be6dccf94bdd2d.
New ELF:b3fcf4108455a0ca13b58a3918594df90ba6486e8c937d5dfa7e6cd7d4ca3b30.
Runner:324e2f2b9b30e6f19054faa75d92f57325f6b4da6f9abafa365355fcd0bb21f7.
These were rebuilt here, not relabelled historical measurements. Their equality
to previously recorded library hashes does not make timing environments identical.

## Deadline limitations remain

For fixed-I/O96k both versions pass0/16 settings under the best-of-three maximum
80%-period rule in BOTH new runs. Period exceedances before/after are2988/2548
(first) and2582/2017(confirmation); all-period complete runs are0/48 per version.
At48k fixed-I/O,80%-period settings improve1/16->6/16 and6/16->9/16 respectively,
but worst spikes remain; the confirmation maximum/period can be8.027181.
These are unpaced shared-VM observations, not physical-device callbacks. Reducing
average work is not a96k deadline, hard-real-time or universal no-dropout guarantee.
We do not label every spike an interrupt. Streaming bursts are not callback tests.

The integration decision can use exact-output correctness, the original fixed
study and this separately disclosed confirmation, but must retain the first
failed cost goal and keep deadline/environment qualification open. Final reviewed
HEAD, workflow results and any merge are recorded in PR70 and Issue69. This
follow-up adds no vendor run, natural-voice/MOS claim, new formant preset, expanded
pitch/time capability, heavy research algorithm or Google Drive write.
