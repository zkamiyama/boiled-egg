# Roadmap B: calibrated listening connection — 2026-09-15 JST

## Scope and roadmap status

Roadmap #15 and dependent #16/#17/#18/#19/#20 already existed when this resume
started. They were read rather than duplicated. PR #21 / #16 contains the prior
comparison-contract correction; its four workflows at1cd825dd all succeeded.
This resume downloaded artifact10394945294, verified ZIP SHA256 and120 tracked
source hashes, built that source and passed12/12 product CTests.

New PR #22 / branch quality/calibrated-listening-pack is stacked on PR #21. It
implements another part of #17: exact-operation evidence -> complete raw panels
-> anonymous exploratory listening. No product DSP, C ABI, plugin, default,
formant implementation or stable main change. #16 remains pending review/merge;
#17 remains open for its broader criteria. #18/#19/#20 are not marked complete.

Commits:76b0c18d protocol,0108ad30 candidate evidence,64ecd125 panel/presentation,
0383055f fourteen accounting regressions,2db8d07e actual WSOLA/R3 integration,
573b6e7d CI. Validated code checkpoint573b6e7dda5b7d4f3e976214fdd418ddba04ae34.
Subsequent d7d117ea usage guide and this record change documentation only.

## Implemented contract

Reuse comparison_contract.py for input/output semantics and CLI receipts, and
reference_rubberband.py for direct offline R2/R3 generation. Do not confuse the
FFmpeg realtime filter with direct offline processing. All engines/configurations
are explicit. First eligibility/pack implementation is **Formant Off only**;
Harmonic/Monophonic/preserved policies are rejected, not replaced by Off.

Calibration keys include exact candidate config, resolved executable/library
and dependencies, adapter hashes, numerical-library versions, rate/channels and
T/p request. Changes require new evidence. Raw probe logs remain available;
ASLR addresses in ldd output are observation details, not execution identity.
Tests verify that altered dependency identities reject reuse while changed load
addresses alone do not. No cryptographic vendor attestation is claimed.

Every requested natural cell requires its own passing operation evidence, then
valid raw metadata. Failed/missing actual output stops listener-pack publication.
No nearest-ratio matching, fitted delay, trim/pad, extra resampling, output gain
fitting, limiter or automatic fallback. Root directories must be new.

The listener folder has anonymous trial IDs/choices and re-encoded FLOAT WAVs
without engine metadata. Organizer identity/provenance/answer key are separate.
One common attenuation per trial makes sample peaks<=.95; the same gain applies
to all candidates and original orientation audio. Raw results are untouched and
every presentation PCM equals the declared float32 transform. Relative loudness
remains; this is not loudness-matched, true-peak-limited or sample-synchronous AB.
Ratings are initially blank. Export/validation keep only explicit responses.
Zero responses produce no MOS or candidate adoption decision.

## Frozen calibration and results

Installed local environment: NumPy2.3.5, SciPy1.17.0, SoundFile0.13.1;
FFmpeg7:7.1.5-0+deb13u1, Rubber Band package3.3.0+dfsg-2+b3, libsndfile1.2.2-2+b1.
These are measured installed builds, not claims of the latest release.

The WSOLA executable is rebuilt from PR #21 source. Existing PV General and
Transient executables are rebuilt from the prior verified f8e5ef2 source archive
(synthetic mergef57ef970, tree d8eeb9b7,198 hashes). No PV DSP is reimplemented.
Receipts bind actual executable/core-library hashes. Supplied20 reference WAVs
are extracted unchanged; all are mono44.1k. This is historical development data,
not a fresh holdout, and no MOS labels are scored.

Six configurations x44.1/48/96k xmono/stereo x13 declared duration/pitch/combined
operations produce **468 calibration outputs**. Signal:two-second440Hz; fixed
250ms exclusion for strongest spectral peak;5-cent limit. Stereo additionally
requires full-file relative RMS of yR+.5*yL <=1e-5. That strict diagnostic includes
boundaries and is not a perceptual audibility or product-release threshold.

| Configuration | Metadata | Tone gate | Both gates | Mono eligible | Stereo eligible |
|---|---:|---:|---:|---:|---:|
|WSOLA|78/78|78/78|78/78|39/39|39/39|
|PV General|78/78|78/78|59/78|39/39|20/39|
|PV Transient|78/78|78/78|56/78|39/39|17/39|
|Direct offline R3|78/78|78/78|49/78|39/39|10/39|
|Direct offline R2|78/78|34/78|20/78|17/39|3/39|
|FFmpeg wrapper|78/78|19/78|12/78|9/39|3/39|

