# Low-register formant detail / 低音域の包絡詳細

`BOILEDEGG_BACKEND_FORMANT_LOW_DETAIL` is an explicit construction option for the
experimental spectral backend. It uses the existing cepstral-envelope estimator
with order80 instead of40 before rate scaling (160 instead of80 at96kHz).
It adds no FFT, larger window, iteration, F0 detector or audio buffer. It does not
change the 60–900Hz F0-search interval. The name describes an envelope-detail
candidate for low-register monophonic material, **not a pitch-range selector**.

## Supported combinations

Use PV General, Monophonic formant policy,48/96kHz, one or two linked channels,
explicit streaming or realtime I/O, time ratio1 and a fixed pitch ratio in[.5,2].
The normal spectral build option and per-handle experimental opt-in are both
required. Other rates, quality modes, Off/Harmonic, WSOLA, time ratios other than1,
or continuous-pitch/time flags are rejected; no fallback or automatic selection.
Existing dynamic formant parameters/events retain their meaning. This option does
not expand the PV time/pitch range and is not a new `QUALITY_MONOPHONIC` backend.

```c
#include <boiled_egg/backend.h>
boiledegg_config audio = boiledegg_default_config(48000, 1);
audio.max_block_size = 64; /* PV supports at most1024, unlike the base default. */
boiledegg_backend_config mode = boiledegg_default_backend_config();
mode.backend_id = BOILEDEGG_BACKEND_PHASE_VOCODER;
mode.quality_mode = BOILEDEGG_QUALITY_GENERAL;
mode.formant_policy = BOILEDEGG_FORMANT_POLICY_MONOPHONIC;
mode.io_contract = BOILEDEGG_IO_STREAMING;
mode.initial_pitch_ratio = 2.0f;
mode.flags = BOILEDEGG_BACKEND_ALLOW_EXPERIMENTAL |
             BOILEDEGG_BACKEND_FORMANT_LOW_DETAIL;
boiledegg_result status = boiledegg_validate_backend_config(&audio, &mode);
/* Only create when status==BOILEDEGG_OK; keep an unsupported result explicit. */
```

Compile with `BOILED_EGG_ENABLE_EXPERIMENTAL_SPECTRAL=ON`. The existing C++
header-only `engine(audio, mode)` constructor accepts the same configuration.
The feature is identified by validation of the complete configuration, not merely
by a broad backend inventory range. Older SDKs reject the unknown flag rather than
silently emulate it.

## Compatibility and persistence

Old flags/defaults and existing PCM are unchanged. There are no new exported
functions, structure fields, parameter/plugin IDs, latency/tail changes or GUI
controls. The flag is immutable and read back through
`boiledegg_get_backend_configuration`. The parameter-only state structures do not
encode construction flags: persist the backend construction configuration alongside
parameter state. Reset preserves the choice; a parameter restore cannot change it.
Existing plugin project/state formats are not extended by this SDK-only option.

## Qualification boundary

The known synthetic check83/check173 regression showed smaller absolute envelope
RMSE in8/8 conditions at±12st and48/96k. It is not independent natural-voice MOS,
stereo naturalness, arbitrary pitch ratios, extreme time-stretch, or evidence of
parity with Soloist/élastique. Harmonic was explicitly excluded after the preceding
experiment found new unwanted-energy failures. A lower envelope error must not
hide new distortion, raw peak changes or callback overruns.

日本語：音色の包絡を細かく扱う、明示選択の限定previewです。入力音域をHzで選ぶ
設定や、REAPERのLowest〜Highestに対応する7段階設定ではありません。既存の品質
モード・保持方針・フォルマント移動量は別軸のままです。旧設定の音と互換性を維持
し、未検証の声・歌唱や自然さ、ハードリアルタイムを認定しません。

Measured scope, negative results and cost receipts are in
`docs/benchmarks/FORMANT_DETAIL_RESULTS_2026-09-23.md` and Issue67.
