# Complementary component / transient transport study — 2026-09-15

Base: 58f1c6b7c6e34967cad92f63cf6f6897d0f9b6fa. No production changes.

## Hypothesis and scope

The preceding phase-edge/projection study improves spectral descriptors but does
not preserve local attack timing. Test magnitude-time placement jointly with
phase by separating complementary linked harmonic/percussive components.
Long-window PV treats harmonic material; a short time-domain overlap-add path
moves actual percussive waveform grains, not just their spectral phases.
A separate anchored-grain variant preserves local unit time slope around detected
percussive events. This is an OFFLINE constant-TSM study, T in[.5,2], pitch=1.
No formant preservation, dynamic automation, new live plugin or RT claim.

Driedger/Mueller/Ewert (2014) motivates long-PV/short-OLA separation. SELEBI
(Akaishi/Holighaus/Yatabe,2026) motivates resolving magnitude/phase localization
together; our separation and grain maps are NOT a reproduction of SELEBI.
Implement independently; do not copy reference or copyleft implementation code.

## Fixed comparators

1. locked: unchanged inherited full-band identity-phase-lock renderer.
2. heap: unchanged inherited full-band phase-gradient heap renderer.
3. split_heap_long: same complementary separation, both components long heap PV.
4. split_locked_ola: long locked harmonic branch plus short percussive OLA.
5. split_heap_ola: long heap harmonic branch plus short percussive OLA.
6. split_heap_anchor: same as5, with prescribed percussive-event anchor mapping.

All outputs have the same source and exact round(T*input_frames) duration. No
per-file winner selection, waveform normalization, limiter, fitted offset or DTW.
The manual experiment choice is not automatic product profile selection.
Separation uses2048 Hann / hop256 at48k, doubled at96k;31-frame temporal and
31-bin spectral medians, shared channel-power magnitude; a complementary squared
soft mask. Zero-energy cells have neutral masks. Harmonic long window2048 and
inherited heap settings. Percussive grains256 / synthesis hop64 at48k, doubled
at96k. No full-band512-FFT replacement of the product is involved.
Anchors: peaks in a1ms smoothed percussive power envelope,40ms minimum spacing,
5% maximum prominence, above4x centered50ms local median. Protect +/-12ms,
clipped to20% neighboring/end gaps times min(1,T), maintaining monotonic maps.
Both source and output maps pass through each detected anchor (u,T*u); local
input/output slope is1. Outside protected intervals use monotone linear joins.
No target/oracle information enters detection or synthesis.

## Confirmation and metrics

Pilot sources: Ardour_2,Female_4,Male_6,Rock_4,Triangle_02; report all, freeze any
change before the other15 sources. This is within-iteration confirmation only;
the20-source archive has been used historically. Full natural grid uses these20
actual references x T=.5,1.5,2 x6 methods. Do not substitute unavailable audio.

Analytic grid:48/96k, T=.5,1,1.5,2; tonal bank,55Hz, isolated2ms/20ms attacks,
noise bursts, staggered stereo attacks and mixed steady/attack content. Include
exact identity, expected attack time/width/energy, pre/post leakage, partial
balance, and stereo diagnostics. Compare against explicit analytical target
support, not 'narrower is always better'. Separate eight mixed-source seeds
26091520..26091527 at both rates/T=.5,1.5,2 after design freeze.

Reuse preceding5ms RMS-shape, onset-flux correlation, global Welch PSD and
512/2048/8192 local-STFT shape definitions unchanged. Do not pool with older
cepstral metrics. Source-relative descriptors are not ideal-waveform/native
zplane error or MOS. Record decomposition residual/energy, detection counts,
actual protected support, raw peaks and all negative results. Bootstrap source
clusters (4000 draws,seed260915), retain all methods; no multiplicity correction.

Correctness: independent mask/map/OLA oracles, complement identity, zero/short/
odd signals, deterministic ties, no source mutation, finite/exact output,
anti-phase and channel permutation. Standalone C++ anchor interpolation helper
must be allocation-free with bounded lookup and sanitizer/numerical checks.
Full offline Python renderer is explicitly not allocation-free or RT qualified.

Save input/source/analysis/kernel hashes and full grid manifests. Primary results
must not count repeated baseline renders as independent sources. Product/main,
ABI, current pitch/time ramps, CLAP/VST3 and state remain unchanged.

Primary conceptual sources:
https://www.audiolabs-erlangen.de/resources/2014-SPL-HPTSM/
https://arxiv.org/html/2602.16421v1
