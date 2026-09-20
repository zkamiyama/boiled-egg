# R2a phase-gradient reference results — 2026-09-20 JST

Related #45; numerical foundation #44/#50; later #46-49; parent #19/#15, evaluation #17 and default WSOLA defect #41. Base main3a933a043561b11232cb894c12f6ff18daf62f24, tree0aecfc0565d368f86b0059dbdbc5d9177349864d. Existing318 files stay unchanged. The Issue44-49 series already existed; this continuation does not create duplicate issues or reimplement NSDGT.

## Decision and delivered scope

Deliver only a reproducible phase-reference subunit for R2. Actual accepted NSDGT analysis/dual synthesis is reused, and an isolated C++20/23 phase kernel consumes/returns complex coefficients. This is not full SELEBI, external author-output equivalence, pitch/formant/stereo processing or a product quality mode. Issue45 remains open. The original SDK/defaults/ABI/state/IDs/latency/tail/transport/plugins/GUI are unchanged; the research header is not installed or linked into the SDK.

The two explicit methods are backward-difference PV WITHOUT identity phase locking and paper-based PVDR heap integration. The former is NOT the complete IPL-PV baseline in SELEBI and NOT the current SDK PV General. Do not use its large attenuation below to claim superiority over the product or over the paper's actual IPL baseline.

PVDR equations13-18 and Algorithm1 from Prusa/Holighaus EUSIPCO2017 (arXiv2202.07382) define the gradients/integration. Finite boundaries, first-frame initialization from input phase, one-sided edge gradients, positive-spectrum real symmetry, deterministic low-amplitude phase seeds and heap ties are explicit implementation-profile choices. The independent dense reference confirms these implemented equations, not every unspecified author convention. Arbitrary nonuniform-hop arithmetic-mean slopes are separately named an extension, not author-validated PVDR.

SELEBI arXiv2602.16421v1 II/IV-E/VI motivates constant M, actual-hop accounting and22.05k/V2048/hop128/M=V*alpha settings. Its window/hop compression planner and onset masks are NOT implemented in this subunit. The earlier full-band anchor construction is not reused. No learned score, source stems, oracle marker or hidden alternate algorithm is used.

## Fixed experiment

Protocol9a4037c06481865961ebd55e7922edbc246830b7 precedes new implementation tests and acoustic measurement. Before the full run, plan SHA256
`7b060f96066d02c1d45b931c127b216809c152681cf887ff9ce254dccdea085d`
was posted to Issue45 comment5749161468. It binds all input/code/NSDGT/phase ELF/dependencies/settings/environment. No waveform code, input, window, phase rule or threshold was changed after looking at acoustic results.

Eight generated1second inputs:61Hz/1000Hz pure tones,61-to861Hz chirp, impulse, impulse+1000Hz, impulse+1000/2000/3000Hz, causal50Hz decaying transient, and that transient+1000Hz. Exact amplitudes/timing/decay/fades are in the protocol and fixture. These are our declared synthetic diagnostics, not the original paper's complete dataset or natural-audio holdout. No MOS was produced.

Rate22050; alpha1/2/4; V2048 Hann, M=2048*alpha. Fixed analysis hop128/alpha and an irregular extension repeating[1,.5,1,.75] times that hop. Synthesis centers are alpha*analysis centers, never cumulative rounded-hop clocks; endpoint L-1 and zero extension are explicit. There is no alpha1 bypass.8inputs x3alpha x2schedules x2methods=96cells, each3 complete fresh passes:288/288 completed. Output length and finite/nonzero checks pass. Each cell's output/coefficient/modified-coefficient/gradient/predecessor hashes match across repeats. All288 saved complex outputs and decompressed predecessor traces were read back and verified, including trace counts versus native counters.

Large coefficient/gradient arrays are reproducible from retained inputs/schedules and identified by hash. Full audio outputs and full predecessor traces are retained; small independent control arrays are stored. A hash is not a substitute for an unexecuted comparison. The protocol exists as a separate preregistration commit; local measured source has318 prior files plus7 measured implementation/test files. Final source also adds protocol/workflow/results without changing those seven files. Final CI uses its own complete-tree plan and binary identities.

