#!/usr/bin/env python3
"""Declared, rotated timing experiment; no best-run selection or parallel trials.

Standard library only. A failed/incomplete run cannot publish COMPLETE.json.
Existing results are never overwritten. Periodic and saturated runs stay separate.
"""
from __future__ import annotations
import argparse
import hashlib
import itertools
import json
import os
import platform
import subprocess
from pathlib import Path

PROTOCOLS = (('saturated','legacy'), ('saturated','cpu'), ('saturated','wall'),
             ('periodic','cpu'), ('periodic','wall'))

def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

def snapshot() -> dict:
    result = {'uname':list(platform.uname()),'affinity':sorted(os.sched_getaffinity(0))}
    for name in ('/sys/fs/cgroup/cpu.max','/sys/fs/cgroup/cpu.stat','/proc/self/cgroup',
                 '/proc/sys/kernel/perf_event_paranoid','/sys/devices/system/clocksource/clocksource0/current_clocksource'):
        try: result[name] = Path(name).read_text()
        except OSError as error: result[name] = {'unavailable':str(error)}
    return result

def run(args: argparse.Namespace) -> None:
    if args.output.exists() or not 1<=args.count<=100000:
        raise ValueError('absent output and count in [1,100000] required')
    probes={}
    for text in args.probe:
        label, path = text.split('=',1)
        if not label or not all(c.isalnum() or c in '-_' for c in label) or label in probes:
            raise ValueError('unique simple labels required')
        probes[label]=Path(path).resolve(strict=True)
    policy = None
    if args.matrix=='capacity':
        from capacity import DEFAULT_POLICY, validate_policy
        policy=validate_policy(json.loads(args.policy.read_text()) if args.policy else DEFAULT_POLICY)
        if args.count<policy['minimum_steady_calls']:
            raise ValueError('count below capacity policy')
    dependencies={str(p.resolve(strict=True)):digest(p.resolve(strict=True))
                  for p in getattr(args,'dependency',[])}
    args.output.mkdir(parents=True)
    identity={label:dict(path=str(p),sha256=digest(p)) for label,p in probes.items()}
    if args.matrix=='observer':
        cells=list(itertools.product(probes,('dsp','control','noop'),PROTOCOLS,(96000,),(32,),(7,)))
    elif args.matrix=='capacity':
        cells=list(itertools.product(probes,('dsp',),(('saturated','wall'),),(48000,96000),(32,64),(-12,-7,-3,0,3,7,12)))
    else:
        cells=list(itertools.product(probes,('dsp',),(('periodic','wall'),),(48000,96000),(32,64),(-12,-7,-3,3,7,12)))
    order=[]
    for repeat in (1,2,3):
        rotated=cells[repeat-1:]+cells[:repeat-1]
        if repeat==2: rotated=list(reversed(rotated))
        for label,workload,protocol,rate,block,shift in rotated:
            name=f'{label}-{workload}-{protocol[0]}-{protocol[1]}-{rate}-{block}-{shift:+d}-r{repeat}'
            order.append(dict(name=name,label=label,workload=workload,schedule=protocol[0],bracket=protocol[1],
                              rate=rate,block=block,shift=shift,repeat=repeat))
    manifest=dict(schema='boiled-egg.rt-audit-matrix.v1',count=args.count,probes=identity,
                  matrix=args.matrix,runs=order,runner_sha256=digest(Path(__file__)),environment=snapshot(),
                  dependencies=dependencies,capacity_policy=policy)
    (args.output/'plan.json').write_text(json.dumps(manifest,indent=2)+'\n')
    for i,cell in enumerate(order):
        cmd=[str(probes[cell['label']]),str(args.count),'200',str(cell['repeat']),cell['workload'],
             cell['schedule'],cell['bracket'],str(cell['rate']),str(cell['block']),str(cell['shift'])]
        if any(digest(Path(p))!=h for p,h in dependencies.items()):raise ValueError('linked dependency changed')
        before=snapshot()
        with (args.output/(cell['name']+'.csv')).open('x') as out, (args.output/(cell['name']+'.json')).open('x') as err:
            proc=subprocess.run(cmd,stdout=out,stderr=err,timeout=180,check=False)
        info=dict(command=cmd,returncode=proc.returncode,before=before,after=snapshot(),
                  csv_sha256=digest(args.output/(cell['name']+'.csv')),
                  metadata_sha256=digest(args.output/(cell['name']+'.json')))
        (args.output/(cell['name']+'.receipt.json')).write_text(json.dumps(info,indent=2)+'\n')
        if proc.returncode: raise RuntimeError(f'{cell["name"]} failed; evidence retained')
        if any(digest(p)!=identity[k]['sha256'] for k,p in probes.items()):raise ValueError('probe changed')
        if any(digest(Path(p))!=h for p,h in dependencies.items()):raise ValueError('linked dependency changed')
        if (i+1)%5==0: print(f'{i+1}/{len(order)} runs complete',flush=True)
    (args.output/'COMPLETE.json').write_text(json.dumps(dict(plan_sha256=digest(args.output/'plan.json'),runs=len(order)))+'\n')

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--probe',action='append',required=True,metavar='LABEL=EXECUTABLE')
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--count',type=int,default=12000)
    parser.add_argument('--matrix',choices=('observer','periodic','capacity'),default='observer')
    parser.add_argument('--policy',type=Path,help='capacity policy fixed before trials')
    parser.add_argument('--dependency',type=Path,action='append',default=[],help='explicit linked library/source identity; repeatable')
    run(parser.parse_args())
