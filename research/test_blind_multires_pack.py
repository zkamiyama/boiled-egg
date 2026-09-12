#!/usr/bin/env python3
from __future__ import annotations

import csv
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from research import make_blind_multires_pack as pack
from pathlib import Path

import numpy as np
import soundfile as sf

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "research" / "make_blind_multires_pack.py"
SAMPLE_RATE = 16000


class BlindMultiresPackTest(unittest.TestCase):
    def test_balanced_four_way_pack(self) -> None:
        with tempfile.TemporaryDirectory(prefix="boiled-egg-blind-test-") as td:
            root = Path(td)
            references = root / "references"
            general_renders = root / "general"
            transient_renders = root / "transient"
            multires_renders = root / "multires"
            output = root / "pack"
            for directory in (references, general_renders, transient_renders, multires_renders):
                directory.mkdir(parents=True)

            categories = {
                "Female_4": "voice",
                "Ocarina_02": "solo",
                "Rock_4": "mix",
                "Woodwinds_4": "polyphonic",
            }
            percent = "150.0"
            general_rows: list[dict[str, object]] = []
            transient_rows: list[dict[str, object]] = []
            multires_rows: list[dict[str, object]] = []

            time = np.arange(SAMPLE_RATE, dtype=np.float64) / SAMPLE_RATE
            for index, (stem, category) in enumerate(categories.items()):
                reference = (0.15 * np.sin(2.0 * np.pi * (220.0 + 40.0 * index) * time)).astype(np.float32)
                sf.write(references / f"{stem}.wav", reference, SAMPLE_RATE, subtype="FLOAT")

                general_dir = general_renders / stem / f"{percent}_per"
                transient_dir = transient_renders / stem / f"{percent}_per"
                multires_dir = multires_renders / stem / f"{percent}_per"
                for directory in (general_dir, transient_dir, multires_dir):
                    directory.mkdir(parents=True)

                systems = {
                    general_dir / "elastique.wav": reference * 0.90,
                    general_dir / "boiled_harmonic.wav": reference * 1.05,
                    transient_dir / "boiled_harmonic.wav": reference * 0.97,
                    multires_dir / "multires_harmonic.wav": reference * 1.02,
                }
                for path, audio in systems.items():
                    sf.write(path, audio, SAMPLE_RATE, subtype="FLOAT")

                common = {
                    "stem": stem,
                    "category": category,
                    "percent": percent,
                    "pitch_ratio": 1.5,
                    "semitones": 7.01955,
                }
                general_rows.extend(
                    [
                        {**common, "system": "elastique", "env_rmse_db": 2.0 + index, "onset_corr": 0.70},
                        {**common, "system": "harmonic", "env_rmse_db": 1.5 + index, "onset_corr": 0.75},
                    ]
                )
                transient_rows.append(
                    {**common, "system": "harmonic", "env_rmse_db": 1.6 + index, "onset_corr": 0.82}
                )
                multires_rows.append(
                    {
                        "stem": stem,
                        "category": category,
                        "percent": percent,
                        "pitch_ratio": 1.5,
                        "semitones": 7.01955,
                        "env": 1.55 + index,
                        "onset": 0.85,
                    }
                )

            def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
                with path.open("w", newline="", encoding="utf-8") as stream:
                    writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
                    writer.writeheader()
                    writer.writerows(rows)

            general_metrics = root / "general.csv"
            transient_metrics = root / "transient.csv"
            multires_metrics = root / "multires.csv"
            write_csv(general_metrics, general_rows)
            write_csv(transient_metrics, transient_rows)
            write_csv(multires_metrics, multires_rows)

            process = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--general-metrics",
                    str(general_metrics),
                    "--general-renders",
                    str(general_renders),
                    "--transient-metrics",
                    str(transient_metrics),
                    "--transient-renders",
                    str(transient_renders),
                    "--multires-metrics",
                    str(multires_metrics),
                    "--multires-renders",
                    str(multires_renders),
                    "--ref-dir",
                    str(references),
                    "--output",
                    str(output),
                    "--per-category",
                    "1",
                    "--seed",
                    "12345",
                ],
                capture_output=True,
                text=True,
            )
            self.assertEqual(process.returncode, 0, msg=process.stderr or process.stdout)

            manifest = pack.load_rows(output / "manifest.csv")
            answer_key = pack.load_rows(output / "answer_key.csv")
            self.assertEqual(len(manifest), 4)
            self.assertEqual(len(answer_key), 4)
            self.assertEqual({row["category"] for row in manifest}, set(categories.values()))

            expected_systems = {
                "derived_elastique",
                "general_harmonic",
                "transient_harmonic",
                "multires_harmonic",
            }
            for row in answer_key:
                self.assertEqual({row[label] for label in ("A", "B", "C", "D")}, expected_systems)
            for row in manifest:
                trial = int(row["trial"])
                trial_dir = output / f"trial_{trial:02d}"
                self.assertTrue((trial_dir / "reference.wav").is_file())
                for label in ("A", "B", "C", "D"):
                    self.assertTrue((trial_dir / f"{label}.wav").is_file())

            html = (output / "index.html").read_text(encoding="utf-8")
            self.assertIn("Overall", html)
            self.assertIn("Attack/clarity", html)
            self.assertIn("Tonal/formant", html)
            self.assertTrue((output / "README.txt").is_file())