## Numerical conformance and actual test results

36 independent small coefficient cases (FFT16/32/64, regular/irregular centers,3alpha,2methods) agree with a Python complex128 dense sorted-priority reference. Maximum normalized complex error3.559072954923187e-8 (limit3e-6); predecessor arrays match exactly; gradients match at1e-12 absolute/relative. Analytic phase planes force both time and frequency paths. Low-phase seed changes affect only insignificant bins in the relevant control. Erasing/scaling coefficients and passing through actual synthesis verifies no hidden input-copy bypass.

Across the acoustic grid maximum coefficient magnitude change is5.9480634255489004e-8, below3e-6. Exact Hermitian output is explicitly constructed, and imaginary reconstruction residue is independently retained. Mathematical zero coefficients produce zero output; nonzero acoustic fixtures cannot pass as all-zero output.

Local tests actually completed, with unique enabled counts and skip0:
-66 Python methods (11new+55existing scoped numerical/measurement/contract controls).
-Phase kernel GCC20/GCC23/Clang20/Clang23:11CTest each, including C11 entry.
-Clang ASan/UBSan/leak checks:11/11.
-GCC TSan:1/1 independent-call concurrency test; not concurrent operations on one retained instance.
-Unchanged NSDGT:12/12 CTest.
-Fresh unchanged spectral-ON SDK:26/26 CTest, inventory/JUnit checked.

Before the full grid, fault injection of rows labelled complete but missing evidence caused an assessor KeyError. Original source and failure log are retained. A fail-closed identity/finite/required-field guard and a negative test were added BEFORE the registered acoustic run. No completed acoustic results were retuned, and no old measurement was attached to a rebuilt binary. Further malformed or adversarial schemas beyond tested contracts are not universally certified.

## Acoustic observations: not a quality qualification

Each table row below covers24cells=8signals x3alpha. Pure-tone count6=2tones x3alpha;2 are identity. Numeric identity error is unaligned/unfitted relative L2, not a perceptual score.

|Schedule/method|Pure-tone3-gate pass|Maximum alpha1 relative L2|
|---|---:|---:|
|fixed/backward PV no IPL|2/6|3.001069615e-7|
|fixed/PVDR profile|6/6|1.931174040|
|irregular/backward PV no IPL|2/6|3.030423841e-7|
|irregular/PVDR extension|6/6|1.805114388|

The3 tone gates are5cent,1dB target-sinusoid amplitude and1% unexplained energy on the settled interval. The PVDR profile passed all8 nonidentity tone cells across both schedules, but this is only two synthetic frequencies. Its large alpha1 waveform difference is NOT hidden by bypass, alignment, gain fitting or a new threshold. It may include global phase changes as well as other deviations; relative L2 alone does not prove audible loss. It does mean that this exact profile is not a sample-transparent unity product path. External author-output checks and initialization/gradient boundary differences remain outstanding.

Fixed-hop61Hz examples:

|alpha|backward PV amplitude error dB|PVDR amplitude error dB|backward/PVDR spectral error|
|---|---:|---:|---|
|2|-2.308963|-0.033949|0.255332/0.052145|
|4|-24.406550|-0.010909|0.936149/0.121178|

Both dominant-frequency errors are near zero in these examples; frequency alone misses the baseline amplitude loss. The backward-only/no-IPL implementation is deliberately weak as a phase ablation. These numbers are not measurements of SDK PV General, SELEBI's IPL-PV or commercial software. Never call them an engine ranking.

A causal50Hz decay exposes a remaining transient problem:

|alpha|method|Event-neighborhood spectral error|Energy-centroid error vs oracle ms|5-95% energy width ms|
|---|---|---:|---:|---:|
|2|backward PV no IPL|0.446956|12.774544|69.206350|
|2|PVDR profile|0.425490|11.854660|66.394560|
|4|backward PV no IPL|0.943970|32.948346|88.435370|
|4|PVDR profile|0.936626|32.373963|84.716550|

