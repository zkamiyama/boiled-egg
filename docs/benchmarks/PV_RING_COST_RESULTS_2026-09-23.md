# Exact PV ring addressing: results — 2026-09-23 JST

Issue69, parent67/15. Base main b972e0355ae656a74fb3fb1b1a99429f1668a5e4,
tree d0259667dd826a7255a858cdfb508af5d4504680. PR68's explicit low-register
Monophonic detail and PR64's WSOLA corrections are already integrated and retained.

## Change and decision

Replace18 unsigned modulo ring addresses with `position & (capacity-1)`:15 in
pv_rt.cpp and3 in pv_execution.inc. The four capacities already come from
next_capacity and are positive powers of two. A private constexpr helper asserts
that precondition in debug builds. Negative resampler positions and samples outside
the live ring interval are rejected BEFORE conversion/indexing, as before.

No new state field, audio buffer, allocation or table. No change to float equations,
FFT/window/hop, tap count/order, feature choice, sample publication, coroutine yield
points or work budgets. Existing ABI/state/IDs/defaults/latency/tail and explicit
formant restrictions remain. This is a same-output cost optimization, not improved
naturalness, new pitch/time capability, or a new formant preset. The measured64
settings all became faster in this environment. **96k deadline qualification is
still unmet; whole-run deadline reliability did not improve.**

## Provenance and fixed execution

Remote protocol9f1f212065a1ca4ba359b5fc43b235f248ff5a54 precedes the full comparison.
Plan SHA256 c89fbe56c917e7f5d84dfbb444f6df5b35ec7b6dff42f2058c38d4f81494ed4e
was registered in Issue69 comment5795256008 before execution. It binds source,
inputs, renderer, old/new libraries, linked dependencies and CPU0 affinity. Old and
new SDKs were built afresh; prior CI source artifact10725394417 was used to restore
and verify384source hashes/tree, not reused as this run's binaries or output.
The failed direct clone (DNS) is retained as an environment failure.

The existing quality/formant_detail renderer, driver, fixtures and acoustic metrics
are unchanged. Both libraries run through that SAME executable with checked loader
resolution. Source was snapshotted at measurement; later additions to source audit,
CI and this report do not relabel old binaries. Their exact implementation/renderer
hashes are preserved. CI prepares its own full-tree plan and outputs.

Quality regression:4 known synthetic families x48/96k x+/-12st xdetail0/1 x3 x2
libraries =192 renders. All192 complete;96 paired PCM/acoustic/metadata records
match exactly and all repetitions match. This is known regression, not a new
holdout, MOS or vendor comparison. The first synchronous attempt was interrupted
by the execution timeout at92records; it is retained separately and not added to
the successful count. The same plan was then run fully in a new directory.

Cost:two-second vowel120, stereo R=-.5L;48/96k xmono/stereo x32/64 x+/-12st xstream/
fixed-I/O xdetail0/1 =64settings, each old/new x3 =384renders. No parallel compilation
or test was running during cost measurement. Order alternates between libraries
by repetition. All384 complete,192 paired PCM/length/latency/tail/energy/proportion
records match, and repetitions match. Full576 saved audio/receipt records are
retained, with every service duration and EOF/setup timing. No clipping/gain/lag
fitting, output substitution or success-subset selection is used.

## Cost and deadline observations

Per setting, compute each run's service time/input-block count, then the median of
three repeats. Ratios below are candidate/base. The input work, client, waveform,
publication and output length are the same; nonempty pull counts are not a work
normalizer. Whole path adds EOF time; construction is separate.

|Path|Settings|Median ratio|Maximum ratio|Faster|
|---|---:|---:|---:|---:|
|Streaming|32|0.89639435|0.94022925|32/32|
|Fixed I/O|32|0.90118508|0.97042364|32/32|
|All|64|0.90118508|0.97042364|64/64|

Whole-path median ratio0.90114756, maximum0.97042364. The fixed objectives
median<=1.0 and every setting<=1.25 pass. This single environment is not proof of
these percentages on every CPU. Median setup is approximately42ms on both sides;
minor setup-time differences are not advertised as a separate speed improvement.
Additional per-instance sample storage and audio processing allocations: zero.
The existing new/new[] controls pass; that instrumentation is not a universal
proof about every allocator or every host.

