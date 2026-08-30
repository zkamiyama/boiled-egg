#!/usr/bin/env python3
from pathlib import Path
import argparse
import csv
import subprocess

import numpy as np
import soundfile as sf

ROOT = Path(__file__).resolve().parents[1]


def peak_hz(x, sr, lo=100, hi=4000):
    x = x[len(x) // 4 : 3 * len(x) // 4]
    X = np.abs(np.fft.rfft(x * np.hanning(len(x))))
    f = np.fft.rfftfreq(len(x), 1 / sr)
    mask = (f >= lo) & (f <= hi)
    return float(f[mask][np.argmax(X[mask])])


def corr(a, b):
    n = min(len(a), len(b))
    a = a[:n] - np.mean(a[:n])
    b = b[:n] - np.mean(b[:n])
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-12))


def middle_rms(x, sr):
    trim = min(sr // 2, max(0, len(x) // 4))
    y = x[trim : len(x) - trim] if len(x) > 2 * trim else x
    return float(np.sqrt(np.mean(np.square(y))) if len(y) else 0.0)


def transient_width_ms(y, sr, interval_in_frames, time_ratio):
    """Median 90%-energy width around isolated clicks. Diagnostic only, not a pass/fail metric."""
    expected_interval = max(1, int(round(interval_in_frames * time_ratio)))
    radius = int(round(0.040 * sr))
    widths = []
    for center in range(expected_interval, len(y) - expected_interval, expected_interval):
        lo = max(0, center - radius)
        hi = min(len(y), center + radius + 1)
        seg = np.square(y[lo:hi].astype(np.float64))
        if not np.any(seg > 0):
            continue
        peak = int(np.argmax(seg))
        # Grow symmetrically from the local peak until 90% of local transient energy is enclosed.
        total = float(np.sum(seg))
        acc = float(seg[peak])
        left = right = peak
        while acc < 0.90 * total and (left > 0 or right + 1 < len(seg)):
            lv = seg[left - 1] if left > 0 else -1.0
            rv = seg[right + 1] if right + 1 < len(seg) else -1.0
            if rv >= lv:
                right += 1
                acc += float(seg[right])
            else:
                left -= 1
                acc += float(seg[left])
        widths.append((right - left + 1) * 1000.0 / sr)
    return float(np.median(widths)) if widths else float('nan')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--cli', default=str(ROOT / 'build' / 'boiled_egg_cli'))
    args = ap.parse_args()
    cli = Path(args.cli)
    outdir = ROOT / 'results' / 'synthetic'
    outdir.mkdir(parents=True, exist_ok=True)

    cases = [
        ('identity', 'harmonic_stack.wav', 1.0, 0),
        ('stretch_075', 'harmonic_stack.wav', 0.75, 0),
        ('stretch_150', 'harmonic_stack.wav', 1.5, 0),
        ('transient_150', 'click_train.wav', 1.5, 0),
        ('pitch_m12', 'sine_440.wav', 1.0, -12),
        ('pitch_p12', 'sine_440.wav', 1.0, 12),
        ('pitch_p12_passband', 'sine_10000.wav', 1.0, 12),
        ('pitch_p12_stopband', 'sine_14000.wav', 1.0, 12),
        ('combo', 'synthetic_drums.wav', 1.25, 5),
        ('stereo', 'stereo_phase.wav', 1.0, 7),
    ]
    rows = []
    for name, src, time_ratio, pitch_st in cases:
        inp = ROOT / 'data' / 'synthetic' / src
        out = outdir / f'{name}.wav'
        subprocess.run(
            [str(cli), str(inp), str(out), '--time', str(time_ratio), '--pitch', str(pitch_st)],
            check=True,
            capture_output=True,
            text=True,
        )
        x, sr = sf.read(inp, always_2d=True)
        y, _ = sf.read(out, always_2d=True)
        expected = round(len(x) * time_ratio)
        row = {
            'case': name,
            'input_frames': len(x),
            'output_frames': len(y),
            'expected_frames': expected,
            'duration_error_frames': len(y) - expected,
        }
        if name in {'pitch_m12', 'pitch_p12'}:
            f = peak_hz(y[:, 0], sr)
            target = 440 * (2 ** (pitch_st / 12))
            row['peak_hz'] = f
            row['pitch_error_cents'] = 1200 * np.log2(f / target)
        if name in {'pitch_p12_passband', 'pitch_p12_stopband'}:
            row['middle_rms'] = middle_rms(y[:, 0], sr)
        if name == 'identity':
            row['identity_corr'] = corr(x[:, 0], y[:, 0])
        if name == 'stereo':
            row['stereo_lr_corr'] = corr(y[:, 0], y[:, 1])
            row['stereo_corr_error'] = row['stereo_lr_corr'] - corr(x[:, 0], x[:, 1])
        if name == 'transient_150':
            row['transient_90pct_width_ms'] = transient_width_ms(
                y[:, 0], sr, sr // 4, time_ratio
            )
        rows.append(row)

    by_name = {r['case']: r for r in rows}
    pass_rms = by_name['pitch_p12_passband']['middle_rms']
    stop_rms = by_name['pitch_p12_stopband']['middle_rms']
    by_name['pitch_p12_stopband']['alias_rejection_db'] = 20 * np.log10(
        max(stop_rms, 1e-15) / max(pass_rms, 1e-15)
    )

    fields = sorted({k for r in rows for k in r})
    with open(outdir / 'metrics.csv', 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


if __name__ == '__main__':
    main()
