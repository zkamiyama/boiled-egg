#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import math
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np
import soundfile as sf

from research import report_peak_outliers as audit


class PeakOutlierTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="boiled-egg-peak-test-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.args = argparse.Namespace(ref_dir=self.root / "refs", output=self.root / "report",
                                       peak_threshold=1.0, peak_ratio_threshold=1.10)
        self.args.ref_dir.mkdir()
        sources = (("fixture_voice", "voice", "50", -12), ("fixture_solo", "solo", "200", 12),
                   ("fixture_poly", "polyphonic", "118.92", 3), ("fixture_mix", "mix", "149.83", 7),
                   ("fixture_stress", "mix", "394", 23.7))
        self.reference = np.array([[0.5, 0.25], [-0.5, -0.25], [0.25, 0.125], [-0.25, -0.125]])
        self.rows = {name: [] for name in ("general", "transient", "multires")}
        for stem, category, percent, semitones in sources:
            common = dict(stem=stem, category=category, percent=percent, semitones=semitones)
            standard = dict(env_rmse_db=2.0, onset_corr=0.8, peak=999, rms=999)
            self.rows["general"].extend([{**common, **standard, "system": system}
                                         for system in ("harmonic", "elastique")])
            self.rows["transient"].append({**common, **standard, "system": "harmonic"})
            self.rows["multires"].append({**common, "env": 1.9, "onset": 0.9})
            if semitones > 12:
                continue  # Stress audio deliberately absent; never mixed into target evaluation.
            sf.write(self.args.ref_dir / f"{stem}.wav", self.reference, 16000, subtype="FLOAT")
            for name in self.rows:
                directory = self.root / name / stem / f"{percent}_per"
                directory.mkdir(parents=True)
                filenames = ("boiled_harmonic.wav", "elastique.wav") if name == "general" else (
                    "multires_harmonic.wav" if name == "multires" else "boiled_harmonic.wav",
                )
                for filename in filenames:
                    sf.write(directory / filename, self.reference * (2.4 if name == "multires" else 1.0),
                             16000, subtype="FLOAT")
        for name, rows in self.rows.items():
            path = self.root / f"{name}.csv"
            audit.write_csv(path, rows, tuple(rows[0]))
            setattr(self.args, f"{name}_metrics", path)
            setattr(self.args, f"{name}_renders", self.root / name)

    def command(self) -> list[str]:
        command = [sys.executable, str(Path(audit.__file__).resolve())]
        for name in ("general", "transient", "multires"):
            for kind in ("metrics", "renders"):
                command += [f"--{name}-{kind}", str(getattr(self.args, f"{name}_{kind}"))]
        return command + ["--ref-dir", str(self.args.ref_dir), "--output", str(self.args.output)]

    def test_raw_peak_ratios_rms_and_crest(self) -> None:
        rows, excluded, summary = audit.build_report(self.args)
        self.assertEqual((len(rows), len(excluded), summary["conditions"]), (16, 1, 4))
        self.assertEqual(summary["flagged_rows"], 4)
        for row in rows:
            self.assertEqual(row["artifact_assessment"], "not_listened")
            self.assertEqual(row["duration_error_frames"], 0)
            self.assertEqual(row["channels"], 2)
            self.assertEqual(row["audio_sha256"], audit.sha256(Path(row["audio_path"])))
            self.assertLessEqual(abs(row["semitones"]), 12)
            if row["system"] == "multires_harmonic":
                self.assertAlmostEqual(row["peak"], 1.2, places=6)
                self.assertAlmostEqual(row["peak_ratio_vs_transient"], 2.4, places=6)
                self.assertAlmostEqual(row["rms_delta_vs_transient_db"], 20 * math.log10(2.4), places=6)
                self.assertAlmostEqual(row["crest_delta_vs_transient_db"], 0.0, places=6)
                self.assertEqual((row["env_rmse_db"], row["onset_corr"]), (1.9, 0.9))

    def test_coverage_does_not_invent_missing_pitch_cells(self) -> None:
        _, _, summary = audit.build_report(self.args)
        voice = summary["coverage"]["voice"]
        self.assertEqual(voice["actual_semitones"], [-12.0])
        self.assertEqual(voice["missing_requested_semitones"], [-7, -3, 3, 7, 12])
        self.assertEqual(summary["excluded_stress_conditions"], 1)
        self.assertNotIn(23.7, summary["coverage"]["mix"]["actual_semitones"])
        json.dumps(summary, allow_nan=False)

    def test_silence_has_no_invented_floor_or_infinity(self) -> None:
        stats = audit.amplitude(np.zeros((8, 2)), 48000)
        self.assertEqual(stats["peak"], 0.0)
        for field in ("peak_dbfs", "rms_dbfs", "crest_db"):
            self.assertIsNone(stats[field])
        self.assertIsNone(audit.ratio(1.0, 0.0))
        self.assertIsNone(audit.db(0.0))
        directory = self.args.transient_renders / "fixture_voice" / "50_per"
        sf.write(directory / "boiled_harmonic.wav", np.zeros_like(self.reference), 16000, subtype="FLOAT")
        rows, _, _ = audit.build_report(self.args)
        row = next(row for row in rows if row["stem"] == "fixture_voice" and row["system"] == "multires_harmonic")
        self.assertIsNone(row["peak_ratio_vs_transient"])
        self.assertIn("nonzero_output_vs_silent_transient", row["review_flags"])

    def test_invalid_thresholds_rejected(self) -> None:
        for field in ("peak_threshold", "peak_ratio_threshold"):
            for value in (0, -1, float("nan"), float("inf")):
                args = argparse.Namespace(**vars(self.args))
                setattr(args, field, value)
                with self.subTest(field=field, value=value), self.assertRaisesRegex(ValueError, "thresholds"):
                    audit.build_report(args)

    def test_cli_exports_reports_without_touching_audio(self) -> None:
        before = {path: audit.sha256(path) for path in self.root.rglob("*.wav")}
        result = subprocess.run(self.command(), text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual({p.name for p in self.args.output.iterdir()},
                         {"all_conditions.csv", "peak_outliers.csv", "excluded_stress.csv", "summary.json"})
        with (self.args.output / "peak_outliers.csv").open(newline="") as stream:
            outliers = list(csv.DictReader(stream))
        self.assertEqual(len(outliers), 4)
        self.assertEqual({row["system"] for row in outliers}, {"multires_harmonic"})
        self.assertEqual(before, {path: audit.sha256(path) for path in self.root.rglob("*.wav")})
        second = subprocess.run(self.command(), text=True, capture_output=True)
        self.assertNotEqual(second.returncode, 0)
        self.assertIn("absent or empty", second.stderr)

    def test_bad_audio_leaves_no_report(self) -> None:
        path = self.args.multires_renders / "fixture_voice" / "50_per" / "multires_harmonic.wav"
        sf.write(path, self.reference, 48000, subtype="FLOAT")
        result = subprocess.run(self.command(), text=True, capture_output=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("sample-rate mismatch", result.stderr)
        self.assertFalse(self.args.output.exists())


if __name__ == "__main__":
    unittest.main()
