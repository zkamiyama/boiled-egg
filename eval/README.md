# Evaluation harness

Synthetic correctness, anti-alias, stereo, automation, realtime deadline and blind external comparison tools live here. Third-party audio stays under gitignored `data/external/`.

Primary commands:

```bash
python3 eval/generate_corpus.py
python3 eval/run_synthetic.py --cli build/release/boiled_egg_cli
python3 eval/run_bench.py --bench build/release/boiled_egg_bench
```
