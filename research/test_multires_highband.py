#!/usr/bin/env python3
"""High-band steady-tone modulation gate for the realtime multi-resolution path."""
from __future__ import annotations

import argparse
import csv
import math
import subprocess
from pathlib import Path

import numpy as np
import soundfile as sf
from scipy.signal import hilbert

SAMPLE_RATE = 48000
DURATION_SECONDS = 4.0
FUNDAMENTALS = (5500.0, 6500.0, 7500.0, 8500.0, 9500.0, 10500.0)
SHIFTS = (7, 12)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cli", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)

    frame_count = int(round(SAMPLE_RATE * DURATION_SECONDS))
    time = np.arange(frame_count, dtype=np.float64) / SAMPLE_RATE
    rows: list[dict[str, float | int]] = []

    for fundamental in FUNDAMENTALS:
        source = (0.2 * np.sin(2.0 * np.pi * fundamental * time)).astype(np.float32)
        source_path = args.output / f"input_{int(fundamental)}.wav"
        sf.write(source_path, source, SAMPLE_RATE, subtype="FLOAT")

        for shift in SHIFTS:
            target = fundamental * 2.0 ** (shift / 12.0)
            if target > 22000.0:
                continue
            destination = args.output / f"tone_{int(fundamental)}_{shift:+d}.wav"
            process = subprocess.run(
                [
                    str(args.cli),
                    str(source_path),
                    str(destination),
                    "--time",
                    "1",
                    "--pitch-semitones",
                    str(shift),
                    "--formant",
                    "off",
                    "--block",
                    "256",
                ],
                capture_output=True,
                text=True,
            )
            if process.returncode:
                raise SystemExit(process.stderr or process.stdout)

            rendered, sample_rate = sf.read(destination, always_2d=True, dtype="float32")
            if sample_rate != SAMPLE_RATE or len(rendered) != frame_count:
                raise SystemExit(f"duration/sample-rate regression at {fundamental:g} Hz / {shift:+d} st")
            if not np.all(np.isfinite(rendered)):
                raise SystemExit(f"non-finite high-band output at {fundamental:g} Hz / {shift:+d} st")

            # Ignore startup/end transients and estimate modulation of the
            # steady sinusoid through its analytic-signal amplitude envelope.
            margin = SAMPLE_RATE // 2
            mono = rendered[margin:-margin, 0].astype(np.float64)
            envelope = np.abs(hilbert(mono))
            p1, p5, p95, p99 = np.percentile(envelope, (1.0, 5.0, 95.0, 99.0))
            ripple95 = float(20.0 * math.log10(max(p95, 1.0e-30) / max(p5, 1.0e-30)))
            ripple99 = float(20.0 * math.log10(max(p99, 1.0e-30) / max(p1, 1.0e-30)))
            peak = float(np.max(np.abs(mono)))
            rows.append(
                {
                    "fundamental_hz": fundamental,
                    "shift_semitones": shift,
                    "target_hz": target,
                    "ripple95_db": ripple95,
                    "ripple99_db": ripple99,
                    "peak_abs": peak,
                }
            )

    worst95 = max(float(row["ripple95_db"]) for row in rows)
    worst99 = max(float(row["ripple99_db"]) for row in rows)
    worst_peak = max(float(row["peak_abs"]) for row in rows)
    print("multi-resolution high-band worst 95% ripple dB", worst95)
    print("multi-resolution high-band worst 99% ripple dB", worst99)
    print("multi-resolution high-band worst peak", worst_peak)

    # Current 512/hop-192 candidate is ~0.144 dB worst-case at the 95%
    # percentile range on this fixture. Leave platform margin but fail audible
    # frame-rate amplitude pumping regressions early.
    if worst95 > 0.25:
        raise SystemExit(f"high-band amplitude-modulation regression: {worst95:.3f} dB")
    if worst_peak > 0.25:
        raise SystemExit(f"unexpected high-band peak growth: {worst_peak:.3f}")

    with (args.output / "metrics.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


if __name__ == "__main__":
    main()