This centroid is NOT an onset estimate. The oracle moves the decay onset to alpha*source_time while preserving its decay constant; it is a specified engineering target, not the unique ideal for every audio source. Mixture measurements remain full-band and are not called isolated transient accuracy. Although the profile improves some spectral errors, phase processing alone has not solved decay-time localization. Isolated impulses also retain nonzero spectral error: at alpha4 backward/PVDR full errors0.306886/0.307989, and widths0/0.272109ms. Improvement is not uniform across inputs/metrics.

Spectral error is Eq13-type Frobenius magnitude difference but uses our fixed independent2048Hann/128hop evaluation transform and explicit finite boundaries. It is not claimed to reproduce TableII. Raw peak/RMS/imaginary residue, full and local errors, uncorrected centroid/width/energy, alpha1 differences and all repetitions are retained. No gain/lag fitting, clipping, resampling, DTW, successful-subset scoring or source replacement hides failures.

## Runtime and memory

Median of each cell's3 full-pass times, then median/max over24cells (seconds):

|Schedule/method|median|max|
|---|---:|---:|
|fixed/backward PV|0.229124|1.275332|
|fixed/PVDR|0.242281|1.288906|
|irregular/backward PV|0.287427|1.736862|
|irregular/PVDR|0.300842|1.837818|

Each full pass includes actual analysis, phase and dual synthesis plus host allocation/call overhead; separate stages are recorded. Output lengths differ withalpha. This is not callback deadline capacity or the prior1.25x real-time cost gate. The phase kernel's maximum analytical workspace estimate is209,523,352bytes; caller coefficient/gradient/output buffers and NSDGT workspace are additional. Full Python measurement-process peakRSS593,172KiB is not per-instance owned memory. Allocations and one-frame lookahead are intentional in this NRT reference, with no hard-RT/noalloc or fixed product-latency claim.

## Recorded identities and reproduction

Local phase ELF SHA256: ce9ec1e43f462e64d3ab8674be8c77e28c4b8a7d41ab0a4c5c85743fd98b931c.
Local unchanged NSDGT ELF SHA256: bf6eca0fe752e4408816d4919f71c3d5503bf9f5c08386fc228660a58eb61f82.
Phase source SHA256:3173396b6197857d0a6f0413e15ebd1afc80f6c0b8194e8f299378dce595ae51.
Runner SHA256:06068dba9096fb10bd08d5bd3a046d41ee4d90767b4d790e1a0630897a59f66b.
Test SHA256:3378157e6ad24130e356d8b21a79500840f4f0562f5dd02b06beecabccdbd639.
Summary SHA256:5565e0f26e2be2318ae2fb38f1d757b25c465abc08e26b2b4739168cb860d728.

Build and store evidence outside source, register each new plan before its run:

```sh
cmake -S research/nsdgt -B /tmp/be-nsg -DCMAKE_BUILD_TYPE=Release
cmake --build /tmp/be-nsg -j2
cmake -S research/pvdr_phase -B /tmp/be-phase -DCMAKE_BUILD_TYPE=Release
cmake --build /tmp/be-phase -j2
export PYTHONPATH=eval OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
python eval/pvdr_phase_reference.py prepare --phase /tmp/be-phase/libpvdr_phase.so --nsdgt /tmp/be-nsg/libnsdgt.so --output /tmp/be-phase-plan
python eval/pvdr_phase_reference.py run --plan /tmp/be-phase-plan/plan.json --sha256 REGISTERED_SHA --output /tmp/be-phase-results
```

Final CI/head/review/merge and Drive readback are recorded in the PR and latest Issue45/19/15 comments. CI has its own binaries/plan/timing, not relabelled local evidence. Next R2 work is exact author-convention comparison and SELEBI's actual mask/window/hop planner with explicit difference table; IPL baseline is needed before a paper-table reproduction claim. R3/#46 pitch compression/up-down,48/96k and joint bass/event validation are later. #47 is conditional, #48/#49 separate product promotion tracks. Existing WSOLA defect41 and parent quality/research issues remain unfinished.

Primary sources: https://arxiv.org/pdf/2202.07382 ; https://arxiv.org/html/2602.16421v1 ; https://github.com/ltfat/phaseret . External GPL author implementation has not been copied into this repository. Source availability, licenses and original datasets remain separate reproduction requirements.
