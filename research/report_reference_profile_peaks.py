#!/usr/bin/env python3
"""Raw peak review for exact-grid reference profiles; no audible-artifact verdict."""
from __future__ import annotations

import argparse
import json
import math
import tempfile
from collections import defaultdict
from pathlib import Path

from eval_multires_corpus import fingerprint
from make_blind_multires_pack import load_trial
from make_reference_profile_pack import inside, read_grid
from report_peak_outliers import amplitude, db, ratio, write_csv


def audit(evaluation: Path, references: Path, peak_threshold: float = 1.0,
          ratio_threshold: float = 1.1) -> tuple[list[dict], dict]:
    if any(not math.isfinite(v) or v <= 0 for v in (peak_threshold,ratio_threshold)):
        raise ValueError('review thresholds must be finite and positive')
    source_summary, metrics = read_grid(evaluation)
    grouped = defaultdict(dict)
    for row in metrics:
        grouped[(row['stem'],row['pitch_semitones'],row['formant'])][row['profile']] = row
    rows = []
    for (stem,pitch,formant), paired in sorted(grouped.items()):
        first = paired['general']
        ref = inside(references,first['reference_name'])
        paths = {p:inside(evaluation,r['render_path']) for p,r in paired.items()}
        if fingerprint(ref) != first['reference_sha256'] or any(
                fingerprint(paths[p]) != r['render_sha256'] for p,r in paired.items()):
            raise ValueError('raw-audio fingerprint mismatch')
        reference,audio,rate = load_trial(ref,paths)
        if rate != first['sample_rate'] or reference.shape != (first['frames'],first['channels']):
            raise ValueError('raw-audio metadata mismatch')
        ref_stats = amplitude(reference,rate)
        stats = {p:amplitude(x,rate) for p,x in audio.items()}
        baseline = stats['transient']
        for profile, value in stats.items():
            relative = ratio(value['peak'],baseline['peak'])
            flags = []
            if value['peak'] > peak_threshold: flags.append('sample_peak_above_threshold')
            if relative is not None and relative > ratio_threshold: flags.append('peak_ratio_vs_transient')
            if baseline['peak'] == 0 and value['peak'] > 0: flags.append('nonzero_vs_silent_transient')
            if ref_stats['peak'] == 0 and value['peak'] > 0: flags.append('nonzero_vs_silent_reference')
            rows.append(dict(stem=stem,category=first['category'],pitch_semitones=pitch,
                formant=formant,profile=profile,**value,
                peak_ratio_vs_reference=ratio(value['peak'],ref_stats['peak']),
                peak_ratio_vs_transient=relative,
                rms_delta_vs_reference_db=db(ratio(value['rms'],ref_stats['rms'])),
                rms_delta_vs_transient_db=db(ratio(value['rms'],baseline['rms'])),
                env=paired[profile]['env'],onset=paired[profile]['onset'],
                review_flags=';'.join(flags),artifact_assessment='not_listened',listening_notes='',
                render_path=paired[profile]['render_path'],render_sha256=paired[profile]['render_sha256']))
    summary = dict(schema='boiled-egg.reference-profile-peaks.v1',
        corpus_label=source_summary['corpus_label'],external_baseline='none',
        evaluation_summary_sha256=fingerprint(evaluation/'summary.json'),
        conditions=len(grouped),rows=len(rows),flagged_rows=sum(bool(r['review_flags']) for r in rows),
        peak_threshold=peak_threshold,ratio_threshold=ratio_threshold,
        notes=['Raw sample peaks, not true peaks; no normalization or limiting.',
               'Review flags are not audible-artifact failures or promotion gates.',
               'Undefined silence ratios remain null/blank; no invented floor.',
               'Envelope/onset copied from fingerprinted evaluator metrics.'])
    return rows,summary


def main() -> None:
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('evaluation','ref-dir','output'):
        parser.add_argument('--'+name,type=Path,required=True)
    parser.add_argument('--peak-threshold',type=float,default=1.0)
    parser.add_argument('--ratio-threshold',type=float,default=1.1)
    args=parser.parse_args()
    if args.output.exists(): raise ValueError('output must not exist')
    rows,summary=audit(args.evaluation,args.ref_dir,args.peak_threshold,args.ratio_threshold)
    flagged=sorted((r for r in rows if r['review_flags']),key=lambda r:(
        r['peak_ratio_vs_transient'] if r['peak_ratio_vs_transient'] is not None else -1,r['peak']),reverse=True)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.peak-review-',dir=args.output.parent) as tmp:
        staging=Path(tmp)/'report';staging.mkdir()
        write_csv(staging/'all_conditions.csv',rows,tuple(rows[0]))
        write_csv(staging/'peak_outliers.csv',flagged,tuple(rows[0]))
        (staging/'summary.json').write_text(json.dumps(summary,indent=2,allow_nan=False)+'\n')
        staging.rename(args.output)
    print(json.dumps(summary,indent=2))


if __name__ == '__main__':
    main()
