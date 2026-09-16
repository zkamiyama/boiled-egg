# Static stereo integration contract — 2026-09-16

Roadmap #15/#17, scoped integration review from #25. Base is #27 checkpoint
9ce32bb62c78674d0d66239854dc65c3c713137d. This change integrates the already
verified #26 pooled static stereo repair and #27 exact-output optimization into
the actual opt-in spectral sources. It is not another estimator or quality model.
Existing patches remain immutable historical/reproduction inputs and must not be
applied again to the integrated source.

## Frozen scope

Only static non-Fuzzy multichannel PV changes from the former unpatched SDK.
Mono, WSOLA, continuous-pitch/time arithmetic, ABI, parameter IDs, state, reported
latency and plugin defaults must remain unchanged. The spectral build option and
per-instance experimental flag are still required. This branch does not promote
research renderers, change stable main or claim broad perceptual superiority.
The corrected stereo path must be compiled directly from this checkout; a CI
that tests only a separately patched dependency is insufficient for this step.

## Integration acceptance

1. The two integrated runtime files must be byte-identical to applying
   pooled_static_stereo.patch then static_stereo_cost.patch to the pinned
   f8e5ef2cbce84f396597860a408b4a3084796115 source. Do not edit the preserved patches.
2. Promote the existing 288-static/12-dynamic spatial regression to an ordinary
   opt-in CTest. Retain 1e-5 proportionality, exact block32/257 equivalence and
   nonzero/finite output requirements. No relaxed thresholds or fitted audio.
3. Add focused integration regression for static reset, empty/parameter-only
   calls, in-place processing, state restoration and duplicate/channel-exchanged
   inputs. Tests must check declared latency/tail and fail under the unpatched
   stereo path rather than pass because they never exercise it.
4. Replay 144 static and 12 dynamic whole-output histories against an independent
   build of the preserved patch chain. Require exact fingerprints with the same
   compiler/options, not approximate metric agreement or cross-compiler identity.
5. GCC/Clang C++20/23, ASan/UBSan, TSan, spectral OFF and installed C/C++ consumers
   remain checked. Run the original strict stereo/time audit against the direct
   integrated build, not a substitute dependency. Existing host CI remains intact.
6. Reuse the predeclared empirical capacity policy (state-best-of-three <=80% of
   period) and <=1.25 original mean-cost ratio without changing thresholds.
   The predecessor's cost study is not relabeled a new run. Newly measured runs
   must retain cold rows, maxima, deadline misses and actual complete-run counts.

No listener responses are required to establish exact equivalence with the
already corrected/optimized output. Natural quality estimation remains separate:
OMOQ or any other frozen model requires source-and-engine held-out validation
before providing automated musical-quality selection. No MOS is inferred here.
