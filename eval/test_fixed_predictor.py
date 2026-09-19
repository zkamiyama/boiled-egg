"""Generated controls only: no real weights, TSM engine, or measured MOS.

Run unit tests with unittest. Run this file with --evidence DIR to retain the
complete 48/96k fixture grid, every rejection, hashes, and analytical comparison.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

import numpy as np
import soundfile as sf

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fixed_predictor as f


def digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


class Fixture:
    def __init__(self, root: Path):
        self.root = root
        root.mkdir(parents=True)
        self.rows, self.predictions = [], []
        for source in range(3):
            for rate in (48000, 96000):
                ref = f"source{source}-{rate}.wav"
                size = rate // 25
                sf.write(root / ref, .1 * np.sin(2*np.pi*(223+source*37)*np.arange(size)/rate),
                         rate, subtype="FLOAT")
                for engine in range(2):
                    for ratio in (.8, 1.25):
                        key = f"s{source}-r{rate}-e{engine}-t{ratio}"
                        proc = key + ".wav"
                        frames = round(size * ratio)
                        # Analytically generated duration; NOT any actual TSM engine.
                        sf.write(root / proc, .1 * np.sin(2*np.pi*(223+source*37)*np.arange(frames)/rate),
                                 rate, subtype="FLOAT")
                        label = 1 + source + engine*.5 + (ratio == 1.25)*.25 + (rate == 96000)*.125
                        self.rows.append(dict(item_id=key, source_id=f"recording{source}",
                            engine_id=f"synthetic-engine{engine}", method=f"synthetic{engine}",
                            category=f"synthetic-tone{source % 2}", ratio=ratio, mos=label,
                            pitch_semitones=0, formant="off", reference_path=ref, processed_path=proc,
                            reference_sha256=f.contract.fingerprint(root/ref),
                            processed_sha256=f.contract.fingerprint(root/proc),
                            reference_frames=size, processed_frames=frames,
                            reference_samplerate=rate, processed_samplerate=rate,
                            reference_channels=1, processed_channels=1))
                        self.predictions.append(dict(item_id=key, prediction=label, status="ok"))
        self.development = [dict(source_id=f"development-{stage}", engine_id=f"seen-{stage}",
                                reference_sha256=digest(stage), stage=stage) for stage in sorted(f.STAGES)]
        self.plan = dict(schema=f.SCHEMA, model_id="synthetic-analytical-controls-NOT-OMOQ",
                         label_origin="synthetic_fixture", expected_rows=len(self.rows),
                         development_coverage="complete", aliases_reviewed=True,
                         scope=dict(task="tsm", pitch_semitones=0, formant="off", channels=1,
                                    sample_rates=[48000, 96000], ratio_range=[.8, 1.25]), artifacts={})
        for role in sorted(f.ARTIFACTS):
            path = root / (role + ".txt")
            path.write_text(f"synthetic {role} placeholder; no external model executed\n")
            self.plan["artifacts"][role] = dict(path=path.name, sha256=f.contract.fingerprint(path))
        self.seal()

    def seal(self):
        for name, rows in (("evaluation", self.rows), ("development", self.development),
                           ("predictions", self.predictions)):
            f.dataset.write_csv(self.root/(name+".csv"), rows)
        for name in ("evaluation", "development"):
            self.plan[name] = dict(path=name+".csv", sha256=f.contract.fingerprint(self.root/(name+".csv")))
        f.contract.json_write(self.root/"plan.json", self.plan)
        self.plan_sha = f.contract.fingerprint(self.root/"plan.json")
        self.receipt = dict(plan_sha256=self.plan_sha,
                           predictions_sha256=f.contract.fingerprint(self.root/"predictions.csv"),
                           artifacts={key: value["sha256"] for key, value in self.plan["artifacts"].items()})
        f.contract.json_write(self.root/"receipt.json", self.receipt)

    def run(self, output="result"):
        return f.evaluate(self.root/"plan.json", self.plan_sha, self.root/"predictions.csv",
                          self.root/"receipt.json", self.root/output)

    def command(self, output):
        return [sys.executable, str(Path(f.__file__)), "--plan", str(self.root/"plan.json"),
                "--plan-sha256", self.plan_sha, "--predictions", str(self.root/"predictions.csv"),
                "--receipt", str(self.root/"receipt.json"), "--output", str(self.root/output)]


# Every mutation is a deliberately invalid synthetic control, not a new real-data split.
NEGATIVES = {
    "source_overlap": "overlap:source_id",
    "engine_overlap": "overlap:engine_id",
    "selection_overlap": "overlap:source_id",
    "calibration_overlap": "overlap:source_id",
    "renamed_reference": "inconsistent source_id",
    "unknown_inventory": "incomplete or unknown",
    "unreviewed_aliases": "aliases not reviewed",
    "empty_development": "missing CSV columns",
    "duplicate_prediction": "duplicate item_id",
    "missing_prediction": "missing/extra prediction IDs",
    "extra_prediction": "missing/extra prediction IDs",
    "failed_prediction": "failed prediction",
    "nonfinite_prediction": "nonfinite prediction",
    "overflow_prediction": "overflow",
    "missing_label": "could not convert",
    "nonfinite_label": "nonfinite measured/synthetic label",
    "changed_weights": "changed file",
    "changed_preprocessing": "changed file",
    "changed_audio": "changed file",
    "changed_plan": "plan hash mismatch",
    "receipt_mismatch": "receipt identity mismatch",
    "wrong_grid": "incomplete evaluation grid",
    "zero_output": "silent/zero audio",
    "both_zero": "silent/zero audio",
    "nonfinite_audio": "nonfinite audio",
    "stereo": "outside declared scope",
    "pitch": "non-TSM operation",
    "formant": "non-TSM operation",
    "freeze": "outside declared range",
    "duration": "duration ratio mismatch",
    "metadata": "audio metadata mismatch",
    "undeclared_rate": "outside declared scope",
    "duplicate_csv_column": "duplicate CSV column",
    "ragged_csv": "ragged CSV",
    "duplicate_json_key": "duplicate JSON key",
    "escape_path": "escapes root",
    "malformed_artifacts": "invalid frozen model artifacts",
}


def mutate(x: Fixture, name: str):
    row = x.rows[0]
    if name in {"source_overlap", "selection_overlap", "calibration_overlap"}:
        stage = {"source_overlap":"train", "selection_overlap":"selection",
                 "calibration_overlap":"calibration"}[name]
        next(r for r in x.development if r["stage"] == stage)["source_id"] = row["source_id"]
    elif name == "engine_overlap": x.development[0]["engine_id"] = row["engine_id"]
    elif name == "renamed_reference": x.development[0]["reference_sha256"] = row["reference_sha256"]
    elif name == "unknown_inventory": x.plan["development_coverage"] = "unknown"
    elif name == "unreviewed_aliases": x.plan["aliases_reviewed"] = False
    elif name == "empty_development": x.development.clear()
    elif name == "duplicate_prediction": x.predictions.append(copy.deepcopy(x.predictions[0]))
    elif name == "missing_prediction": x.predictions.pop()
    elif name == "extra_prediction": x.predictions.append(dict(item_id="extra", prediction=3, status="ok"))
    elif name == "failed_prediction": x.predictions[0]["status"] = "failed"
    elif name == "nonfinite_prediction": x.predictions[0]["prediction"] = "nan"
    elif name == "overflow_prediction": x.predictions[0]["prediction"] = "1e308"
    elif name == "missing_label": row["mos"] = ""
    elif name == "nonfinite_label": row["mos"] = "inf"
    elif name == "wrong_grid": x.plan["expected_rows"] += 1
    elif name in {"zero_output", "both_zero", "nonfinite_audio", "stereo"}:
        prefixes = ("reference", "processed") if name == "both_zero" else ("processed",)
        for prefix in prefixes:
            size = row[prefix+"_frames"]
            values = np.zeros(size) if name != "stereo" else np.ones((size, 2))*.1
            if name == "nonfinite_audio": values[0] = np.nan
            sf.write(x.root/row[prefix+"_path"], values, row[prefix+"_samplerate"], subtype="FLOAT")
            new_hash = f.contract.fingerprint(x.root/row[prefix+"_path"])
            for sibling in x.rows:
                if sibling[prefix+"_path"] == row[prefix+"_path"]:
                    sibling[prefix+"_sha256"] = new_hash
    elif name == "pitch": row["pitch_semitones"] = 7
    elif name == "formant": row["formant"] = "harmonic"
    elif name == "freeze": row["ratio"] = 0
    elif name == "duration": row["ratio"] = 1
    elif name == "metadata": row["processed_frames"] += 1
    elif name == "undeclared_rate": x.plan["scope"]["sample_rates"] = [96000]
    elif name == "escape_path":
        outside = x.root.parent / (x.root.name+"-outside.txt")
        outside.write_text("outside")
        x.plan["artifacts"]["weights"] = dict(path="../"+outside.name, sha256=f.contract.fingerprint(outside))
    x.seal()
    if name in {"changed_weights", "changed_preprocessing"}:
        (x.root/(name.removeprefix("changed_")+".txt")).write_text("changed")
    elif name == "changed_audio": (x.root/row["processed_path"]).write_bytes(b"changed")
    elif name == "changed_plan": (x.root/"plan.json").write_text("{}")
    elif name == "receipt_mismatch":
        x.receipt["predictions_sha256"] = "0"*64
        f.contract.json_write(x.root/"receipt.json", x.receipt)
    elif name in {"duplicate_csv_column", "ragged_csv"}:
        path = x.root/"predictions.csv"
        path.write_text("item_id,prediction,status,status\na,3,ok,ok\n" if name == "duplicate_csv_column"
                        else "item_id,prediction,status\na,3\n")
    elif name == "malformed_artifacts":
        x.plan["artifacts"] = list(x.plan["artifacts"])
        f.contract.json_write(x.root/"plan.json", x.plan)
        x.plan_sha = f.contract.fingerprint(x.root/"plan.json")
        x.receipt["plan_sha256"] = x.plan_sha
        f.contract.json_write(x.root/"receipt.json", x.receipt)
    elif name == "duplicate_json_key":
        (x.root/"receipt.json").write_text('{"plan_sha256":"a","plan_sha256":"b"}')


class MetricTests(unittest.TestCase):
    def test_analytical_controls(self):
        y = np.arange(1., 6.)
        for name, p, rmse, bias, corr in (("perfect", y, 0, 0, 1),
                ("bias", y+1, 1, 1, 1), ("reversed", 6-y, math.sqrt(8), 0, -1),
                ("constant", np.full(5, 3.), math.sqrt(2), 0, None)):
            with self.subTest(name=name):
                result = f.metrics(y, p)
                self.assertAlmostEqual(result["rmse"], rmse, places=12)
                self.assertAlmostEqual(result["bias"], bias, places=12)
                for metric in ("pearson", "spearman"):
                    if corr is None: self.assertIsNone(result[metric])
                    else: self.assertAlmostEqual(result[metric], corr, places=12)
        self.assertEqual(f.metrics(y, y+1)["predictions_outside_1_5"], 1)
        self.assertEqual(f.metrics(y, y+1)["fixed_bin_bias_mae"], 1)

    def test_tied_ranks(self):
        y = np.array([1.,1.,2.,3.])
        self.assertAlmostEqual(f.metrics(y, -y)["spearman"], -1, places=12)

    def test_too_few_and_constant_labels(self):
        for y in (np.array([1., 2.]), np.ones(5)):
            self.assertIsNone(f.metrics(y, np.arange(len(y)))["pearson"])

    def test_invalid_metric_vectors(self):
        for y, p in (([], []), ([1], [1,2]), ([1,2,3], [1,2,np.nan])):
            with self.assertRaises(ValueError): f.metrics(np.array(y), np.array(p))

    def test_bootstrap_repeatable_and_source_grouped(self):
        rows = [dict(source_id=str(s), label=3, prediction=3+s) for s in range(3) for _ in range(s+1)]
        first = f.summarize(rows)
        self.assertEqual(first, f.summarize(rows))
        self.assertEqual(first["source_count"], 3)
        self.assertIsNotNone(first["source_cluster_ci95"])
        self.assertIsNone(f.summarize(rows[:3])["source_cluster_ci95"])


class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
    def tearDown(self): self.temp.cleanup()

    def test_complete_grid_and_subgroups(self):
        x = Fixture(self.root/"valid")
        report = x.run()
        self.assertEqual(report["status"], "audited", report["errors"])
        self.assertEqual(len(report["raw_evaluation"]), 24)
        self.assertEqual(report["scores"]["overall"]["rmse"], 0)
        self.assertEqual(report["scores"]["overall"]["source_count"], 3)
        self.assertEqual(len(report["scores"]["by_category_engine_id"]), 4)
        self.assertEqual(report["label_origin"], "synthetic_fixture")
        self.assertFalse(report["model_inference_performed"])
        self.assertIsNone(report["quality_selection"])
        self.assertEqual(f.load_json(x.root/"result/report.json"), report)

    def test_all_negative_controls(self):
        for name, reason in NEGATIVES.items():
            with self.subTest(name=name):
                x = Fixture(self.root/name)
                mutate(x, name)
                report = x.run()
                self.assertEqual(report["status"], "blocked")
                self.assertIn(reason, " ".join(report["errors"]))
                self.assertIsNone(report["scores"])
                self.assertIsNone(report["quality_selection"])
                self.assertFalse((x.root/"result/rows.csv").exists())

    def test_cli_success_failure_and_no_overwrite(self):
        x = Fixture(self.root/"cli")
        for output, expected in (("cli-ok", 0), ("cli-ok", 2)):
            result = subprocess.run(x.command(output), capture_output=True, text=True)
            self.assertEqual(result.returncode, expected, result.stderr)
        before = f.contract.fingerprint(x.root/"cli-ok/report.json")
        mutate(x, "missing_prediction")
        result = subprocess.run(x.command("cli-bad"), capture_output=True, text=True)
        self.assertEqual(result.returncode, 2)
        self.assertEqual(f.contract.fingerprint(x.root/"cli-ok/report.json"), before)

    def test_changed_during_scoring_is_blocked(self):
        x = Fixture(self.root/"race")
        real_score = f.score
        def changed(rows):
            result = real_score(rows)
            (x.root/"weights.txt").write_text("replaced after initial verification")
            return result
        with mock.patch.object(f, "score", side_effect=changed): report = x.run()
        self.assertEqual(report["status"], "blocked")
        self.assertIn("during evaluation", report["errors"][0])

    def test_empty_unknown_and_invalid_schema(self):
        for key, value in (("expected_rows", 0), ("schema", "bad"), ("label_origin", "predicted_mos")):
            x = Fixture(self.root/key); x.plan[key] = value; x.seal()
            self.assertEqual(x.run()["status"], "blocked")


def evidence(root: Path):
    """Retain every synthetic comparison and CLI rejection; throw on mismatch."""
    root.mkdir(parents=True, exist_ok=False)
    summary = dict(label_origin="synthetic_fixture", external_model_inference=False,
                   quality_selection=None, grid_rows_per_case=24, positive=[], negative=[])
    for name in ("perfect", "bias", "reversed", "constant"):
        x = Fixture(root/name)
        y = np.array([r["mos"] for r in x.rows])
        p = {"perfect": y, "bias": y+1, "reversed": 6-y, "constant": np.full(len(y), 3.)}[name]
        for row, value in zip(x.predictions, p): row["prediction"] = float(value)
        x.seal()
        process = subprocess.run(x.command("result"), capture_output=True, text=True)
        (x.root/"cli.txt").write_text(process.stdout+process.stderr)
        report = f.load_json(x.root/"result/report.json")
        f.require(process.returncode == 0 and report["status"] == "audited", name)
        actual = report["scores"]["overall"]
        expected = float(np.sqrt(np.mean((p-y)**2)))
        f.require(abs(actual["rmse"]-expected) <= 1e-12, "analytical RMSE mismatch")
        summary["positive"].append(dict(case=name, exit=process.returncode, rmse=actual["rmse"],
                                        pearson=actual["pearson"], spearman=actual["spearman"],
                                        expected_rmse=expected, report_sha256=f.contract.fingerprint(x.root/"result/report.json")))
    for name, reason in NEGATIVES.items():
        x = Fixture(root/name); mutate(x, name)
        process = subprocess.run(x.command("result"), capture_output=True, text=True)
        (x.root/"cli.txt").write_text(process.stdout+process.stderr)
        report = f.load_json(x.root/"result/report.json")
        f.require(process.returncode == 2 and report["status"] == "blocked" and report["scores"] is None
                  and reason in " ".join(report["errors"]), f"unblocked control: {name}")
        summary["negative"].append(dict(case=name, exit=process.returncode, expected_reason=reason,
                                        errors=report["errors"], report_sha256=f.contract.fingerprint(x.root/"result/report.json")))
    summary["source_sha256"] = {Path(m.__file__).name: f.contract.fingerprint(Path(m.__file__)) for m in (f, sys.modules[__name__])}
    f.contract.json_write(root/"summary.json", summary)
    hashes = {str(p.relative_to(root)): f.contract.fingerprint(p) for p in sorted(root.rglob("*")) if p.is_file()}
    f.contract.json_write(root/"hashes.json", hashes)
    print(json.dumps(dict(positive=len(summary["positive"]), negative=len(summary["negative"]),
                         rows_per_case=24, quality_selection=None)))


if __name__ == "__main__":
    if "--evidence" in sys.argv:
        parser = argparse.ArgumentParser(description=__doc__)
        parser.add_argument("--evidence", type=Path, required=True)
        evidence(parser.parse_args().evidence)
    else:
        unittest.main()
