# Evaluation baselines

The project library has no dependency on any competitor implementation. Baselines live under `third_party/eval-only/`, which is gitignored, and are used only to render comparison outputs.

## Signalsmith Stretch

- Source: https://github.com/Signalsmith-Audio/signalsmith-stretch
- Licence: MIT
- Useful features for comparison: streaming pitch/time processing, reported input/output latency, automation guidance, formant compensation, and split-computation support.

## Rubber Band

- Source: https://github.com/breakfastquay/rubberband
- Licence: GPL-2.0-or-later unless a separate commercial licence is obtained.
- The command-line form is documented as `rubberband -t <timeratio> -p <semitones> input.wav output.wav`.
- Keep it evaluation-only unless the licensing choice for the product explicitly permits integration.

## zplane elastique

Do not commit zplane SDK binaries, headers, licence keys, or rendered material whose licence forbids redistribution. Put licensed local material under `third_party/local/` or `data/external/elastique_ref/` (both should remain untracked) and render references locally.
