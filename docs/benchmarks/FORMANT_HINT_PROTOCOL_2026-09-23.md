# Low-input formant hint: bounded experiment, 2026-09-23 JST

Issue67, parent60/15. Base main086a26daec314534a4246203636bafa84d0c1373,
tree b24f4f7f7bf2418906e3b3624427339bd463a5ee. This local source snapshot is
verified against371 file hashes and that tree. Prior cost results are history,
not new measurements. PR66 is a separate older-base alternative, not merged here.

## Hypothesis fixed before audio results
Reuse current PV construction options, not a new algorithm or additional FFT.
A cepstral lifter below the fundamental period can retain a spectral envelope;
see Julius O. Smith, Spectral Audio Signal Processing, Cepstral Windowing,
https://www.dsprelated.com/freebooks/sasp/Cepstral_Windowing.html . That principle
does not validate these numbers or guarantee naturalness. Our hypothesis is that
order80 can represent low-register envelopes better than40; independently narrow
the monophonic F0 search from60–900Hz to60–240Hz. No changes to gain limit15dB,
window, hop, frame scheduling, pitch/time, public ABI/state/IDs/default/latency.

Four explicit test-adapter configurations before existing rate scaling:
legacy(40,60,900); range_only(40,60,240); detail_only(80,60,900); low(80,60,240).
At96k, the existing rate policy doubles the lifter order and FFT/hop. Harmonic
does not use the F0 range, so those pairs must match. No automatic source detection,
no claimed equivalence to elastique's named ranges, and no installed presets yet.

Development uses existing vowel120/vowel220 generators. Confirmation uses83/173Hz
with distinct resonances590/1630/2710Hz, widths115/155/195Hz and phase .43k+.013k².
These are small synthetic sources, not previously unseen natural-voice validation.
Two rates48/96k, General, Harmonic/Monophonic, shifts-12/+12, time1/block64,
four profiles andthree repeats:192 per stage,384 render attempts. All source Wavs,
code/executable/dependency identities and full grids are locked in plan.json.
Select per-policy minimum development mean preserved-envelope RMSE; ties follow
legacy-first table order. Publish selection hash BEFORE confirmation rendering.
Do not retune to confirmation. All four profiles still render for diagnosis.

Reuse current joint sinusoidal measurement, fixed central1s interval,250–3500Hz
band and absolute amplitude targets; no gain, lag, DTW, clipping or ideal-output
substitution. Preserve peak/RMS/unexplained energy and all failures independently.
New profile acceptance requires >=6/8 confirmation improvements, mean RMSE<=90%
of legacy, no new >1% unexplained-energy failures where legacy passed, no new
peak>1. This is a narrow synthetic gate, not naturalness or vendor superiority.
CPU comparison must use3 complete repetitions per fixed configuration, same work,
<=1.25 cost ratio in every setting and aggregate median<=1.10. Setup, EOF and
individual service maxima/deadline overruns are separate. No hardRT claim.
If these gates fail, retain adapter/negative findings and do NOT change SDK defaults
or expose a preset as a qualified improvement.

## Verification
Unknown hints/invalid arguments/failed processes/zero output/incomplete grids fail
closed. Compare legacy probe with actual public SDK and existing oracle, verify
reset and Harmonic invariance, scheduled paths, GCC/Clang20/23, ASan/UBSan, process
new-allocation count, source preservation, finite output and repeat PCM. A separate
readback checks every saved waveform and receipt. Different binaries require new
identities, never borrowed old successes. Cost measurements are adapter/native
service, not a physical audio callback. No vendor execution or Drive upload.
