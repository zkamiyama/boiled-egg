# Exact-output WSOLA cost checks

These controls belong to Issues62/63/65. They do not install a new SDK mode.
The original root CTest counts remain unchanged.

```sh
cmake -S quality/wsola_cost -B /tmp/cost-check -DCMAKE_BUILD_TYPE=Release
cmake --build /tmp/cost-check --parallel 2
python quality/audition/run_ctest.py --build /tmp/cost-check --expected 1
```

Build/install the SDK, then configure `quality/streaming_budget` with its prefix
to execute the seven public-C-ABI tests (2650 trials in total). An empty/rounded
zero output is not an acoustic success. The comparator preserves old failures.

The Linux benchmark requires a workspace containing `repo/`,
`build-original/libboiled_egg.so`, `build-before/libboiled_egg.so`,
`build-after/libboiled_egg.so`, and `client/wsola_cost_bench`.
Use the same compiler/options for all SDK builds. `before` is the supplied
correctness-fixed source841b1b18, not a commit promised to exist on remote main.
The source archive and before/after diff retained with the evidence identify it.
Original main7b256119 remains a separate faulty reference.

Compile the client using this directory's CMake project with
`WSOLA_COST_BUILD_BENCH=ON` and an installed package prefix. Copy only the one
built executable to `client/`; the benchmark runs that same binary with each SDK
via process-local `LD_LIBRARY_PATH`. Run only in a trusted local test workspace.
It is not a general loader for untrusted libraries. Registration and measurement:

```sh
python quality/wsola_cost/run_bench.py prepare --root /absolute/workspace --output /tmp/cost-plan
# Record the printed plan SHA before execution. Do not reuse another machine's SHA.
python quality/wsola_cost/run_bench.py run --plan /tmp/cost-plan/plan.json --sha256 RECORDED_SHA --output /tmp/cost-results
```

The script pins one child at a time, rotates version order, preserves failures,
and stores raw PCM and per-call timings. Do not compile or run other heavy tests
concurrently. Wall/thread CPU/native API service times have different scopes;
see the results document. The package and path layout is explicit, not auto-mode
selection. Performance cannot be inferred from a green correctness-only CI.

The before/after source and binary hash, compiler/runtime, full56-setting grid,
all3repetitions and raw failures must accompany performance claims. A revised
binary needs a new plan and rerun. Global compiler fast-math, changed filters,
clip/normalization, output trimming and hidden mode changes are not permitted
ways to satisfy this same-PCM optimization contract.
