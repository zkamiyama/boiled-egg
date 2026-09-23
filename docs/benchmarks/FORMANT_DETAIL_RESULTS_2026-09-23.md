# Public low-register formant detail: results — 2026-09-23 JST

Issue67; parent60/58/15. Base main086a26daec314534a4246203636bafa84d0c1373,
tree b24f4f7f7bf2418906e3b3624427339bd463a5ee. PR64's length/progress fixes and
WSOLA cost reduction are retained. The older alternative PR66 is not applied.

## Prior selection versus new execution

Issue67's protocol9f599ca7 and its earlier comments describe four construction
profiles tested before this continuation. Both policies selected order80 alone;
narrowing the F0 range did not change the tested PCM. Harmonic had two new >1%
unexplained-energy failures on confirmation and was rejected. Monophonic passed
the limited quality and private-bridge cost gates. The earlier384quality/192cost
raw artifacts and executables were not available in this environment. These are
historical Issue records, not measurements newly repeated or byte-verified here.

This continuation implements only the already-selected Monophonic detail option
through the public SDK. It does not tune order, F0 range, gain limit, windows or
quality thresholds to the known confirmation results. check83/check173 are now
known regression data, **not a new unseen holdout**. The original publication on
cepstral windowing motivates the method, not the numeric order80 or naturalness:
https://www.dsprelated.com/freebooks/sasp/Cepstral_Windowing.html .

## Implementation

Public backend-config flag bit3 is `BOILEDEGG_BACKEND_FORMANT_LOW_DETAIL`.
Validation permits only PV General/Monophonic,48/96k,time1,static pitch and explicit
I/O; continuous flags and all other policy/quality/rate combinations are rejected.
The backend sets the existing cepstral order to80 before rate scaling. F0 remains
60–900Hz; this is not a user F0-range feature, Auto classifier, seven-range preset
or reproduction of a zplane setting. No extra FFT, window, buffer, iteration or
new signal estimator. Existing formant events/state behavior remains supported.

Production changes are exactly three files: backend.h, backend.cpp and
spectral_backend.cpp. There are no public struct/function/parameter/plugin-ID,
WSOLA/default, timing, latency/tail, GUI or transport changes. Old flags follow
the old path. The construction getter includes the new bit; parameter-only state
does not serialize it, so clients must persist construction configuration too.
New source checks retain the complete C1/package/duration audit chain with pinned
references and permit only the exact three reviewed runtime hashes. Existing
old-client/export/CSV comparisons are not removed or replaced by source hashes.

## Preregistered public execution

Before quality/cost execution, Issue67 comment5786250971 registered plan
`a405d8e9f4db3d768a062025ec33342b0721d0fefa8ed2a0dee922548ade4419`.
It binds source, input, current/old SDK, the common public executable, linked
dependencies, settings and environment. Dynamic-loader resolution is checked.

Quality:4known generated families(vowel120/220,check83/173) x48/96k x±12st x
old/new flag x3repetitions=96renders. All are mono,time1,block64,Monophonic General.
Existing joint-sinusoid measurement uses the0.5–1.5s interval,250–3500Hz and absolute
amplitude targets, without gain/lag fitting. Peak/RMS and unexplained energy stay
separate. Sixteen old-main renders use the same current executable and explicit
old SDK loading; all16 match unflagged current PCM. All96 completed and repeated
PCM matches. The original32raw inputs include stereo counterparts for the cost run.

Public cost:48/96k xmono/stereo x32/64blocks xstream/fixed-I/O x±12st xold/newflag
x3repetitions=192renders. Same2second input, pinned CPU and alternating flag order.
The actual public fixed-I/O callback is measured, not the earlier private bridge.
One service group is one input block plus its needed drain; creation and EOF are
separate. Full raw service arrays/maxima/period overruns and output are retained.
All192 completed;32settings have identical per-flag repeated PCM. Linked stereo
R=-.5L has measured maximum proportional error0.

## Quality and scope of acceptance

The known check-set8conditions all improve. Mean absolute envelope dB-RMSE is
11.700763422737737 ->6.992213914396059 (about40.24% less in this metric).
There are no new >1% unexplained-energy failures where old passed and no new
peak>1. However unexplained energy increases in6/8 checks and stays below1%; the
metric improvement is not a claim that every distortion quantity decreases.

