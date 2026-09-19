# Offline PV phase-reconstruction research

A separately built C++20/23 **non-real-time finite-file renderer**. It never
becomes the SDK's default backend, installs no public ABI, and has no plugin or
Audition Lab UI integration. Select it explicitly. This is a research tool, not
a certified high-quality or mastering mode.

```sh
cmake -S research/offline_pv -B build-offline -DCMAKE_BUILD_TYPE=Release
cmake --build build-offline -j2
python quality/audition/run_ctest.py --build build-offline --expected 5
build-offline/boiled_egg_offline_pv input.wav NEW_OUTPUT_DIRECTORY \
  --execution offline --allow-experimental --iterations 32 \
  --time 1 --pitch-semitones -12 --formant off
```

The output directory must not exist. Success writes raw float32 `output.wav`
and `report.json`. Validation failure writes a blocked report in the newly
created directory, removes partial WAV output and returns2; an already existing
directory is untouched. Parent directories must exist. This CLI uses English
errors; it is not exposed as a new Japanese/English GUI option.

## Explicit capability, not quality certification

| Property | Supported in this initial research profile |
|---|---|
| Input | WAV, 48/96kHz, mono; no implicit resampling/downmix |
| File length | Nonempty, at most30 seconds; file size limit24,000,000 bytes |
| Time ratio | 0.5–2, defined as output length / input length |
| Pitch | Constant -12 to +12 semitones |
| Formant | Off only; other requests fail rather than silently change |
| Iterations | Explicit0,8,32; zero is the paired PV-seed control |
| Memory | At most512MiB conservative estimated owned work; not process-RSS guarantee |
| Execution | Synchronous offline whole-file with allocations; not an audio callback |
| Unsupported | Live input, speed0/freeze, stereo, automation/ramp, preserved formants |

A render can take longer than playback. No fixed real-time latency or PDC promise
is made. Timing in the screen includes fresh-process startup and WAV I/O; it is
not callback CPU capacity. A future product-level offline job API, cancellation,
progress UI, longer files, allocation accounting and distribution review are
separate tasks. Do not simply run this CLI inside an audio callback.

## Algorithm identity

`pv-seeded-griffin-lim-research-v1`: centered square-root-Hann STFT with FFT4096,
hop256 at48k (both double at96k), linearly mapped magnitudes and classic PV phase
seed; alternate overlap-add/reanalysis with fixed-magnitude replacement for the
specified iteration count. Intermediate stretch factor is `time_ratio *
pitch_ratio`. Pitch conversion uses our centered65-position Blackman-windowed
sinc resampler, cutoff`.95 * min(1, 1/pitch_ratio)`. It is bypassed only when
pitch_ratio is exactly1, not as an identity shortcut around the transform.

This is our engineering combination of established methods. It is NOT SELEBI,
not the current SDK PV with an extra quality flag, and not a reconstruction of
the historical multi-resolution implementation. Own magnitude residual is saved
for every iteration, but is an optimization objective, not a naturalness score.
No reference/oracle waveform, event positions, fitted output gain or fitted lag
enters the renderer. Fixed windows may preserve a smeared target magnitude;
more iterations can therefore improve that objective while worsening a useful
acoustic property. Preserve the failures and do not automatically promote32 over8.

## Fixed comparison

See `docs/benchmarks/OFFLINE_PV_PROTOCOL_2026-09-20.md`. The actual historical
native MR control must be built separately from commit
`dd04c9388443ff3358af34b85ca5a5c880f45e71`; never merge that whole branch as a
side effect. Its1024/256+512/192 windows are kept at both rates as the historical
code specifies (unlike this rate-scaled candidate).

```sh
python eval/offline_pv_benchmark.py prepare \
  --sdk build-main/boiled_egg_backend_cli \
  --legacy build-legacy/boiled_egg_multires_rt_cli \
  --offline build-offline/boiled_egg_offline_pv --output NEW_EXPERIMENT
# Store the printed SHA256 before executing the grid.
python eval/offline_pv_benchmark.py run --plan NEW_EXPERIMENT/plan.json \
  --plan-sha256 REGISTERED_SHA256 --output NEW_RESULTS
python eval/offline_pv_assess.py --summary NEW_RESULTS/summary.json \
  --output NEW_RESULTS/assessment.json
```

Plans bind local absolute binary/dependency/source paths. Reproduction in another
environment creates its own new plan and hashes; it must not relabel old timing
records as measurements of rebuilt binaries. Compare each output and preserve
all210 settings/630 runs. No synthetic fixture is natural-audio MOS evidence.

## 日本語の要点

非リアルタイム専用・有限ファイルの研究モードです。重い反復計算を使えますが、
既存SDKやDAWの既定処理は変更しません。48/96k・モノラル・フォルマントOffだけを
明示対応し、未対応条件は拒否します。0/8/32回の反復を利用者が選択します。
目的関数が改善しても、音程・アタック位置・広がりが改善したとは限りません。
試験と結果の中止条件を確認し、製品品質や総合的な自然さの保証には使わないでください。
