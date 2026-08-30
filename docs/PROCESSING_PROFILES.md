# Manual processing profiles

boiled egg deliberately uses **manual processing profiles** rather than silently switching algorithms based on an opaque signal classifier. The profile is selected when the DSP handle is created and remains fixed until the handle is recreated.

This mirrors the product requirement that a DAW/project should sound reproducible: loading the same project with the same profile must not pick a different backend because a classifier threshold moved.

## Public C ABI

Use `boiledegg_create_ex()` with a `boiledegg_profile_config`.

- `BOILEDEGG_QUALITY_GENERAL` — balanced general-purpose/polyphonic processing.
- `BOILEDEGG_QUALITY_TRANSIENT` — attack/transient locality is prioritized. The current production backend uses a shorter WSOLA window/search footprint.
- `BOILEDEGG_QUALITY_EFFICIENT` — reduced correlation-search work for lower CPU use.
- `BOILEDEGG_QUALITY_MONOPHONIC` — reserved for the dedicated single-pitch backend. It is intentionally reported as unsupported until that backend passes the quality/realtime gates.

`boiledegg_create()` remains binary/source compatible and is equivalent to `boiledegg_create_ex()` with `boiledegg_default_profile()`.

Profile changes are **lifecycle operations**, not sample-accurate automation. Hosts should recreate/reactivate the instance when changing them.

## Formant handling

`BOILEDEGG_FORMANT_PRESERVE` is already part of the profile ABI, but the current production WSOLA backend reports it as unsupported. This avoids exposing a checkbox that is silently a no-op.

The research backend is developing two different implementations behind the same user-facing intent:

1. **Harmonic/polyphonic preservation** — linked-channel spectral-envelope estimation and compensation suitable for voices, instruments and mixes with multiple simultaneous partial structures.
2. **Monophonic preservation** — a pitch-aware path that estimates a dominant F0 and limits positive spectral-envelope gain to harmonic neighborhoods, reducing amplification of spectral valleys/noise.

The two implementations must remain separate internally even if a plugin UI later presents a single `Preserve Formants` switch.

## Promotion gates

A research backend may become a supported product profile only after all of the following pass:

- exact output-duration and pitch-accuracy regression;
- Roberts/Paliwal TSM objective/MOS-proxy comparison against the current production baseline;
- deterministic synthetic formant-envelope fixtures;
- speech and harmonic/polyphonic listening fixtures;
- stereo-link/image regression;
- allocation-free hot-path test;
- ASan/UBSan and ThreadSanitizer where applicable;
- callback p99/deadline gate at 44.1/48/96 kHz including 32-frame blocks;
- CLAP/VST3 host lifecycle and state compatibility.

For downward pitch shifts, bandwidth extension is a separate quality requirement: envelope preservation alone cannot recreate source excitation above the frequency range retained by the downshift/resampling operation.
