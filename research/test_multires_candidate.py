#!/usr/bin/env python3
"""Deterministic low-frequency safety gate for the realtime multi-resolution backend.

The short high-band analysis must never leak its known low-frequency failure
modes into the recombined output. This test renders low fundamentals through
exactly the public research CLI and checks target pitch, target/spur energy,
finite samples, peak sanity and exact duration over the primary +/-12 st range
plus the historically useful +7 st intermediate point.
"""
from __future__ import annotations

import argparse
import csv
import math
import subprocess
from pathlib import Path

import numpy as np
import soundfile as sf

SAMPLE_RATE = 48000
DURATION_SECONDS = 2.0
FUNDAMENTALS = (55.0, 80.0, 120.0, 220.0, 440.0)
SHIFTS = (-12, 7, 12)


def analyze(audio: np.ndarray, target_hz: float) -> tuple[float, float, float]:
    margin = SAMPLE_RATE // 2
    x = np.asarray(audio[margin:-margin], dtype=np.float64)
    n_fft = 1 << int(np.ceil(np.log2(len(x) * 8)))
    power = np.abs(np.fft.rfft(x * np.hanning(len(x)), n_fft)) ** 2
    frequencies = np.fft.rfftfreq(n_fft, 1.0 / SAMPLE_RATE)
    audible = (frequencies > 20.0) & (frequencies < SAMPLE_RATE / 2.0 - 100.0)
    audible_indices = np.flatnonzero(audible)
    peak_index = int(audible_indices[np.argmax(power[audible])])
    peak_hz = float(frequencies[peak_index])
    cents_error = float(1200.0 * np.log2(peak_hz / target_hz))

    target_band = (frequencies > target_hz - 3.0) & (frequencies < target_hz + 3.0)
    target_power = float(np.sum(power[target_band]))
    spur_power = max(float(np.sum(power[audible])) - target_power, 1.0e-30)
    target_to_spur_db = float(10.0 * np.log10((target_power + 1.0e-30) / spur_power))
    return peak_hz, cents_error, target_to_spur_db


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cli", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)

    frames = int(round(SAMPLE_RATE * DURATION_SECONDS))
    time = np.arange(frames, dtype=np.float64) / SAMPLE_RATE
    rows: list[dict[str, float | int]] = []

    for fundamental in FUNDAMENTALS:
        source = (0.35 * np.sin(2.0 * np.pi * fundamental * time)).astype(np.float32)
        source_path = args.output / f"input_{int(fundamental)}.wav"
        sf.write(source_path, source, SAMPLE_RATE, subtype="FLOAT")

        for shift in SHIFTS:
            destination = args.output / f"tone_{int(fundamental)}_{shift:+d}.wav"
            command = [
                str(args.cli),
                str(source_path),
                str(destination),
                "--time",
                "1",
                "--pitch-semitones",
                str(shift),
                "--formant",
                "harmonic",
            ]
            process = subprocess.run(command, capture_output=True, text=True)
            if process.returncode:
                raise SystemExit(process.stderr or process.stdout)

            rendered, rendered_rate = sf.read(destination, always_2d=True, dtype="float32")
            if rendered_rate != SAMPLE_RATE:
                raise SystemExit(f"sample-rate regression: {rendered_rate}")
            if len(rendered) != frames:
                raise SystemExit(
                    f"duration regression {fundamental:g} Hz {shift:+d} st: {len(rendered)} != {frames}"
                )
            if not np.all(np.isfinite(rendered)):
                raise SystemExit(f"non-finite output {fundamental:g} Hz {shift:+d} st")

            mono = rendered[:, 0]
            target_hz = fundamental * 2.0 ** (shift / 12.0)
            peak_hz, cents_error, target_to_spur_db = analyze(mono, target_hz)
            peak_abs = float(np.max(np.abs(mono)))
            rows.append(
                {
                    "fundamental_hz": fundamental,
                    "shift_semitones": shift,
                    "target_hz": target_hz,
                    "measured_peak_hz": peak_hz,
                    "cents_error": cents_error,
                    "target_to_spur_db": target_to_spur_db,
                    "peak_abs": peak_abs,
                    "frames": len(rendered),
                }
            )

    max_cents = max(abs(float(row["cents_error"])) for row in rows)
    min_spur = min(float(row["target_to_spur_db"]) for row in rows)
    max_peak = max(float(row["peak_abs"]) for row in rows)
    print("multi-resolution tonal max cents", max_cents)
    print("multi-resolution tonal min target/spur dB", min_spur)
    print("multi-resolution tonal max peak", max_peak)

    # Current validated checkpoint is about 2.16 cents and 23 dB. Keep a
    # little numerical/platform margin without allowing the short branch's
    # hundreds-of-cents low-frequency failures back into the recombined path.
    if max_cents > 3.0:
        raise SystemExit(f"low-frequency pitch safety regression: {max_cents:.3f} cents")
    if min_spur < 22.0:
        raise SystemExit(f"low-frequency spur safety regression: {min_spur:.3f} dB")
    if max_peak > 1.0:
        raise SystemExit(f"unexpected tonal peak growth: {max_peak:.3f}")

    metrics = args.output / "metrics.csv"
    with metrics.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


if __name__ == "__main__":
    main()