|Known check|rate|shift|old RMSE dB|new RMSE dB|
|---|---:|---:|---:|---:|
|83Hz|48000|-12|12.92309|8.09796|
|83Hz|48000|+12|12.13804|8.55596|
|83Hz|96000|-12|12.65943|7.96009|
|83Hz|96000|+12|11.85886|8.42101|
|173Hz|48000|-12|10.66878|5.16622|
|173Hz|48000|+12|11.33809|6.29349|
|173Hz|96000|-12|10.69452|5.18390|
|173Hz|96000|+12|11.32531|6.25908|

The prior Harmonic rejection remains; this flag is not allowed for Harmonic.
Neither vendor binaries nor new natural-voice/MOS data were executed. No claim of
élastique/Soloist parity, high-register suitability, extreme PV range extension,
continuous-pitch quality or general perceptual superiority is made.

## Cost, including overruns

Per-setting medians of3 service-time/input-block averages, candidate/old:
-32settings overall: median1.0006299909685654,maximum1.11731865323792.
-16stream settings: median1.0124485178755398,maximum1.0711139678139738.
-16fixed-I/O settings: median0.9984004717077,maximum1.11731865323792.
All settings<=1.25 and aggregate median<=1.10 meet the preregistered cost gate.
This is near-flat typical cost, **not universal speed improvement**.

Recorded period exceedances across48runs per flag per I/O group:
stream6756->6764;fixed-I/O150->195. Streaming service bursts are not physical
callbacks. Fixed-I/O calls are public callbacks but unpaced shared-VM measurements,
not hardware playback. The increase in exceedance count is retained; no hard-RT,
zero-dropout, all-callback deadline or new80% capacity qualification is claimed.
Creation/EOF and individual maxima are separate in the full receipts.

## Tests actually executed locally

Public/direct same-PV-configuration comparisons cover12cases each for streaming,
fixed-I/O and formant events; reset and32/257partition outputs agree exactly.
Declared latency/tail agrees with legacy configuration. These validate wiring,
not independent acoustic ground truth. Processing new/new[] interception observes0
allocations, including reset/flush; it is not a universal allocator/hard-RT proof.

GCC/Clang C++20/23 each8CTest;ASan/UBSan/leaks8;TSan independent-instance1;
C11 creation/readback; SDK ON26/OFF13; relocatedC11/C++ ON/OFF5each; new Python7;
strict scope/legacy audit16. Inventory/JUnit and skips are checked. Legacy export,
old C/C++ and preview comparisons are additionally run in the final PR workflow.
The final CI status and any retrieved artifacts are recorded in the PR/Issue,
not assumed from this workflow definition.

Initial3 test failures came from using the base SDK default maxblock4096 in a
PV control. Test configuration was corrected to64, without weakening the SDK's
1024 limit. The original test source/JUnit is retained. Two quality runs were
interrupted by tool-call time limits and remain separate partial logs; the final
full96 used a new directory and unchanged plan/code/binary. No partial run is
counted as a completed96. An unused intermediate plan is marked unexecuted.

## Reproduction and identities

Measured newSDK SHA256:a60c258b92b3816c164bc5baac86fe135ba72115b7565ad663be6dccf94bdd2d.
Measured oldSDK SHA256:e68dd3440a3e15f4d59f80db3ae04b0f9cb0cc7f3df94b7e46ad4a74fc22b2fe.
Common renderer SHA256:dbd7683aca4f28a85ff092fd73368fce88b24f3539be52e8573ed3b010010362.
Build a baseline outside the source from main086 and the candidate with:

```sh
cmake -S quality/formant_detail -B /tmp/detail -DCMAKE_BUILD_TYPE=Release
cmake --build /tmp/detail -j2
python quality/audition/run_ctest.py --build /tmp/detail --expected 8
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python quality/formant_detail/verify.py prepare \
 --runner /tmp/detail/formant_render --before /tmp/old/libboiled_egg.so \
 --after /tmp/detail/sdk/libboiled_egg.so --out /tmp/new-plan
# Register the printed NEW plan hash; the preceding run's hash is not portable.
python quality/formant_detail/verify.py run --plan /tmp/new-plan/plan.json \
 --sha256 NEW_HASH --mode quality --out /tmp/new-quality
# Similarly mode old, and mode cost; use separate new output directories.
```

The source snapshot's local Git root is not upstream history. Small remote commits
are independently checked against local trees. Final known-data regression is a
limited preview acceptance, not all of Issue67, broad input-range presets, new
quality mode, new plugin state or the remaining extreme-pitch roadmap. No Drive
write and no vendor execution in this continuation.
