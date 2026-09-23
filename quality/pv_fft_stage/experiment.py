#!/usr/bin/env python3
"""Run the existing complete PV replay with explicit FFT-experiment provenance.

The historical comparator is reused unchanged. Its BASE is an expected-provenance
constant, not a processing option; bind it explicitly to this experiment's actual
predecessor before invoking its original input/output checks and measurement code.
The old pooled cost gate is retained, with fixed-I/O reported separately.
"""
from __future__ import annotations
import argparse
import contextlib
import io
import json
from pathlib import Path
import statistics
import sys
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'quality/pv_ring'))
import compare as replay
BASE='d4093d87aba960a1965b1243f6e685a23420ff25'
PROTOCOL='284306e912e8d3205ce027f5cec2f0e63f2ae65b'
EXPERIMENT='pv-fft-first-stage-v1'
replay.BASE=BASE


def check_plan(plan):
    if plan.get('experiment')!=EXPERIMENT or plan.get('protocol_commit')!=PROTOCOL:
        raise ValueError('Wrong FFT experiment/protocol')
    replay.identity(plan)


def cost_decision(report):
    if report.get('mode')!='cost' or not report.get('integrity_pass'):
        return dict(qualified=False,reason='not a complete paired cost run',hard_realtime_qualified=False)
    groups={}
    for io_mode in (1,2):
        rows=[r for r in report['pairs'] if r['io']==io_mode]
        if len(rows)!=32:raise ValueError('Incomplete I/O stratum')
        ratios=[r['ratio'] for r in rows]
        groups[str(io_mode)]=dict(settings=32,median_ratio=statistics.median(ratios),max_ratio=max(ratios),
            faster=sum(r<1 for r in ratios),goal_pass=statistics.median(ratios)<=1 and max(ratios)<=1.25)
    return dict(qualified=groups['2']['goal_pass'],fixed_io=groups['2'],streaming_control=groups['1'],
        original_pooled_gate=report['cost_goal_pass'],hard_realtime_qualified=False)


def main():
    p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest='cmd',required=True)
    a=sub.add_parser('prepare')
    for name in ('runner','before','after','out'):a.add_argument('--'+name,type=Path,required=True)
    a=sub.add_parser('run');a.add_argument('--plan',type=Path,required=True);a.add_argument('--sha256',required=True)
    a.add_argument('--mode',choices=('quality','cost'),required=True);a.add_argument('--out',type=Path,required=True)
    args=p.parse_args()
    if args.cmd=='prepare':
        with contextlib.redirect_stdout(io.StringIO()):replay.prepare(args)
        path=args.out/'plan.json';plan=json.loads(path.read_text())
        plan.update(experiment=EXPERIMENT,protocol_commit=PROTOCOL,
                    scope='Exact cooperative first-stage FFT batching; no waveform change')
        check_plan(plan);replay.write(path,plan);print(replay.sha(path));return 0
    check_plan(json.loads(args.plan.read_text()))
    status=replay.run(args)
    if args.mode=='cost':
        decision=cost_decision(json.loads((args.out/'summary.json').read_text()))
        replay.write(args.out/'fft-stage-decision.json',decision)
        print(json.dumps(decision,indent=2))
    return status

if __name__=='__main__':raise SystemExit(main())
