#!/usr/bin/env python3
from __future__ import annotations
import argparse
from pathlib import Path
from tsm_dataset import benchmark_boiled_egg, benchmark_manifest, render_boiled_egg, summarize

ROOT = Path(__file__).resolve().parents[1]

def main() -> None:
    parser = argparse.ArgumentParser(description="Run the TSM dataset benchmark")
    parser.add_argument("--dataset", type=Path, default=ROOT / "data" / "external" / "tsm_test")
    parser.add_argument("--cli", type=Path, default=ROOT / "build" / "release" / "boiled_egg_cli")
    parser.add_argument("--results", type=Path, default=ROOT / "results" / "tsm_test")
    parser.add_argument("--skip-baselines", action="store_true")
    parser.add_argument("--skip-render", action="store_true")
    args = parser.parse_args()

    dataset = args.dataset.resolve()
    results = args.results.resolve()
    results.mkdir(parents=True, exist_ok=True)
    baseline_metrics = results / "baseline_metrics.csv"
    render_manifest = dataset / "boiled_egg" / "manifest.csv"
    boiled_metrics = results / "boiled_egg_metrics.csv"

    if not args.skip_baselines or not baseline_metrics.exists():
        benchmark_manifest(dataset, dataset / "manifest.csv", baseline_metrics)
    if not args.skip_render or not render_manifest.exists():
        render_boiled_egg(dataset, dataset / "manifest.csv", args.cli.resolve(), dataset / "boiled_egg" / "audio", render_manifest)
    benchmark_boiled_egg(dataset, render_manifest, boiled_metrics)
    summarize(baseline_metrics, boiled_metrics, results)
    print(results / "SUMMARY.md")

if __name__ == "__main__":
    main()
