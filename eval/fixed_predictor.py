#!/usr/bin/env python3
"""Audit and score already-produced, fixed predictions; NEVER train a model.

See docs/benchmarks/FIXED_PREDICTOR_PROTOCOL_2026-09-20.md. Uses the existing
TSM manifest and audio contract. A clean declared-inventory audit is not proof
of provenance completeness, model execution, or perceptual qualification.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path
import platform
import re
import sys
from typing import Any

import numpy as np
import scipy
from scipy import stats
import soundfile as sf

import comparison_contract as contract
import tsm_dataset as dataset

SCHEMA = "boiled-egg.fixed-predictor.v1"
STAGES = {"train", "validation", "selection", "calibration"}
ARTIFACTS = {"weights", "implementation", "preprocessing", "environment"}
IDENTITY = {"source_id", "engine_id", "reference_sha256"}
EVAL_FIELDS = IDENTITY | {
    "item_id", "category", "method", "ratio", "mos", "pitch_semitones", "formant",
    "reference_path", "processed_path", "processed_sha256", "reference_frames",
    "processed_frames", "reference_samplerate", "processed_samplerate",
    "reference_channels", "processed_channels",
}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def text(value: Any, field: str) -> str:
    require(isinstance(value, str) and bool(value.strip()), f"missing {field}")
    require(value == value.strip() and value.casefold() not in {"unknown", "unavailable"},
            f"unresolved {field}")
    return value


def number(value: Any, field: str) -> float:
    require(not isinstance(value, bool), f"boolean {field}")
    result = float(value)
    require(math.isfinite(result), f"nonfinite {field}")
    return result


def sha(value: Any) -> str:
    require(isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None,
            "expected lowercase SHA256")
    return value


def load_json(path: Path) -> dict:
    def unique(pairs):
        result = {}
        for key, value in pairs:
            require(key not in result, f"duplicate JSON key: {key}")
            result[key] = value
        return result

    def invalid(value):
        raise ValueError(f"nonfinite JSON constant: {value}")

    result = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=unique,
                        parse_constant=invalid)
    require(isinstance(result, dict), "expected JSON object")
    return result


def inside(root: Path, name: str) -> Path:
    require(not Path(text(name, "path")).is_absolute(), "absolute evidence path")
    result = (root / name).resolve(strict=True)
    require(root.resolve() in result.parents and result.is_file(), "evidence path escapes root")
    return result


def checked_file(root: Path, spec: dict, files: dict[str, str]) -> Path:
    path = inside(root, spec["path"])
    expected = sha(spec["sha256"])
    require(contract.fingerprint(path) == expected, f"changed file: {spec['path']}")
    files[str(path)] = expected
    return path


def table(path: Path, fields: set[str]) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as stream:
        reader = csv.reader(stream)
        header = next(reader, [])
        require(len(header) == len(set(header)), "duplicate CSV column")
        require(fields <= set(header), f"missing CSV columns: {sorted(fields - set(header))}")
        require(all(len(row) == len(header) for row in reader), "ragged CSV")
    rows = dataset.read_manifest(path)
    require(bool(rows), "empty CSV")
    return rows


def index(rows: list[dict[str, str]]) -> dict[str, dict[str, str]]:
    result = {}
    for row in rows:
        key = text(row["item_id"], "item_id")
        require(key not in result, f"duplicate item_id: {key}")
        result[key] = row
    return result


def audit_inventory(evaluation: list[dict], development: list[dict],
                    coverage: str, aliases_reviewed: bool) -> dict:
    require(bool(evaluation) and bool(development), "empty identity inventory")
    for row in evaluation + development:
        for field in IDENTITY:
            text(row[field], field)
        sha(row["reference_sha256"])
    for row in development:
        require(row["stage"] in STAGES, "unrecognized development stage")
    # A renamed byte-identical reference must not become a new bootstrap source.
    known_sources: dict[str, str] = {}
    for row in evaluation + development:
        digest = row["reference_sha256"]
        require(known_sources.setdefault(digest, row["source_id"]) == row["source_id"],
                "reference hash has inconsistent source_id aliases")
    overlaps = {}
    for field in sorted(IDENTITY):
        left = {row[field] for row in evaluation}
        overlaps[field] = sorted(left & {row[field] for row in development})
    stages = {stage: sum(row["stage"] == stage for row in development) for stage in sorted(STAGES)}
    reasons = [f"overlap:{field}" for field, values in overlaps.items() if values]
    if coverage != "complete":
        reasons.append("development inventory incomplete or unknown")
    if aliases_reviewed is not True:
        reasons.append("source/engine aliases not reviewed")
    return dict(passed=not reasons, reasons=reasons, overlaps=overlaps,
                development_stages=stages, evaluation_rows=len(evaluation),
                development_rows=len(development),
                claim="disjointness of declared inventory only; completeness is externally reviewed")


def metrics(truth: np.ndarray, prediction: np.ndarray) -> dict:
    require(len(truth) > 0 and truth.shape == prediction.shape, "empty/mismatched metric vectors")
    require(bool(np.isfinite(truth).all() and np.isfinite(prediction).all()), "nonfinite metric vector")
    with np.errstate(over="raise", invalid="raise"):
        error = prediction - truth
        result = dict(n=len(truth), rmse=float(np.sqrt(np.mean(error ** 2))),
                      mae=float(np.mean(np.abs(error))), bias=float(np.mean(error)))
    defined = len(truth) >= 3 and np.ptp(truth) != 0 and np.ptp(prediction) != 0
    result["pearson"] = float(stats.pearsonr(truth, prediction).statistic) if defined else None
    result["spearman"] = float(stats.spearmanr(truth, prediction).statistic) if defined else None
    for key in ("pearson", "spearman"):
        if result[key] is not None and not math.isfinite(result[key]):
            result[key] = None
    bins = np.digitize(prediction, [2.0, 3.0, 4.0])
    result["calibration_bins"] = [
        dict(bin=i, n=int(np.sum(bins == i)),
             mean_prediction=float(np.mean(prediction[bins == i])) if np.any(bins == i) else None,
             mean_label=float(np.mean(truth[bins == i])) if np.any(bins == i) else None)
        for i in range(4)]
    result["fixed_bin_bias_mae"] = float(sum(abs(np.sum(error[bins == i])) for i in range(4)) / len(error))
    result["predictions_outside_1_5"] = int(np.sum((prediction < 1) | (prediction > 5)))
    return result


def summarize(rows: list[dict]) -> dict:
    truth = np.array([row["label"] for row in rows], dtype=np.float64)
    prediction = np.array([row["prediction"] for row in rows], dtype=np.float64)
    result = metrics(truth, prediction)
    sources = sorted({row["source_id"] for row in rows})
    result["source_count"] = len(sources)
    result["source_cluster_ci95"] = None
    if len(sources) >= 3:
        groups = [np.array([i for i, row in enumerate(rows) if row["source_id"] == source])
                  for source in sources]
        rng = np.random.default_rng(20260920)
        samples = []
        for _ in range(1000):
            chosen = np.concatenate([groups[i] for i in rng.integers(len(groups), size=len(groups))])
            error = prediction[chosen] - truth[chosen]
            samples.append([np.sqrt(np.mean(error ** 2)), np.mean(np.abs(error)), np.mean(error)])
        limits = np.quantile(samples, [0.025, 0.975], axis=0)
        result["source_cluster_ci95"] = {key: limits[:, i].tolist()
                                         for i, key in enumerate(("rmse", "mae", "bias"))}
    result["ci_scope"] = "1000 source-cluster draws, seed20260920; conditional on observed engines; <3 sources: null"
    return result


def score(rows: list[dict]) -> dict:
    result = {"overall": summarize(rows)}
    for fields in (("source_id",), ("category",), ("engine_id",), ("category", "engine_id")):
        keys = sorted({tuple(row[field] for field in fields) for row in rows})
        result["by_" + "_".join(fields)] = [
            dict(group=dict(zip(fields, key)), metrics=summarize([
                row for row in rows if tuple(row[field] for field in fields) == key])) for key in keys]
    return result


def validate_scope(plan: dict) -> dict:
    scope = plan["scope"]
    require(scope["task"] == "tsm" and scope["formant"] == "off" and
            number(scope["pitch_semitones"], "pitch_semitones") == 0 and
            type(scope["channels"]) is int and scope["channels"] == 1,
            "unsupported scope: only mono TSM, pitch0, formant Off")
    rates = scope["sample_rates"]
    require(isinstance(rates, list) and bool(rates) and
            all(type(rate) is int and rate in (44100, 48000, 88200, 96000) for rate in rates) and
            len(rates) == len(set(rates)), "invalid declared rates")
    limits = scope["ratio_range"]
    require(len(limits) == 2 and 0 < number(limits[0], "ratio_min") <= number(limits[1], "ratio_max"),
            "invalid positive duration-ratio range")
    return scope


def validate_audio(root: Path, row: dict, scope: dict, files: dict[str, str]) -> None:
    infos = []
    for prefix in ("reference", "processed"):
        path = checked_file(root, dict(path=row[prefix + "_path"], sha256=row[prefix + "_sha256"]), files)
        info = contract.inspect_audio(path)
        require(info["sha256"] == row[prefix + "_sha256"], "audio changed during inspection")
        require(info["channels"] == 1 and info["sample_rate"] in scope["sample_rates"], "audio outside declared scope")
        require(info["rms"] > 1e-8, "silent/zero audio cannot qualify a prediction")
        for field, actual in (("frames", info["frames"]), ("channels", info["channels"]),
                              ("samplerate", info["sample_rate"])):
            require(number(row[prefix + "_" + field], field) == actual, "audio metadata mismatch")
        infos.append(info)
    require(infos[0]["sample_rate"] == infos[1]["sample_rate"], "input/output rate mismatch")
    ratio = number(row["ratio"], "duration ratio")
    require(scope["ratio_range"][0] <= ratio <= scope["ratio_range"][1], "ratio outside declared range")
    require(abs(infos[1]["frames"] / infos[0]["frames"] - ratio) <= 1e-8, "duration ratio mismatch")
    require(number(row["pitch_semitones"], "pitch_semitones") == 0 and row["formant"] == "off",
            "non-TSM operation; no pitch/formant qualification")


def evaluate(plan_path: Path, plan_sha256: str, predictions_path: Path,
             receipt_path: Path, output: Path) -> dict:
    """Write a complete receipt, including on validation failure. Never overwrite."""
    output.mkdir(parents=True, exist_ok=False)
    report: dict[str, Any] = dict(schema=SCHEMA, status="blocked", errors=[], scores=None,
                                 quality_selection=None, model_inference_performed=False,
                                 plan_sha256=plan_sha256)
    files: dict[str, str] = {}
    rows: list[dict] = []
    try:
        sha(plan_sha256)
        require(contract.fingerprint(plan_path) == plan_sha256, "plan hash mismatch")
        files[str(plan_path.resolve())] = plan_sha256
        plan = load_json(plan_path)
        require(plan["schema"] == SCHEMA, "unsupported plan schema")
        report["model_id"] = text(plan["model_id"], "model_id")
        report["label_origin"] = plan["label_origin"]
        require(plan["label_origin"] in {"measured_mos", "synthetic_fixture"}, "unknown label origin")
        scope = validate_scope(plan)
        report["scope"] = scope
        require(type(plan["expected_rows"]) is int and plan["expected_rows"] > 0, "invalid expected row count")
        root = plan_path.resolve().parent
        require(isinstance(plan["artifacts"], dict) and set(plan["artifacts"]) >= ARTIFACTS,
                "missing/invalid frozen model artifacts")
        artifacts = {}
        for role, spec in sorted(plan["artifacts"].items()):
            checked_file(root, spec, files)
            artifacts[role] = spec["sha256"]
        report["artifacts"] = artifacts
        manifest = table(checked_file(root, plan["evaluation"], files), EVAL_FIELDS)
        development = table(checked_file(root, plan["development"], files), IDENTITY | {"stage"})
        report["raw_evaluation"] = manifest
        report["raw_development"] = development
        entries = index(manifest)
        require(len(entries) == plan["expected_rows"], "incomplete evaluation grid")
        report["audit"] = audit_inventory(manifest, development, plan["development_coverage"], plan["aliases_reviewed"])
        predictions_hash = contract.fingerprint(predictions_path)
        receipt_hash = contract.fingerprint(receipt_path)
        files[str(predictions_path.resolve())] = predictions_hash
        files[str(receipt_path.resolve())] = receipt_hash
        predictions = table(predictions_path, {"item_id", "prediction", "status"})
        report["raw_predictions"] = predictions
        predicted = index(predictions)
        receipt = load_json(receipt_path)
        require(receipt["plan_sha256"] == plan_sha256 and receipt["predictions_sha256"] == predictions_hash and
                receipt["artifacts"] == artifacts, "prediction receipt identity mismatch")
        require(set(predicted) == set(entries), "missing/extra prediction IDs")
        require(report["audit"]["passed"], "independence audit blocked: " + "; ".join(report["audit"]["reasons"]))
        for key, row in sorted(entries.items()):
            text(row["category"], "category")
            text(row["method"], "method")
            require(predicted[key]["status"] == "ok", f"failed prediction: {key}")
            label = number(row["mos"], "measured/synthetic label")
            require(1 <= label <= 5, "label outside 1..5")
            prediction = number(predicted[key]["prediction"], "prediction")
            validate_audio(root, row, scope, files)
            rows.append(dict(item_id=key, source_id=row["source_id"], engine_id=row["engine_id"],
                             category=row["category"], ratio=row["ratio"], label=label,
                             prediction=prediction, error=prediction-label))
        scores = score(rows)
        # Catch accidental replacement during inspection/scoring, not just before it.
        require(all(contract.fingerprint(Path(path)) == digest for path, digest in files.items()),
                "evidence changed during evaluation")
        dataset.write_csv(output / "rows.csv", rows)
        report["rows_sha256"] = contract.fingerprint(output / "rows.csv")
        report["scores"] = scores
        report["status"] = "audited"
    except (ValueError, KeyError, TypeError, OSError, RuntimeError, OverflowError, FloatingPointError) as exc:
        report["errors"].append(f"{type(exc).__name__}: {exc}")
    report["verified_files"] = files
    report["scorer"] = dict(python=platform.python_version(), numpy=np.__version__, scipy=scipy.__version__,
                             soundfile=sf.__version__, executable_sha256=contract.fingerprint(Path(sys.executable)),
                             sources={Path(module.__file__).name: contract.fingerprint(Path(module.__file__))
                                      for module in (sys.modules[__name__], contract, dataset)})
    contract.json_write(output / "report.json", report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--plan-sha256", required=True)
    parser.add_argument("--predictions", type=Path, required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        report = evaluate(args.plan, args.plan_sha256, args.predictions, args.receipt, args.output)
    except OSError as exc:
        print(json.dumps(dict(status="blocked", errors=[str(exc)], quality_selection=None)))
        return 2
    print(json.dumps(dict(status=report["status"], errors=report["errors"], quality_selection=None), allow_nan=False))
    return 0 if report["status"] == "audited" else 2


if __name__ == "__main__":
    raise SystemExit(main())
