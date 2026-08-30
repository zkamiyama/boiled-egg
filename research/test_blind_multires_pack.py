#!/usr/bin/env python3
from __future__ import annotations

import csv
import subprocess
import sys
import tempfile
import unittest
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

            manifest = list(csv.DictReader((output / "manifest.csv").open(encoding="utf-8")))
            answer_key = list(csv.DictReader((output / "answer_key.csv").open(encoding="utf-8")))
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


if __name__ == "__main__":
    unittest.main()
