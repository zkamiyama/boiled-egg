#!/usr/bin/env python3
"""Deterministic pitch/formant regression for the integrated C++ research backend."""
from __future__ import annotations

import argparse
import json
import math
import subprocess
import tempfile
from pathlib import Path

import numpy as np
import soundfile as sf
from scipy import signal

SR = 48000
NFFT = 2048
HOP = 256
SHIFTS = (-12, -7, -3, 3, 7, 12)


def resonator(f: float, bw: float):
    r = np.exp(-np.pi * bw / SR)
    th = 2 * np.pi * f / SR
    return np.array([1 - r]), np.array([1, -2 * r * np.cos(th), r * r])


def make_vowel(seconds: float = 2.0) -> np.ndarray:
    n = int(SR * seconds)
    x = np.zeros(n, np.float64)
    x[:: round(SR / 120)] = 1
    for f, bw in ((700, 90), (1220, 110), (2600, 150)):
        x = signal.lfilter(*resonator(f, bw), x)
    x = np.r_[x[0], np.diff(x)]
    return (0.5 * x / (np.max(np.abs(x)) + 1e-12)).astype(np.float32)


def make_harmonic(seconds: float = 2.0) -> np.ndarray:
    n = int(SR * seconds)
    t = np.arange(n) / SR
    x = sum(signal.sawtooth(2 * np.pi * f * t) for f in (110, 138.59, 164.81, 220)) / 4
    for f, bw in ((900, 120), (1800, 180), (3200, 250)):
        x = signal.lfilter(*resonator(f, bw), x)
    return (0.4 * x / (np.max(np.abs(x)) + 1e-12)).astype(np.float32)


def cep_env(x: np.ndarray, q: int = 40):
    f, _, z = signal.stft(
        x,
        fs=SR,
        window="hann",
        nperseg=NFFT,
        noverlap=NFFT - HOP,
        nfft=NFFT,
        boundary="zeros",
        padded=True,
    )
    logm = np.log(np.maximum(np.abs(z), 1e-7))
    full = np.concatenate([logm, logm[-2:0:-1]], axis=0)
    c = np.fft.ifft(full, axis=0).real
    keep = np.zeros_like(c)
    keep[: q + 1] = c[: q + 1]
    keep[-q:] = c[-q:]
    env = np.fft.fft(keep, axis=0).real[: len(f)]
    return f, env


def env_error(ref: np.ndarray, test: np.ndarray) -> float:
    f, a = cep_env(ref)
    _, b = cep_env(test)
    n = max(a.shape[1], b.shape[1])
    u = np.linspace(0, 1, n)

    def retime(x: np.ndarray) -> np.ndarray:
        old = np.linspace(0, 1, x.shape[1])
        return np.vstack([np.interp(u, old, row) for row in x])

    a = retime(a)
    b = retime(b)
    mask = (f >= 150) & (f <= 6000)
    a = a[mask] * 20 / np.log(10)
    b = b[mask] * 20 / np.log(10)
    # Ignore global gain; this metric is broad spectral-envelope shape only.
    b += np.median(a - b, axis=0, keepdims=True)
    return float(np.sqrt(np.mean((a - b) ** 2)))


