# Standalone audition: native transport and freeze contract

Status: design amendment, not an implemented SDK capability or a test result.
Branch: app/pyside6-audition-lab, based on main d8e835d6.

## User-visible meaning

Pitch is a displacement in semitones: 0 means unchanged pitch; convert using
pitch_ratio = 2 ** (semitones / 12). Playback speed is independent: 0 means
freeze while continuing to sound, 1 means normal time progression, 4 means
four-times source progression. A separate Pause command stops playback.

Do not implement speed zero as mute, pause, infinite offline rendering, or an
undisclosed common post-render loop. Native backend freeze is the intended path.
Do not describe this amendment as support already present in main.

## SDK ownership

Use an additive source-position/output-driven transport interface, separate from
the existing finite-duration push/pull and fixed-input/output insert contracts.
A caller requests a bounded number of output frames per render call. Source
position and output synthesis time are independent clocks. At equal sample rates:
source_position_next = source_position + speed * output_frames (constant speed).
At speed zero the source anchor does not advance; synthesis and pitch-control
progression continue. Account explicitly for unequal source/output sample rates.

The existing time ratio denotes output duration / input duration; for a positive
constant playback speed it is 1 / speed. Neither infinity nor a zero analysis hop
is a valid way to extend that finite-ratio implementation to freeze. Preserve the
existing API semantics, validation, ABI, output limits and flush behavior.

For a prepared file source, preserve the anchor on freeze, then resume advancing
from it. For a future live-input effect, freeze requires an explicit capture /
drop-or-buffer / resume policy: an arbitrary-duration source pause cannot also
promise fixed end-to-end delay while retaining every new live input sample.
Stored-file transport can retain bounded DSP state independently of hold duration.

## Backend-specific implementation work

PV: retain the local magnitudes, interchannel complex relationships and frequency
estimates derived from nonzero-spaced analysis windows. Continue phase synthesis
at a finite output hop. Do not keep re-estimating frequency by dividing by zero
or setting all phase increments to zero. Use peak phase locking and linked-channel
rotation where appropriate. Pitch/formant controls remain independent during hold;
reset-onset logic must not retrigger an identical frozen attack every frame.

WSOLA/time-domain: native bounded-region grain repetition/overlap with continuity
is a different freeze algorithm and must remain labeled as time-domain freeze,
not a spectral hold. Multiresolution/composite research modes require separate
hold and resume handling for all branches. External engines expose only verified
capabilities; unsupported freeze must not silently select a different algorithm.

Native freeze, time-domain hold, and unsupported are explicit capability states.
Do not expand supported speed or pitch ranges merely by widening UI sliders.
Speed 0..4 including arbitrarily near zero requires output-driven scheduling;
finite output quotas, end-of-source behavior, cancellation and bounds are required.

## Acceptance to implement before declaring success

- Source anchor stays fixed at zero speed; output frames keep increasing.
- Synthetic steady tones remain nonzero with no systematic pitch drift; verify
  frequency and modulation independently of the synthesis implementation.
- Speed 1 -> small positive speed -> 0 -> positive speed changes are continuous
  within declared transition rules, without fitted alignment or a hidden limiter.
- Pitch 0 is unity; pitch changes still operate while source position is frozen.
- Stereo relations, silence/DC, short/end-of-file input and resume are covered.
- Long holds do not grow DSP memory; render calls have bounded output/work and
  no processing-time allocation. Output histories are block-partition invariant.
- Existing SDK modes, ABI and ordinary playback outputs remain regression-tested.
- GUI freeze and Pause are distinct; the GUI never runs DSP on its event thread.

Primary feasibility references (not runtime dependencies or copied code):
Csound mincer documents independently controlled position/pitch and a stationary
source pointer: https://csound.com/docs/manual/mincer.html
Csound pvoc documents stationary position and independent transposition:
https://csound.com/docs/manual/pvoc.html

No native-freeze C++ implementation, rendered proof, GUI integration or quality
qualification is claimed by this protocol commit.