The complete mixed report remains **passed=false**,274/468 eligible. All raw
failures and measurements remain. No gate was loosened. These are limited
strongest-component/anti-phase checks, not general music or engine-quality ranks.
Peak-frequency maxima in cents:WSOLA .983995; PV General .004574; PV Transient
.002014; R3 .000216; R2 48.664662; FFmpeg91.099828. A strongest spectral component
is not automatically every definition of perceived fundamental frequency.

Stereo residual maxima:PV General3.9777e-4,Transient1.5657e-4,R3 .0214808. The
mechanisms/perceptual significance have not been resolved. This does not silently
cancel the predefined mono study or establish that all stereo outputs are bad.

An earlier calibration was interrupted by a tool-call execution limit after138
receipts, before a complete summary. It is retained separately and not counted
as complete evidence. The final full run used unchanged code/binaries and a new
output directory. No incomplete run was converted into a successful pack.

## Actual-source panel and presentation

The panel/operations were declared before calibration: WSOLA, PV General,
PV Transient, direct R3; T=.8/1.25 at pitch0 and T=1 at -7/+7st; Off.
Their exact44.1k mono operation cells pass. Full source files are processed:
20 sources x4 operations x4 candidates = **320 primary natural renders**.
All320 are finite float32, exact expected frames (max error0), correct rate/ch.
Source/binary/adapter hashes remain stable. No full aligned-waveform quality score
is asserted. The historical corpus and repeated tone grid are not independent
samples merely because many outputs were generated.

Natural maximum raw sample peak1.430693;83/320 outputs exceed1 and remain unmodified.
80 randomized four-choice trials are generated. The minimum common presentation
gain is-3.556459dB; original source peaks mean all80 trials get some attenuation.
No answer key or source/engine names are in the listener metadata. The organizer
files remain separate. Ratings received=0; listening_status=not_listened;
quality_selection=null; alignment_verified=false.

Pack ID:ce6d8c78968723e829eb0b8a5b0578695f9ab0578139cd07be2babacc41595da.
Primary count is **788 output renders** (468 calibration+320 natural), not including
unit-test doubles,12 small real integration renders, presentation copies or the
interrupted run. No subjective winner is inferred.

## Software verification and hosted CI

Local fourteen bookkeeping tests + one real WSOLA/R3 end-to-end test pass.
Inherited twenty comparison unit tests,three dataset tests,one real FFmpeg/main
integration and four direct-reference tests pass: **43 Python tests in this scope**,
no skips. Product CTest12/12 passes. Reused spectral dependency CTest23/23 passes.
No new production DSP is modified, so these are evaluation integration checks,
not a new audio-kernel optimization or real-DAW qualification.

All five PR workflows at573b6e7d succeed:
- calibrated-listening34973617614:Python3.11/3.13,product regression,14 tests and
  actual8-calibration/4-render anonymous-panel integration with raw evidence;
- comparison-contract34973617716;
- existing product ci34973617640;
- research-pv34973617562;
- dataset-tools34973617844.

Downloaded new artifact10397859482 SHA256:
7c9f51e914dce331abb04e5671d866c1c35b6a853449f855d5ed76f8de514b0d.
ZIP CRC and126 tracked source hashes verify. All124 locally present tracked files
match; the two absent local files were the committed workflow/protocol. CI merge
91eece79206bb33b47fd9a1b7ef06666c84b200f has tree
4d5c30a30c504b551da3708222f6001c93075f02. Re-running the14 Python tests directly
from the downloaded source passes. Hosted integration observations are separate
from the320 actual-user-source renders.

Evidence SHA256:
- calibration summary4935a2aab1b18fd04ccda6a8e3180dfa6c1ef159faf126cb9f7c5b2b581979b0
- calibration rows5bc149c9557c36aed844ccb78d50ac7270bb401b205194831f6382ed7c139eb0
- natural summaryd48e728e96a862bee1400dd73253ac9aed3a3eecf58058752eab6c9c22a46ac7
- listener trials79298d0b764b2d6024f01acc5ae913ee6e1c1a98e83d981036fd51c8c2f196c0

## Remaining roadmap gates

#16:PR #21 review/merge is pending; implementation and verification are not called
merged. #17:Signalsmith/native-zplane acquisition, preserved-formant comparison,
full alignment/stereo checks, independent licensed confirmation recordings and
real listener/host evidence remain open. The new off-only player/registry is a
working prerequisite, not completion of formant-preserving product selection.
#18 staged adoption, #19 gap-driven research and #20 environment expansion are not
started by this patch. No new detector-repair research is substituted for them.

Use docs/CALIBRATED_LISTENING.md for explicit panels, request lists, calibrate/render/
pack commands and evidence limits. Listener audio is delivered separately from
organizer keys and reproducibility records. User/source/vendor audio and native
libraries are not committed to git. This record makes no native-zplane, blind-score,
OS realtime, formant-quality or commercial-parity claim.
