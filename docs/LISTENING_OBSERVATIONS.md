# Explicit listening observations (roadmap #15 / #17)

The calibrated panel can now be carried from verified raw outputs to anonymous
presentation and back to explicitly submitted observations. This is evaluation
infrastructure, not a new DSP or an automatic backend-adoption decision.

`calibrated_listening.make_pack` verifies every presentation transform, creates
`organizer/integrity.json`, and checks the complete pack before publication. The
index covers the player, public trial list, all presentation WAVs and organizer
key/evidence/report. It excludes only itself. Keep its SHA256 separately when
sharing/archiving. Hashes detect divergence from a trusted record; they do not
prove listener identity or make arbitrary edits cryptographically impossible.
The organizer-to-candidate mapping must match the embedded successful render
receipts, not merely a matching self-generated checksum.

## Collecting observations

Share only `listener/`, not `organizer/`. Participants use the generated HTML and
export `ratings.json`; blanks are not filled with default ratings. Keep each
export outside the immutable pack, with an anonymous participant identifier.
Do not reuse the same identifier or submission file as multiple listeners.

Create a submission manifest, for example:

```json
[
  {"listener_id":"L001","path":"/absolute/responses/L001.json"},
  {"listener_id":"L002","path":"/absolute/responses/L002.json"}
]
```

Then run from the checkout:

```sh
python eval/listening_results.py --pack results/listening \
  --submissions submissions.json --output results/observations \
  --expected-index-sha256 HASH_RECORDED_WHEN_PACK_WAS_CREATED
```

`submissions.json` equal to `[]` deliberately generates a no-response report:
`explicit_ratings=0`, all means/differences `null`, `quality_selection=null`.
It does not produce a neutral score, zero-quality score, MOS or a winning engine.
The report and explicit-observation table are published atomically to a NEW
output directory. Existing evidence and reports are not overwritten.

## What is compared

A scoring panel is one participant, one trial and one dimension (naturalness,
attack or sustain). Only panels with all candidates explicitly rated contribute
to descriptive candidate means or paired differences. Incomplete panels and all
valid responses remain recorded. Unrelated ratings from different listeners or
sources are never paired. Candidate means/deltas first average each contributing
listener's complete panels, then weight those listeners equally. The counts
expose unequal trial coverage; equal listener weighting does not make such a
sample representative. The 1..5 values are exploratory ordinal responses; their
arithmetic summaries are not a certified quality scale or a significance test.

Wrong-pack responses, duplicate trial/choice/dimension ratings, unknown choices,
nonfinite/boolean/out-of-range scores, changed audio/player/key files, invalid
organizer mappings and missing evidence are rejected before output is published.
Original recordings and renderer binaries need not still exist to audit an
already generated presentation; the embedded receipts and separately trusted
index preserve its recorded identity. Re-rendering still needs the original
calibration dependencies and files.

## Scope left open

The existing panel is **Formant Off only**. Preserved-formant fidelity and timing,
complex stereo, independent licensed confirmation audio, native-zplane/Signalsmith
references, real-DAW listening and use-case adoption remain open under #17. The
original is only orientation audio, not the unique ideal transformed waveform.
No sample-synchronous player or formal ITU-R compliance is claimed. The reference
method context remains ITU-R BS.2132; this small HTML player is not its full study
procedure. Raw output is unaltered; presentation keeps the one common peak-safe
attenuation per trial already documented in CALIBRATED_LISTENING.md.

## Tests

```sh
PYTHONPATH=eval python -W error::ResourceWarning -m unittest -v \
  test_calibrated_listening test_listening_results
```

The observation tests use clearly labeled fabricated bookkeeping fixtures only;
those numbers are never reported as human responses or audio-quality evidence.
Actual executable integration uses the existing `test_candidate_integration.py`.