class BlindPackValidationTest(unittest.TestCase):
    @staticmethod
    def rows(semitones: float = 7.0) -> tuple[list[dict], list[dict], list[dict]]:
        common = dict(stem="Tone", percent="150.0", category="solo", semitones=str(semitones))
        standard = dict(env_rmse_db="2.0", onset_corr="0.8")
        return (
            [{**common, **standard, "system": name} for name in ("harmonic", "elastique")],
            [{**common, **standard, "system": "harmonic"}],
            [{**common, "env": "1.9", "onset": "0.9"}],
        )

    def test_numeric_condition_identity(self) -> None:
        general, transient, multires = self.rows()
        transient[0]["percent"] = "150"
        multires[0]["percent"] = "1.5e2"
        selected = pack.select_conditions(general, transient, multires, 1)
        self.assertEqual(selected[0]["percent"], "150.0")

    def test_duplicate_metrics_rejected(self) -> None:
        general, transient, multires = self.rows()
        general.append({**general[0], "percent": "150"})
        with self.assertRaisesRegex(ValueError, "duplicate"):
            pack.select_conditions(general, transient, multires, 1)
        with self.assertRaisesRegex(ValueError, "duplicate"):
            pack.multires_map([multires[0], multires[0]])

    def test_invalid_condition_keys(self) -> None:
        for stem, percent in [("../Tone", "150"), ("..", "150"), ("a\\b", "150"),
                              ("Tone", "NaN"), ("Tone", "Infinity"), ("Tone", "0"),
                              ("Tone", "-1"), ("Tone", "bad")]:
            with self.subTest(stem=stem, percent=percent), self.assertRaises(ValueError):
                pack.condition_key(stem, percent)

    def test_nearby_render_is_never_substituted(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            expected = root / "Tone" / "150_per"
            expected.mkdir(parents=True)
            self.assertEqual(pack.source_dir(root, "Tone", "150.0"), expected)
            for percent in ("151", "149.999999999"):
                with self.subTest(percent=percent), self.assertRaises(FileNotFoundError):
                    pack.source_dir(root, "Tone", percent)

    def test_ambiguous_render_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            for name in ("150_per", "150.0_per"):
                (root / "Tone" / name).mkdir(parents=True)
            with self.assertRaisesRegex(ValueError, "ambiguous"):
                pack.source_dir(root, "Tone", "150.0")

    def test_unrelated_render_entries_ignored(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "Tone" / "bad_per").mkdir(parents=True)
            (root / "Tone" / "150_per").write_text("not a directory")
            with self.assertRaises(FileNotFoundError):
                pack.source_dir(root, "Tone", "150")

    def test_missing_pairs_rejected(self) -> None:
        general, transient, multires = self.rows()
        with self.assertRaisesRegex(ValueError, "missing paired"):
            pack.select_conditions(general, transient, [], 1)

    def test_mismatched_metadata_rejected(self) -> None:
        for field, value in (("category", "voice"), ("semitones", "3"), ("semitones", "nan")):
            general, transient, multires = self.rows()
            transient[0][field] = value
            with self.subTest(field=field, value=value), self.assertRaisesRegex(ValueError, "metadata"):
                pack.select_conditions(general, transient, multires, 1)

    def test_nonfinite_metrics_rejected(self) -> None:
        for field, value in (("env", "nan"), ("onset", "inf")):
            general, transient, multires = self.rows()
            multires[0][field] = value
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, "non-finite"):
                pack.select_conditions(general, transient, multires, 1)
        with self.assertRaisesRegex(ValueError, "non-finite pitch"):
            pack.select_conditions(*self.rows(float("nan")), 1)

    def test_target_boundaries_and_empty_selection(self) -> None:
        for semitones in (-12.0, 12.0):
            self.assertEqual(len(pack.select_conditions(*self.rows(semitones), 1)), 1)
        for semitones in (-12.001, 12.001, 23.7):
            with self.subTest(semitones=semitones), self.assertRaisesRegex(ValueError, "no complete"):
                pack.select_conditions(*self.rows(semitones), 1)
        with self.assertRaisesRegex(ValueError, "no complete"):
            pack.select_conditions([], [], [], 1)
        for count in (0, -1):
            with self.assertRaisesRegex(ValueError, "positive"):
                pack.select_conditions(*self.rows(), count)

    def test_audio_metadata_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            sf.write(root / "ref.wav", np.zeros((160, 1)), 16000, subtype="FLOAT")
            for frames, channels, rate, message in (
                (160, 1, 48000, "sample-rate"), (159, 1, 16000, "duration/channel"),
                (160, 2, 16000, "duration/channel"),
            ):
                sf.write(root / "out.wav", np.zeros((frames, channels)), rate, subtype="FLOAT")
                with self.subTest(frames=frames, channels=channels, rate=rate):
                    with self.assertRaisesRegex(ValueError, message):
                        pack.load_trial(root / "ref.wav", {"test": root / "out.wav"})

    def test_empty_and_nonfinite_audio_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "bad.wav"
            for audio in (np.empty((0, 1)), np.array([[np.nan]]), np.array([[np.inf]])):
                sf.write(path, audio, 16000, subtype="FLOAT")
                with self.subTest(audio=audio), self.assertRaisesRegex(ValueError, "empty or non-finite"):
                    pack.load_audio(path)

    def test_level_matching_preserves_headroom_and_linkage(self) -> None:
        mono = np.sin(np.arange(16000) * 0.1)
        reference = np.column_stack((mono, mono * 0.5))
        matched_ref, systems = pack.level_match(reference, {"up": reference * 1.5, "down": reference * 0.75})
        for audio in (matched_ref, *systems.values()):
            self.assertLessEqual(np.max(np.abs(audio)), 0.950001)
            np.testing.assert_allclose(audio[:, 1], audio[:, 0] * 0.5)
            self.assertAlmostEqual(pack.rms(audio), pack.rms(matched_ref), places=12)

    def test_cli_preflight_writes_nothing_on_invalid_trial(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            args = [str(SCRIPT)]
            for name, rows in zip(("general", "transient", "multires"), self.rows()):
                path = root / f"{name}.csv"
                with path.open("w", newline="", encoding="utf-8") as stream:
                    writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
                    writer.writeheader()
                    writer.writerows(rows)
                args += [f"--{name}-metrics", str(path), f"--{name}-renders", str(root / name)]
                directory = root / name / "Tone" / "150_per"
                directory.mkdir(parents=True)
                files = ("elastique.wav", "boiled_harmonic.wav") if name == "general" else (
                    "multires_harmonic.wav" if name == "multires" else "boiled_harmonic.wav",
                )
                for filename in files:
                    sf.write(directory / filename, np.zeros((160, 1)),
                             48000 if name == "multires" else 16000, subtype="FLOAT")
            sf.write(root / "Tone.wav", np.zeros((160, 1)), 16000, subtype="FLOAT")
            output = root / "pack"
            args += ["--ref-dir", str(root), "--output", str(output)]
            with mock.patch.object(sys, "argv", args):
                with self.assertRaisesRegex(ValueError, "sample-rate"):
                    pack.main()
            self.assertFalse(output.exists())
            output.mkdir()
            marker = output / "keep.txt"
            marker.write_text("existing results")
            with mock.patch.object(sys, "argv", args):
                with self.assertRaisesRegex(ValueError, "absent or empty"):
                    pack.main()
            self.assertEqual(marker.read_text(), "existing results")


if __name__ == "__main__":
    unittest.main()
