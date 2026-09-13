#!/usr/bin/env python3
"""Exploratory correlation of descriptors with PROVIDED TSM MOS only.

This does not predict any new render's MOS. Three methods have different time
ratios; correlations are confounded and are not a validated perceptual model.
"""
import argparse,concurrent.futures as cf,csv,json,math
from pathlib import Path
import numpy as np
from scipy import stats
import compare_zplane_outputs as c

def measure(job):
    row,refs,tests=job
    source,rate=c.e.checked_audio(c.e.inside(refs,row['ref_name']))
    audio,sr=c.e.checked_audio(c.e.inside(tests,row['test_name']))
    if sr!=rate:raise ValueError('rate mismatch')
    return dict(source=row['ref_name'],method=row['method'],name=row['test_name'],mos=float(row['MeanOS']),
        **c.tsm_metrics(source,audio,rate))

def run(args):
    rows=c.e.score_rows(args.catalog);index={r['test_name']:r for r in rows}
    jobs=[(index[p.name],args.refs,args.tests) for p in sorted(args.tests.glob('*.wav'))]
    with cf.ProcessPoolExecutor(max_workers=args.workers) as pool: measured=list(pool.map(measure,jobs))
    groups={}
    for method in ('all',*sorted({r['method'] for r in measured})):
        selected=[r for r in measured if method=='all' or r['method']==method]
        groups[method]={metric:dict(n=len(selected),spearman=float(stats.spearmanr([r[metric] for r in selected],[r['mos'] for r in selected]).statistic)) for metric in c.DIRECTIONS}
    args.output.mkdir(parents=True,exist_ok=False)
    with (args.output/'provided_scores.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(measured[0]));w.writeheader();w.writerows(measured)
    report=dict(groups=groups,rows=len(measured),catalog_sha256=c.fingerprint(args.catalog),
        new_audio_mos_predicted=False,interpretation='Provided-score association only. No causal/held-out perceptual validation; methods use different time ratios.')
    (args.output/'summary.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('refs','tests','catalog','output'):p.add_argument('--'+n,type=Path,required=True)
    p.add_argument('--workers',type=int,default=2);run(p.parse_args())
