#!/usr/bin/env python3
"""Explicit, verified constant-ratio external renders. No automatic fallback.

Examples:
  python eval/run_external.py --systems boiled_egg ffmpeg_rubberband --time 1.25 --pitch 5
Every run needs a new --output directory. Failed raw outputs/receipts are retained
but no legacy listening manifest is published if any requested cell failed.
"""
from __future__ import annotations
import argparse
import csv
import json
from pathlib import Path
import sys

from comparison_contract import Engine, Request, fingerprint, identity_unchanged, json_write, render_case, verify_case

ROOT = Path(__file__).resolve().parents[1]


def run(args: argparse.Namespace) -> dict:
    request = Request.from_semitones(args.time, args.pitch)
    if args.limit < 1 or len(args.systems) != len(set(args.systems)):
        raise ValueError("positive limit and unique explicit systems required")
    root = args.corpus.resolve(strict=True)
    sources = sorted(p.resolve() for p in root.rglob("*.wav"))[:args.limit]
    if not sources or len(sources) != len(set(sources)):
        raise ValueError("no unique WAV sources")
    if any(args.output.resolve() == p or args.output.resolve() in p.parents for p in sources):
        raise ValueError("output directory must not contain selected inputs")
    engines = [Engine(name, name, str(args.cli) if name == "boiled_egg" else args.ffmpeg) for name in args.systems]
    # Probe all requested systems before processing; unavailable means error, not fallback.
    probes = {e.name: e.probe() for e in engines}
    inputs = {str(p): fingerprint(p) for p in sources}
    args.output.mkdir(parents=True, exist_ok=False)
    json_write(args.output / "plan.json", dict(request=vars(request), sources=inputs, engines=probes,
        script_sha256=fingerprint(Path(__file__)), expected_cells=len(sources) * len(engines)))
    rows = []
    for i, source in enumerate(sources):
        for engine in engines:
            case = args.output / "systems" / f"{i:04d}_{engine.name}"
            receipt = render_case(engine, probes[engine.name], source, request, case)
            rows.append(dict(source=str(source), system=engine.name, case=str(case.relative_to(args.output)), status=receipt["status"],
                             receipt_sha256=fingerprint(case / "receipt.json")))
    stable = all(fingerprint(Path(p)) == h for p, h in inputs.items()) and all(identity_unchanged(p) for p in probes.values())
    passed = stable and all(row["status"] == "passed" for row in rows)
    if passed:
        for row in rows:
            verify_case(args.output / row["case"])
        with (args.output / "render_manifest.csv").open("x", newline="") as stream:
            writer = csv.writer(stream)
            writer.writerow(["source", "system", "render", "time_ratio", "pitch_st"])
            for row in rows:
                writer.writerow([row["source"], row["system"], str((args.output / row["case"] / "output.wav").resolve()), args.time, args.pitch])
    report = dict(schema="boiled-egg.external-run.v1", passed=passed, rows=rows, stable_inputs_and_binaries=stable,
                  plan_sha256=fingerprint(args.output / "plan.json"),
                  requested_cells=len(sources)*len(engines), actual_cells=len(rows), listening_status="not_listened",
                  note="Metadata contract, not temporal-alignment, perceptual or native-zplane qualification.")
    json_write(args.output / "summary.json", report)
    return report



def verify_run(root: Path) -> tuple[dict, list[dict]]:
    """Offline evidence check; no dependency on the original executable paths."""
    root = root.resolve(strict=True)
    report = json.loads((root / "summary.json").read_text())
    if report.get("schema") != "boiled-egg.external-run.v1" or not report.get("passed"):
        raise ValueError("failed/incomplete comparison")
    if fingerprint(root / "plan.json") != report["plan_sha256"]:
        raise ValueError("plan changed")
    plan = json.loads((root / "plan.json").read_text())
    expected = {(p, name) for p in plan["sources"] for name in plan["engines"]}
    rows = report["rows"]
    actual = [(row["source"], row["system"]) for row in rows]
    if len(actual) != len(set(actual)) or set(actual) != expected or len(actual) != plan["expected_cells"]:
        raise ValueError("duplicate/incomplete comparison grid")
    receipts = []
    for row in rows:
        directory = (root / row["case"]).resolve(strict=True)
        if root not in directory.parents or fingerprint(directory / "receipt.json") != row["receipt_sha256"]:
            raise ValueError("case path/hash mismatch")
        receipt = verify_case(directory)
        if (receipt["source_metadata"]["sha256"] != plan["sources"][row["source"]] or
            receipt["engine"] != row["system"] or receipt["request"] != plan["request"]):
            raise ValueError("case identity mismatch")
        receipts.append(receipt)
    return report, receipts


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", type=Path, default=ROOT / "data/external")
    parser.add_argument("--cli", type=Path, default=ROOT / "build/release/boiled_egg_cli")
    parser.add_argument("--ffmpeg", default="ffmpeg")
    parser.add_argument("--systems", nargs="+", choices=("boiled_egg", "ffmpeg_rubberband"), default=["boiled_egg"])
    parser.add_argument("--output", type=Path, default=ROOT / "results/external")
    parser.add_argument("--limit", type=int, default=8)
    parser.add_argument("--time", type=float, default=1.25)
    parser.add_argument("--pitch", type=float, default=5.0)
    try:
        report = run(parser.parse_args())
    except (OSError, ValueError, RuntimeError) as exc:
        print(exc, file=sys.stderr)
        return 2
    print(f'{sum(row["status"] == "passed" for row in report["rows"])}/{report["requested_cells"]} verified renders')
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
