#!/usr/bin/env python3
"""Full-band tonal safety gate for the validated Transient quality profile."""
from __future__ import annotations

import argparse
import csv
import math
import subprocess
import tempfile
from pathlib import Path

import numpy as np
import soundfile as sf

SR = 48000
SECONDS = 3
FUNDAMENTALS = (55.0, 80.0, 120.0, 220.0, 440.0)
SHIFTS = (-12, 7, 12)
CANDIDATE_FFT = 1024
CANDIDATE_HOP = 256
MAX_ABS_CENTS = 5.0
MIN_TONE_TO_SPUR_DB = 20.0


def render(
    cli: Path,
    source: Path,
    destination: Path,
    semitones: int,
    fft_size: int,
    use_transient_profile: bool,
) -> None:
    command = [
        str(cli), str(source), str(destination),
        "--time", "1",
        "--pitch-semitones", str(semitones),
        "--formant", "off",
    ]
    if use_transient_profile:
        # Exercise the user-facing preset rather than reproducing its raw FFT
        # values here. The C API test separately checks the preset mapping.
        command += ["--profile", "transient"]
    else:
        command += ["--mode", "locked", "--fft", str(fft_size), "--hop", str(fft_size // 8)]
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode:
        raise RuntimeError(result.stderr or result.stdout)


def analyze(audio: np.ndarray, target_hz: float) -> tuple[float, float, float]:
    margin = SR // 2
    x = np.asarray(audio[margin:-margin], dtype=np.float64)
    n_fft = 1 << int(np.ceil(np.log2(len(x) * 4)))
    power = np.abs(np.fft.rfft(x * np.hanning(len(x)), n_fft)) ** 2
    frequencies = np.fft.rfftfreq(n_fft, 1.0 / SR)

    peak_hz = float(frequencies[int(np.argmax(power))])
    cents = float(1200.0 * math.log2(peak_hz / target_hz))

    target_band = (frequencies > target_hz - 3.0) & (frequencies < target_hz + 3.0)
    audible = (frequencies > 20.0) & (frequencies < SR / 2.0 - 100.0)
    target_power = float(np.sum(power[target_band]))
    total_power = float(np.sum(power[audible]))
    spur_power = max(total_power - target_power, 1.0e-30)
    tone_to_spur_db = float(10.0 * np.log10((target_power + 1.0e-30) / spur_power))
    return peak_hz, cents, tone_to_spur_db


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cli", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument(
        "--diagnostic-fft",
        type=int,
        action="append",
        default=[],
        help="Additional raw FFT sizes to measure without gating (for example 512 or 2048).",
    )
    args = parser.parse_args()
    root = args.output or Path(tempfile.mkdtemp(prefix="boiled-egg-transient-tonal-"))
    root.mkdir(parents=True, exist_ok=True)

    fft_sizes = [CANDIDATE_FFT] + [x for x in args.diagnostic_fft if x != CANDIDATE_FFT]
    rows: list[dict[str, float | int | str]] = []

    for f0 in FUNDAMENTALS:
        t = np.arange(SR * SECONDS, dtype=np.float64) / SR
        source_audio = (0.3 * np.sin(2.0 * np.pi * f0 * t)).astype(np.float32)
        source = root / f"input_{f0:g}.wav"
        sf.write(source, source_audio, SR, subtype="FLOAT")

        for fft_size in fft_sizes:
            candidate = fft_size == CANDIDATE_FFT
            for semitones in SHIFTS:
                destination = root / f"output_{f0:g}_{fft_size}_{semitones:+d}.wav"
                render(args.cli, source, destination, semitones, fft_size, candidate)
                output, sample_rate = sf.read(destination, dtype="float32")
                if sample_rate != SR or len(output) != len(source_audio):
                    raise SystemExit(
                        f"duration/sample-rate regression: f0={f0:g}, fft={fft_size}, shift={semitones:+d}"
                    )
                if not np.all(np.isfinite(output)):
                    raise SystemExit(f"non-finite output: {destination}")

                target_hz = f0 * 2.0 ** (semitones / 12.0)
                peak_hz, cents, tone_to_spur_db = analyze(output, target_hz)
                rows.append(
                    {
                        "f0": f0,
                        "selection": "profile:transient" if candidate else "raw-window-diagnostic",
                        "fft": fft_size,
                        "hop": CANDIDATE_HOP if candidate else fft_size // 8,
                        "shift_semitones": semitones,
                        "target_hz": target_hz,
                        "peak_hz": peak_hz,
                        "cents_error": cents,
                        "tone_to_spur_db": tone_to_spur_db,
                    }
                )

                if candidate:
                    if abs(cents) >= MAX_ABS_CENTS:
                        raise SystemExit(
                            f"Transient tonal pitch regression: f0={f0:g}, shift={semitones:+d}, "
                            f"error={cents:.3f} cents"
                        )
                    if tone_to_spur_db <= MIN_TONE_TO_SPUR_DB:
                        raise SystemExit(
                            f"Transient tonal spur regression: f0={f0:g}, shift={semitones:+d}, "
                            f"tone/spur={tone_to_spur_db:.2f} dB"
                        )

    fields = list(rows[0])
    with (root / "metrics.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)

    candidate_rows = [row for row in rows if row["selection"] == "profile:transient"]
    print(
        f"Transient profile ({CANDIDATE_FFT}/{CANDIDATE_HOP}) tonal gate: max_abs_cents=",
        max(abs(float(row["cents_error"])) for row in candidate_rows),
        "min_tone_to_spur_db=",
        min(float(row["tone_to_spur_db"]) for row in candidate_rows),
    )
    for fft_size in fft_sizes:
        group = [row for row in rows if row["fft"] == fft_size]
        print(
            f"fft={fft_size}: max_abs_cents={max(abs(float(row['cents_error'])) for row in group):.3f}, "
            f"min_tone_to_spur_db={min(float(row['tone_to_spur_db']) for row in group):.2f}"
        )


if __name__ == "__main__":
    main()
