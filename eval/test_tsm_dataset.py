#!/usr/bin/env python3
from __future__ import annotations

import csv
import math
import tempfile
import unittest
import zipfile
from pathlib import Path
import sys

import numpy as np
import soundfile as sf

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "eval"))

from tsm_dataset import _best_shift, _corr, compute_metrics, import_dataset, read_manifest


class CorrelationPurityTest(unittest.TestCase):
    def test_float64_inputs_unchanged(self) -> None:
        a = np.array([1.0, 4.0, 2.0, 8.0, 5.0])
        b = np.array([3.0, 1.0, 5.0, 7.0, 2.0])
        before_a, before_b = a.copy(), b.copy()
        self.assertAlmostEqual(_corr(a, b), np.corrcoef(a, b)[0, 1])
        np.testing.assert_array_equal(a, before_a)
        np.testing.assert_array_equal(b, before_b)

    def test_overlapping_strided_views_unchanged(self) -> None:
        base = np.array([2., 9., 1., 3., 7., 8., 4., 6., 5., 0., 11.])
        before = base.copy()
        a, b = base[::2], base[2::2]
        expected = np.corrcoef(a[:len(b)], b)[0, 1]
        self.assertAlmostEqual(_corr(a, b), expected)
        np.testing.assert_array_equal(base, before)

    def test_read_only_arrays(self) -> None:
        a = np.array([1., 3., 2., 8., 5.])
        b = -a.copy()
        a.flags.writeable = False
        b.flags.writeable = False
        self.assertAlmostEqual(_corr(a, b), -1.0)
        self.assertAlmostEqual(_corr(a, a), 1.0)

    def test_shift_search_is_repeatable_without_mutation(self) -> None:
        a = np.array([0., 1., 0., 3., 2., 0., 5., 0., 1., 0.])
        b = np.r_[0., 0., a[:-2]]
        before_a, before_b = a.copy(), b.copy()
        self.assertEqual(_best_shift(a, b, 3), 2)
        self.assertEqual(_best_shift(a, b, 3), 2)
        np.testing.assert_array_equal(a, before_a)
        np.testing.assert_array_equal(b, before_b)

    def test_existing_short_and_constant_conventions(self) -> None:
        self.assertEqual(_corr(np.zeros(2), np.zeros(2)), 0.)
        self.assertEqual(_corr(np.ones(5), np.ones(5)), 1.)
        self.assertEqual(_corr(np.ones(5), np.arange(5.)), 0.)


class TsmDatasetToolsTest(unittest.TestCase):
    def test_import_and_identity_metrics(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            ref_dir = root / "reference"
            test_dir = root / "processed"
            ref_dir.mkdir()
            for method in ("Elastique", "FuzzyTSM"):
                (test_dir / method).mkdir(parents=True)

            sr = 16000
            t = np.arange(sr, dtype=np.float64) / sr
            references = {
                "Tone_A.wav": (0.2 * np.sin(2 * np.pi * 440.0 * t)).astype(np.float32),
                "Tone_B.wav": (0.2 * np.sin(2 * np.pi * 660.0 * t)).astype(np.float32),
            }
            score_rows = []
            for name, audio in references.items():
                sf.write(ref_dir / name, audio, sr, subtype="FLOAT")
                stem = Path(name).stem
                for method in ("Elastique", "FuzzyTSM"):
                    for ratio in (0.75, 1.25):
                        size = round(len(audio) * ratio)
                        warped = np.interp(
                            np.linspace(0.0, 1.0, size, endpoint=False),
                            np.linspace(0.0, 1.0, len(audio), endpoint=False),
                            audio,
                        ).astype(np.float32)
                        filename = f"{stem}_{ratio:.2f}_{method}.wav"
                        sf.write(test_dir / method / filename, warped, sr, subtype="FLOAT")
                        score_rows.append({"File": filename, "MeanOS": "4.25"})

            def make_zip(source: Path, destination: Path) -> None:
                with zipfile.ZipFile(destination, "w") as zf:
                    for path in source.rglob("*"):
                        if path.is_file():
                            zf.write(path, path.relative_to(source.parent))

            ref_zip = root / "ref.zip"
            test_zip = root / "test.zip"
            make_zip(ref_dir, ref_zip)
            make_zip(test_dir, test_zip)
            score_csv = root / "scores.csv"
            with score_csv.open("w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=["File", "MeanOS"])
                writer.writeheader()
                writer.writerows(score_rows)

            destination = root / "dataset"
            paths = import_dataset(ref_zip, test_zip, score_csv, destination, expected_references=2, expected_processed=8)
            manifest = read_manifest(paths.manifest_csv)
            self.assertEqual(len(manifest), 8)
            self.assertTrue(all(math.isclose(float(r["mos"]), 4.25) for r in manifest))
            self.assertEqual({r["method"] for r in manifest}, {"Elastique", "FuzzyTSM"})

            metrics = compute_metrics(ref_dir / "Tone_A.wav", ref_dir / "Tone_A.wav")
            self.assertLess(metrics["log_spectral_distance_db"], 1.0e-6)
            self.assertGreater(metrics["onset_corr"], 0.999)
            self.assertGreater(metrics["chroma_corr"], 0.999)


if __name__ == "__main__":
    unittest.main()
