# Roadmap B / Issue17: independent formant-reference audit

Base:576ebb2ae863a97e04247548ee73a17ab948587c (PR22). A/Issue16 is already merged
via PR21 into main5a7a62af. This change adds evaluation only, not a new DSP,
production backend, or automatic listening eligibility.

## Question and fixed primary grid

Can the existing spectral preview preserve an explicitly defined smooth filter
shape when the excitation pitch changes? Compare its General/Transient modes,
each Off/Harmonic/Monophonic, to the installed direct offline Rubber Band R3,
Off/Preserved. The direct reference runs its own study+process; do not confuse
this with FFmpeg's realtime filter. Preserve each engine's exact named policy:
Rubber Band Preserved does not imply a named Monophonic/Harmonic distinction.

Two synthetic resonance contours, F0=110/220Hz,48/96k, six shifts -12/-7/-3/3/7/12,
mono, eight configurations =384 output renders. Full2second FLOAT inputs with
fixed harmonic phases, source partials through8kHz. Fundamental gain follows the
harmonic excitation; no neural vocoder or native-zplane substitute. Fixtures are
analytical abstractions, not real singing or a general polyphonic validation.

For harmonic k, source coefficient is S(k)*E(k*F0). Intended Off output is the
same coefficient at k*F0*p; intended preserved output is S(k)*E(k*F0*p) there.
Thus the filter contour stays fixed while the excitation pitch moves. Both ideal
shapes are computed independently of any tested DSP. Use only output harmonics
150..6000Hz whose source partial was present. All selected supports remain below
Nyquist in this grid. Analyze the fixed central interval [.25,1.75]seconds, no
fitted alignment. Hann FFT integrates disjoint neighborhoods of known harmonic
frequencies; absolute scalar gain is reported separately, not silently removed
from raw audio. Shape error removes only the mean log-level difference from the
metric, not the output. Report ideal-target error, retained-envelope error and
raw gain/peak. A diagnostic improvement is not a perceptual-quality percentage.

## Acceptance and controls

Hard implementation gates: pure/nonmutating fixture and metric, gain/known-error
calibration, float conversion, exact operation and frame/rate/channel metadata,
finite outputs, unchanged source/adapter/library hashes and complete grid. Bad
renders remain failed with receipts and logs. No post-hoc threshold adjustment,
resampling/padding/normalizing output, best-mode picking, or natural-voice win.
No hard envelope-quality cutoff is invented: results decide the next question.

The existing operation-calibrated blind-pack API remains Off-only. This audit
must not turn a mode into eligible merely because the preservation flag routes.
Formant listening, stereo/time alignment, Signalsmith/native acquisition, new
licensed natural material and real-host observations remain separate B gates.
No listener responses means no MOS or adoption decision. Product C/API/ABI/UI,
old state and all research algorithms remain unchanged.

Primary API semantics checked against official Rubber Band documentation:
https://breakfastquay.com/rubberband/integration.html
https://breakfastquay.com/rubberband/code-doc/classRubberBand_1_1RubberBandStretcher.html
Actual installed library version/hash is recorded, not asserted latest.
