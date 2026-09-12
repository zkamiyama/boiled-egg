#!/usr/bin/env python3
"""Raw peak audit of the exact-grid reference-only profile experiment.

Flags request human review; floating-point samples above 1 are not proof of an
audible artifact. No source audio is altered and no MOS labels are transferred.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import tempfile
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

from eval_reference_profiles import PROFILES
from eval_multires_corpus import fingerprint
from make_blind_multires_pack import load_trial
from make_reference_profile_pack import inside, read_grid


def ratio(a: float, b: float) -> float | None:
    return a/b if b > 0 else None


def db(value: float) -> float | None:
    return 20*math.log10(value) if value > 0 else None


def delta_db(a: float, b: float) -> float | None:
    value = ratio(a, b)
    return db(value) if value is not None else None


def raw_stats(audio: np.ndarray, rate: int) -> dict:
    peak = float(np.max(np.abs(audio)))
    rms = math.sqrt(float(np.mean(audio*audio)))
    frame, channel = np.unravel_index(np.argmax(np.abs(audio)), audio.shape)
    return dict(peak=peak, rms=rms, peak_dbfs=db(peak), rms_dbfs=db(rms),
                crest_db=delta_db(peak, rms), peak_time_seconds=float(frame/rate),
                peak_channel=int(channel), samples_above_unity=int(np.count_nonzero(np.abs(audio) > 1)))


def audit(evaluation: Path, references: Path, *, peak_limit: float = 1.0,
          ratio_limit: float = 1.1) -> tuple[list[dict], dict]:
    if not all(math.isfinite(v) and v > 0 for v in (peak_limit, ratio_limit)):
        raise ValueError('review limits must be finite and positive')
    summary, grid = read_grid(evaluation)
    paired = defaultdict(dict)
    for row in grid:
        paired[(row['stem'], row['pitch_semitones'], row['formant'])][row['profile']] = row
    rows = []
    for (stem, pitch, formant), systems in sorted(paired.items()):
        first = systems['general']
        reference = inside(references, first['reference_name'])
        paths = {p: inside(evaluation, systems[p]['render_path']) for p in PROFILES}
        if fingerprint(reference) != first['reference_sha256']:
            raise ValueError('reference fingerprint mismatch')
        if any(fingerprint(path) != systems[p]['render_sha256'] for p, path in paths.items()):
            raise ValueError('render fingerprint mismatch')
        ref, audio, rate = load_trial(reference, paths)
        if rate != first['sample_rate'] or ref.shape != (first['frames'], first['channels']):
            raise ValueError('reference audio metadata mismatch')
        ref_stats = raw_stats(ref, rate)
        stats = {p: raw_stats(audio[p], rate) for p in PROFILES}
        baseline = stats['transient']
        for profile in PROFILES:
            measured = stats[profile]
            metric = systems[profile]
            if any(not math.isclose(measured[name], metric[name], rel_tol=1e-7, abs_tol=1e-12)
                   for name in ('peak', 'rms')):
                raise ValueError('CSV peak/RMS does not match fingerprinted raw audio')
            peak_ratio = ratio(measured['peak'], baseline['peak'])
            reasons = []
            if measured['peak'] > peak_limit:
                reasons.append('absolute_peak')
            if peak_ratio is not None and peak_ratio > ratio_limit:
                reasons.append('peak_vs_transient')
            if measured['peak'] > 0 and (ref_stats['peak'] == 0 or baseline['peak'] == 0):
                reasons.append('nonzero_against_silence')
            rows.append(dict(stem=stem, category=metric['category'], pitch_semitones=pitch,
                formant=formant, profile=profile, sample_rate=rate, frames=len(ref), channels=ref.shape[1],
                **measured, reference_peak=ref_stats['peak'], reference_rms=ref_stats['rms'],
                peak_ratio_vs_reference=ratio(measured['peak'], ref_stats['peak']),
                peak_ratio_vs_transient=peak_ratio,
                rms_delta_vs_reference_db=delta_db(measured['rms'], ref_stats['rms']),
                rms_delta_vs_transient_db=delta_db(measured['rms'], baseline['rms']),
                crest_delta_vs_transient_db=(measured['crest_db']-baseline['crest_db']
                    if measured['crest_db'] is not None and baseline['crest_db'] is not None else None),
                env=metric['env'], onset=metric['onset'],
                env_delta_vs_transient=metric['env']-systems['transient']['env'],
                onset_delta_vs_transient=metric['onset']-systems['transient']['onset'],
                reference_sha256=metric['reference_sha256'], render_sha256=metric['render_sha256'],
                render_path=metric['render_path'], review_reasons=';'.join(reasons),
                artifact_assessment='not_listened'))
    report = dict(schema='boiled-egg.reference-peak-audit.v1', corpus_label=summary['corpus_label'],
        evaluation_summary_sha256=fingerprint(evaluation/'summary.json'),
        metrics_sha256=fingerprint(evaluation/'metrics.csv'), source_commit=summary.get('source_commit'),
        conditions=len(paired), measurements=len(rows), review_rows=sum(bool(r['review_reasons']) for r in rows),
        review_limits=dict(peak=peak_limit, ratio_vs_transient=ratio_limit),
        category_measurements=dict(sorted(Counter(r['category'] for r in rows).items())),
        formant_measurements=dict(sorted(Counter(r['formant'] for r in rows).items())),
        max_peak=max(r['peak'] for r in rows), listening_status='not_listened', external_baseline='none',
        metric_policy='Peak/RMS remeasured from raw audio; envelope/onset copied from validated evaluator CSV.',
        interpretation='Reference-only exact-grid audit, not the held-out four-way comparison. '
                       'Flags require listening, not automatic rejection. Silence ratios/dB remain null.')
    return rows, report


def write_report(output: Path, rows: list[dict], report: dict) -> None:
    if output.exists() and (not output.is_dir() or any(output.iterdir())):
        raise ValueError('output must be absent or empty')
    output.parent.mkdir(parents=True, exist_ok=True)
    outliers = sorted([r for r in rows if r['review_reasons']],
                      key=lambda r: (r['peak_ratio_vs_transient'] or 0, r['peak']), reverse=True)
    with tempfile.TemporaryDirectory(prefix='.reference-peaks-', dir=output.parent) as tmp:
        staging = Path(tmp)/'report'
        staging.mkdir()
        for name, selected in [('all_peaks.csv', rows), ('peak_outliers.csv', outliers)]:
            with (staging/name).open('w', newline='', encoding='utf-8') as stream:
                writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
                writer.writeheader(); writer.writerows(selected)
        (staging/'summary.json').write_text(json.dumps(report, indent=2, allow_nan=False)+'\n', encoding='utf-8')
        if output.exists():
            output.rmdir()
        staging.rename(output)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('evaluation', 'ref-dir', 'output'):
        parser.add_argument('--'+name, type=Path, required=True)
    parser.add_argument('--peak-limit', type=float, default=1.0)
    parser.add_argument('--ratio-limit', type=float, default=1.1)
    args = parser.parse_args()
    rows, report = audit(args.evaluation, args.ref_dir, peak_limit=args.peak_limit, ratio_limit=args.ratio_limit)
    write_report(args.output, rows, report)
    print(json.dumps(report, indent=2, allow_nan=False))


if __name__ == '__main__':
    main()