def pitch_cents(x: np.ndarray, expected: float):
    x = x[len(x) // 4 : 3 * len(x) // 4]
    w = np.hanning(len(x))
    n = 1 << int(np.ceil(np.log2(len(x) * 8)))
    s = np.abs(np.fft.rfft(x * w, n))
    f = np.fft.rfftfreq(n, 1 / SR)
    valid = np.flatnonzero((f > 80) & (f < 2200))
    k = valid[np.argmax(s[valid])]
    a, b, c = s[k - 1 : k + 2]
    d = 0.5 * (a - c) / (a - 2 * b + c + 1e-30)
    hz = (k + d) * SR / n
    return float(1200 * np.log2(hz / expected)), float(hz)


def render(cli: Path, src: Path, dst: Path, st: int, formant: str) -> None:
    cmd = [
        str(cli),
        str(src),
        str(dst),
        "--time",
        "1",
        "--pitch-semitones",
        str(st),
        "--mode",
        "locked",
        "--formant",
        formant,
    ]
    p = subprocess.run(cmd, capture_output=True, text=True)
    if p.returncode:
        raise RuntimeError(p.stderr or p.stdout)


def read_audio(path: Path) -> np.ndarray:
    y, _ = sf.read(path, always_2d=True, dtype="float32")
    if not np.all(np.isfinite(y)):
        raise SystemExit(f"non-finite output: {path}")
    return y


def assert_per_shift_improvement(rows: dict, candidate: str, reference: str = "off", tolerance: float = 1.02) -> None:
    base = rows[reference]["errors_db"]
    test = rows[candidate]["errors_db"]
    for st, b, t in zip(SHIFTS, base, test):
        if t > tolerance * b:
            raise SystemExit(
                f"{candidate} formant regression at {st:+d} st: {t:.3f} dB vs {b:.3f} dB off"
            )


def assert_level_stability(
    rows: dict,
    candidate: str,
    reference: str = "off",
    max_abs_rms_delta_db: float = 0.25,
    max_peak_ratio: float = 1.40,
) -> dict[str, float]:
    rms_deltas = []
    peak_ratios = []
    for st, candidate_rms, reference_rms, candidate_peak, reference_peak in zip(
        SHIFTS,
        rows[candidate]["rms"],
        rows[reference]["rms"],
        rows[candidate]["peaks"],
        rows[reference]["peaks"],
    ):
        rms_delta_db = 20.0 * math.log10((candidate_rms + 1.0e-30) / (reference_rms + 1.0e-30))
        peak_ratio = candidate_peak / max(reference_peak, 1.0e-30)
        rms_deltas.append(rms_delta_db)
        peak_ratios.append(peak_ratio)
        if abs(rms_delta_db) > max_abs_rms_delta_db:
            raise SystemExit(
                f"{candidate} loudness regression at {st:+d} st: {rms_delta_db:+.3f} dB vs off"
            )
        if peak_ratio > max_peak_ratio:
            raise SystemExit(
                f"{candidate} peak regression at {st:+d} st: {peak_ratio:.3f}x vs off"
            )
    return {
        "max_abs_rms_delta_db": float(max(abs(value) for value in rms_deltas)),
        "max_peak_ratio": float(max(peak_ratios)),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cli", type=Path, required=True)
    ap.add_argument("--output", type=Path)
    args = ap.parse_args()
    out = args.output or Path(tempfile.mkdtemp(prefix="boiled-egg-formant-"))
    out.mkdir(parents=True, exist_ok=True)

    fixtures = {"vowel": make_vowel(), "harmonic": make_harmonic()}
    report: dict[str, object] = {
        "shifts_semitones": list(SHIFTS),
        "pitch": {},
        "formant": {},
        "level_stability": {},
        "stereo": {},
    }
    for name, x in fixtures.items():
        sf.write(out / f"{name}.wav", x, SR, subtype="FLOAT")

    sine = (0.3 * np.sin(2 * np.pi * 440 * np.arange(SR * 2) / SR)).astype(np.float32)
    sf.write(out / "sine.wav", sine, SR, subtype="FLOAT")
    for st in SHIFTS:
        dst = out / f"sine_{st}.wav"
        render(args.cli, out / "sine.wav", dst, st, "off")
        y = read_audio(dst)[:, 0]
        cents, hz = pitch_cents(y, 440 * 2 ** (st / 12))
        report["pitch"][str(st)] = {"hz": hz, "cents_error": cents, "frames": len(y)}
        if len(y) != len(sine) or abs(cents) > 0.1:
            raise SystemExit(f"pitch regression {st}: {cents:.3f} cents, {len(y)} frames")

    for name, ref in fixtures.items():
        rows: dict[str, object] = {}
        modes = ("off", "harmonic", "monophonic") if name == "vowel" else ("off", "harmonic")
        for mode in modes:
            errors = []
            peaks = []
            rms_values = []
            for st in SHIFTS:
                dst = out / f"{name}_{st}_{mode}.wav"
                render(args.cli, out / f"{name}.wav", dst, st, mode)
                y2 = read_audio(dst)
                y = y2[:, 0]
                if len(y) != len(ref):
                    raise SystemExit(f"duration regression {name} {st} {mode}: {len(y)} != {len(ref)}")
                errors.append(env_error(ref, y))
                peaks.append(float(np.max(np.abs(y))))
                rms_values.append(float(np.sqrt(np.mean(y.astype(np.float64) ** 2) + 1.0e-30)))
            rows[mode] = {
                "errors_db": errors,
                "mean_db": float(np.mean(errors)),
                "peaks": peaks,
                "peak_max": float(max(peaks)),
                "rms": rms_values,
            }
        report["formant"][name] = rows

    vowel = report["formant"]["vowel"]
    harmonic = report["formant"]["harmonic"]
    if vowel["harmonic"]["mean_db"] >= 0.90 * vowel["off"]["mean_db"]:
        raise SystemExit("harmonic formant path did not improve vowel envelope enough")
    if vowel["monophonic"]["mean_db"] >= 0.90 * vowel["off"]["mean_db"]:
        raise SystemExit("monophonic formant path did not improve vowel envelope enough")
    if harmonic["harmonic"]["mean_db"] >= 0.96 * harmonic["off"]["mean_db"]:
        raise SystemExit("harmonic formant path did not improve polyphonic envelope enough")
    assert_per_shift_improvement(vowel, "harmonic")
    assert_per_shift_improvement(vowel, "monophonic")
    assert_per_shift_improvement(harmonic, "harmonic")

    report["level_stability"] = {
        "vowel_harmonic": assert_level_stability(vowel, "harmonic"),
        "vowel_monophonic": assert_level_stability(vowel, "monophonic"),
        "polyphonic_harmonic": assert_level_stability(harmonic, "harmonic"),
    }

    # Linked-channel regression: formant processing must not distort a simple
    # inter-channel gain relationship when both channels carry the same source.
    stereo = np.column_stack([fixtures["harmonic"], 0.6 * fixtures["harmonic"]]).astype(np.float32)
    sf.write(out / "stereo.wav", stereo, SR, subtype="FLOAT")
    stereo_out = out / "stereo_7_harmonic.wav"
    render(args.cli, out / "stereo.wav", stereo_out, 7, "harmonic")
    y = read_audio(stereo_out)
    if len(y) != len(stereo):
        raise SystemExit("stereo duration regression")
    residual = y[:, 1] - 0.6 * y[:, 0]
    relation_error = float(np.sqrt(np.mean(residual.astype(np.float64) ** 2)))
    reference_rms = float(np.sqrt(np.mean(y[:, 0].astype(np.float64) ** 2)) + 1e-30)
    relative_error = relation_error / reference_rms
    report["stereo"] = {"gain_relation_rms_error": relation_error, "relative_error": relative_error}
    if relative_error > 1.0e-4:
        raise SystemExit(f"stereo linked-channel regression: relative error {relative_error:.3e}")

    (out / "report.json").write_text(json.dumps(report, indent=2, sort_keys=True))
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
