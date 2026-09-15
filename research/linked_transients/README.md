# Linked transient detection and shared-phase recombination

Offline constant-time-stretch research, pitch=1, rates44.1/48/96k. No product
backend, formant preservation, variable automation, host GUI or realtime claim.
The public SDK and stable main are unchanged. This directory does not use the
previous transient study's blocked/local-only fixture, metric or study files.
All of THIS study's numerical tests, primary evaluation and result auditing run
from the repository checkout. Prior published renderers remain dependencies.

## Build and test

```sh
cmake -S research/linked_transients -B build-linked -G Ninja -DCMAKE_BUILD_TYPE=Release
cmake --build build-linked -j2
ctest --test-dir build-linked --output-on-failure
python -m pip install numpy==2.3.5 scipy==1.17.0 soundfile==0.13.1
export BOILED_EGG_PHASE_HEAP_LIBRARY="$PWD/build-linked/libphase_heap.so"
export BOILED_EGG_LINKED_EVENTS_LIBRARY="$PWD/build-linked/liblinked_events.so"
OPENBLAS_NUM_THREADS=1 python -m unittest discover -s research/linked_transients -p 'test_*.py' -v
```

`event_fusion` preallocates its work vector and sorts at most the supplied
construction capacity. Events in one group must span no more than the tolerance
from the first event; adjacent tiny gaps cannot chain into a large merged group.
The highest normalized prominence wins; time breaks ties. Invalid input leaves
output untouched. This kernel is allocation-free, not the Python detector or
complete audio pipeline. Its C bridge is isolated research, not a public SDK ABI.

`detection.py` compares inherited global40, spacing-only global6 and per-channel6
with1ms fusion. It deliberately retains the inherited envelope/prominence tests.
The known27ms opposite-channel deletion is fixed, but weak/transient-free channels
with tonal residuals can generate false positives. No input class is silently
mapped to a different product profile.

`recombine.py` computes one full-band phase field R. For fixed R, analysis,
coefficient rotation and overlap-add are linear: A_R(h)+A_R(p)=A_R(h+p).
The shared-long control checks this without replacing either component. The
localized candidate replaces only q=g*p via Y=A_R(x)-A_R(q)+transport(q), where g
is an input-derived local taper. This is not measured-output gain correction,
waveform alignment or limiting. Gates and time maps still have finite support;
close or missed events and phase discontinuities remain possible.

## Fixed studies

```sh
for suite in detector synthetic mixtures corpus; do
  OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python research/linked_transients/assess.py \
    --suite "$suite" --heap "$BOILED_EGG_PHASE_HEAP_LIBRARY" \
    --events "$BOILED_EGG_LINKED_EVENTS_LIBRARY" --refs /absolute/20-reference-folder \
    --output "results/$suite" --workers 2
done
python research/linked_transients/audit_results.py --results results --output audited-results
```

Only `corpus` needs the original20 WAVs. Do not substitute other recordings and
call them the supplied corpus. The detector grid has576 comparisons (192 inputs,
three methods). Primary audio grids total1092 outputs:336 analytical,336 seeded
mixtures and420 natural renders, including seven declared modes. Shared-long is
an algebraic control, not a new independently superior audio algorithm. Two
old baseline outputs are additionally replayed for each natural cell and must
match exactly; those120 control renders are not new quality evidence.

Jobs are journaled under `<output>-journal`; journals bind input/code/binary
identity and per-cell values. A changed configuration needs a new output/journal.
The auditor checks expected key sets and every CSV value against the journal,
then reports wins AND losses with source-cluster descriptive intervals. Do not
reconfigure/replace libraries used by an in-progress study. Copy final measured
libraries before running the grids and retain their SHA256s.

Real-audio metrics reuse the previous study's source-relative RMS/flux/PSD/local
STFT definitions. New event metrics compare to a known shifted-position waveform
with unchanged local gate, in per-channel bounded/Voronoi scoring windows. Truth
is never passed to the detector or renderer. Detection uses one-to-one matching
within2ms. No fitted delay/DTW, raw gain normalization or native-zplane result.
The historical20-source corpus is not a pristine holdout. PROTOCOL.md defines
these hypotheses; final results include false positives and remaining coloration.