Deadline diagnostics use each call's ACTUAL frame count, including the final short
block, not just the nominal32/64 period. For each state take the best of three
maximum normalized durations, then evaluate against80% of the period. Separately
retain all real runs and every actual period exceedance:

|Fixed I/O|Best-maximum80% pass, before/after|Period exceedances, before/after|Runs with every call within period, before/after|
|---|---|---|---|
|48k,16settings x3|15/16 ->16/16|18 ->20|36/48 ->35/48|
|96k,16settings x3|4/16 ->5/16|155 ->125|10/48 ->8/48|

At96k the worst state's best maximum/period is3.718608 ->3.124224, still far beyond
80%. At48k it is1.266168 ->0.750756. Lower mean costs do NOT mean fewer failed runs:
both rates have fewer complete-period runs in this sample, and48k has more missed
calls. This is unpaced shared-VM timing, not physical DAC scheduling. We neither
attribute all spikes to interrupts nor call the best-of-three collection a single
successful continuous run. Streaming burst durations remain in the raw/stratified
report but do not establish callback capability. No hard-realtime claim.

## Correctness and local verification

Five integer controls test exhaustive small wraps, one million fixed-seed positions,
uint64 edges, four actual construction-capacity formulas for all legal FFT/block
sizes, and simulated ring storage through unsigned wrap. Invalid capacities are
not exposed as a new supported API. The helper is used only where its invariant
holds; signed negative modulo has not been replaced elsewhere.

- GCC14/Clang17 C++20/23:13/13 CTests each (ring5 + existing public detail8).
- Clang ASan/UBSan/leak controls:13/13. The earlier interrupted sanitizer build is
  retained, not counted; a separate completed build supplies this result.
- TSan:1/1 existing independent-instance test with this PV code.
- Fresh SDK ON26/26 and OFF13/13; relocated C11/C++ shared consumers5/5 each.
- Comparator8/8 and strict audit20/20 Python methods, no skips.
- One unchanged executable per old/new comparison: C288 cells, C++12 cells and
  preview156 cells match. Both shared export sets match. These local comparisons
  are against b972; the older original/OFF/ON audit remains a separate CI check.

Inventory/JUnit counts and absence of skips are checked. The existing tests include
public/direct PCM, events, reset, partition, invalid options/nonfinite inputs,
static stereo and automation/ramp/time controls. No existing product/source/old
client audit is removed. A new named scope first validates EVERY predecessor
(C1/package/duration/formant) on pinned references, then permits only the exact
2file address replacement and1 private helper hash. Unrelated headers/DSP edits,
missing/extra files and modified references are rejected by new negative controls.

## Reproduction and identities

Old library SHA256 a60c258b92b3816c164bc5baac86fe135ba72115b7565ad663be6dccf94bdd2d
New library SHA256 b3fcf4108455a0ca13b58a3918594df90ba6486e8c937d5dfa7e6cd7d4ca3b30
Shared client SHA256 11c51987f05d0926d501bfa35d2f70f9431507a9d79eed1e1b2301d3660a96ff
Quality summary SHA256 cc7060771a1026dd73fc8c703ed14e2c418c4cab6ea945b25c4ad5d55fc6752e
Cost summary SHA256 fe1b61775915b334541429ce4ae1100c04b7c5b59a66ab3f9d3a8a0370ea933c

Build outside source. Supply an exact b972 predecessor library and newly built
quality/pv_ring/detail/formant_render plus its candidate library:

```sh
python quality/pv_ring/compare.py prepare --runner /build/ring/detail/formant_render --before /build/old/libboiled_egg.so --after /build/ring/detail/sdk/libboiled_egg.so --out /evidence/plan
# Register the printed plan hash before executing the comparisons.
python quality/pv_ring/compare.py run --plan /evidence/plan/plan.json --sha256 REGISTERED_HASH --mode quality --out /evidence/quality
python quality/pv_ring/compare.py run --plan /evidence/plan/plan.json --sha256 REGISTERED_HASH --mode cost --out /evidence/cost
```

CI enforces the deterministic output/control gates; noisy shared-runner cost ratios
are not a CI quality claim. Exact final HEAD, CI artifacts/review and any merge are
recorded in Issue69/PR. Current production changes are two files plus one helper;
existing380 of384files remain unchanged, with10 additions overall (394sources).
Broader Issue67 deadlines, voice quality, PV extreme ranges and #41 remain open.
No vendor binary run, Google Drive write, GUI option or heavy research resumption.
