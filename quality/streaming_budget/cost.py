#!/usr/bin/env python3
"""Fixed paired native cost study. A passed cost gate is not an RT guarantee."""
from __future__ import annotations
import argparse, hashlib, itertools, json, math, os, platform, statistics, subprocess, sys
from pathlib import Path
import numpy as np

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def grid():
    cases=[]
    for rate,block,channels,(time,pitch) in itertools.product((48000,96000),(32,64),(1,2),((1,1),(.25,1),(1,.25),(1.25,1.3348398))):
        cases.append(dict(rate=rate,block=block,channels=channels,time=time,pitch=pitch,mode='stream'))
    for rate,block,pitch in itertools.product((48000,96000),(32,64),(.5,1,2,4)):
        cases.append(dict(rate=rate,block=block,channels=2,time=1,pitch=pitch,mode='rt'))
    return cases

def prepare(root,client,baseline,candidate,out):
    out.mkdir(parents=True,exist_ok=False)
    paths=subprocess.check_output(['git','ls-files','-z'],cwd=root).decode().split('\0')
    files={str((root/p).resolve()):sha(root/p) for p in paths if p}
    for p in (client,baseline,candidate):files[str(p.resolve())]=sha(p)
    for lib in (baseline,candidate):
        text=subprocess.check_output(['ldd',str(lib)],text=True)
        for line in text.splitlines():
            if '=>' in line:
                p=line.split('=>')[1].strip().split()[0]
                if p.startswith('/'):files[p]=sha(p)
    affinity=sorted(os.sched_getaffinity(0))
    plan=dict(schema='boiled-egg.wsola-cost.v1',client=str(client.resolve()),baseline=str(baseline.resolve()),candidate=str(candidate.resolve()),
        files=files,cases=grid(),repetitions=3,cpu=affinity[0],allowed_affinity=affinity,platform=platform.platform(),python=sys.version,numpy=np.__version__,
        primary='native time per same accepted input block',order='alternate pair by case+repeat',gate_max_ratio=1.25,rt_fraction=.8)
    (out/'plan.json').write_text(json.dumps(plan,indent=2)+'\n')
    return sha(out/'plan.json')

def verify(plan):
    if plan['cases']!=grid() or plan['repetitions']!=3:raise ValueError('fixed grid changed')
    for p,h in plan['files'].items():
        if sha(p)!=h:raise ValueError('source/binary/dependency changed: '+p)

def assess(rows):
    keys=[(r['case'],r['repeat'],r['role']) for r in rows]
    expected=set(itertools.product(range(48),range(3),('baseline','candidate')))
    if len(keys)!=len(set(keys)) or set(keys)!=expected:raise ValueError('incomplete/duplicate grid')
    result=dict(schema='boiled-egg.wsola-cost-result.v1',rows=len(rows),hard_rt_qualified=False)
    if any(r.get('status')!='complete' for r in rows):return dict(**result,integrity=False,decision='blocked_execution')
    for r in rows:
        for key in ('native_seconds','wall_seconds'):
            value=r['measurement'][key]
            if not math.isfinite(value) or value<=0:raise ValueError('nonpositive/nonfinite timing')
    paired={(r['case'],r['repeat'],r['role']):r for r in rows};cells=[]
    for i,c in enumerate(grid()):
        bs=[paired[i,j,'baseline'] for j in range(3)];cs=[paired[i,j,'candidate'] for j in range(3)]
        for a,b in zip(bs,cs):
            if a['pcm_sha256']!=b['pcm_sha256']:raise ValueError('PCM changed')
            for key in ('input_frames','output_frames','input_blocks','api_calls','pulls','underruns','latency','tail'):
                if a['measurement'][key]!=b['measurement'][key]:raise ValueError('contract changed: '+key)
        if len({r['pcm_sha256'] for r in bs+cs})!=1:raise ValueError('repeat PCM changed')
        bn=statistics.median(r['measurement']['native_seconds']/r['measurement']['input_blocks'] for r in bs)
        cn=statistics.median(r['measurement']['native_seconds']/r['measurement']['input_blocks'] for r in cs)
        bw=statistics.median(r['measurement']['wall_seconds'] for r in bs);cw=statistics.median(r['measurement']['wall_seconds'] for r in cs)
        vals=(bn,cn,bw,cw)
        if not all(math.isfinite(v) and v>0 for v in vals):raise ValueError('nonpositive/nonfinite timing')
        cells.append(dict(case=i,**c,native_ratio=cn/bn,wall_ratio=cw/bw,baseline_native_per_block=bn,candidate_native_per_block=cn,
            cost_pass=cn/bn<=1.25,baseline_warm_create=statistics.median(r['measurement']['warm_create_seconds'] for r in bs),
            candidate_warm_create=statistics.median(r['measurement']['warm_create_seconds'] for r in cs),
            cache_sample_bytes=cs[0]['measurement']['window']//2*4,baseline_max=max(r['calls']['max'] for r in bs),candidate_max=max(r['calls']['max'] for r in cs)))
    groups={}
    for mode in ('stream','rt'):
        rr=[r for r in cells if r['mode']==mode]
        groups[mode]=dict(cases=len(rr),cost_pass=sum(r['cost_pass'] for r in rr),native_ratio_median=statistics.median(r['native_ratio'] for r in rr),native_ratio_max=max(r['native_ratio'] for r in rr),
            wall_ratio_median=statistics.median(r['wall_ratio'] for r in rr),wall_ratio_max=max(r['wall_ratio'] for r in rr),faster=sum(r['native_ratio']<1 for r in rr))
    rt=[]
    for rate,block,role in itertools.product((48000,96000),(32,64),('baseline','candidate')):
        rr=[r for r in rows if r['role']==role and grid()[r['case']]['mode']=='rt' and grid()[r['case']]['rate']==rate and grid()[r['case']]['block']==block]
        states={k:[r for r in rr if r['case']==k] for k in {r['case'] for r in rr}}
        best_worst=max(min(r['services']['mean'] for r in s) for s in states.values())
        best_worst_max=max(min(r['services']['max'] for r in s) for s in states.values())
        rt.append(dict(rate=rate,block=block,role=role,worst_best_of_three_mean=best_worst,period=block/rate,best_mean_within_80pct=best_worst<=.8*block/rate,worst_best_of_three_max=best_worst_max,best_max_within_80pct=best_worst_max<=.8*block/rate,
                       observed_80pct_exceedances=sum(r['services']['over80'] for r in rr),observed_period_exceedances=sum(r['services']['over100'] for r in rr),
                       full_passes_within_period=sum(r['services']['over100']==0 for r in rr),passes=len(rr),max_observed=max(r['services']['max'] for r in rr)))
    return dict(**result,integrity=True,pcm_pairs=144,groups=groups,cells=cells,rt_diagnostics=rt,decision='same-output-cost-observation')

def run(planpath,digest,out):
    if sha(planpath)!=digest:raise ValueError('plan SHA mismatch')
    plan=json.loads(planpath.read_text());verify(plan);out.mkdir(parents=True,exist_ok=False);rows=[]
    for i,c in enumerate(plan['cases']):
        for repeat in range(3):
            order=('baseline','candidate') if (i+repeat)%2==0 else ('candidate','baseline')
            for role in order:
                prefix=out/f'{i:02}-{repeat}-{role}';row=dict(case=i,repeat=repeat,role=role,status='failed')
                env=dict(os.environ,LD_LIBRARY_PATH=str(Path(plan[role]).parent),OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1')
                argv=['taskset','-c',str(plan['cpu']),plan['client'],str(c['rate']),str(c['channels']),str(c['block']),str(c['time']),str(c['pitch']),c['mode'],str(prefix)]
                try:
                    linked=subprocess.check_output(['ldd',plan['client']],env=env,text=True)
                    resolved=[line.split('=>')[1].split()[0] for line in linked.splitlines() if line.strip().startswith('libboiled_egg.so ') and '=>' in line]
                    if len(resolved)!=1 or Path(resolved[0]).resolve()!=Path(plan[role]).resolve():raise ValueError('incorrect library resolved')
                    r=subprocess.run(argv,env=env,text=True,capture_output=True,timeout=45)
                    prefix.with_suffix('.stdout').write_text(r.stdout);prefix.with_suffix('.stderr').write_text(r.stderr)
                    if r.returncode:raise ValueError('client exit '+str(r.returncode))
                    m=json.loads(r.stdout);pcm=prefix.with_suffix('.f32');audio=np.fromfile(pcm,dtype='<f4')
                    if audio.size!=m['output_frames']*c['channels'] or not np.isfinite(audio).all() or not np.any(audio):raise ValueError('invalid PCM')
                    def timings(suffix):
                        p=Path(str(prefix)+suffix);v=np.fromfile(p,dtype='<f8')
                        if not len(v) or not np.isfinite(v).all() or np.any(v<0):raise ValueError('invalid timings')
                        return dict(count=len(v),mean=float(np.mean(v)),p99=float(np.quantile(v,.99)),max=float(np.max(v)),over80=int(np.sum(v>.8*c['block']/c['rate'])),over100=int(np.sum(v>c['block']/c['rate'])),sha256=sha(p))
                    calls=timings('.calls.f64');services=timings('.services.f64')
                    if calls['count']!=m['api_calls'] or services['count']!=m['input_blocks']:raise ValueError('timing count')
                    row.update(status='complete',measurement=m,pcm_sha256=sha(pcm),pcm_file=pcm.name,calls=calls,services=services)
                except (OSError,ValueError,subprocess.SubprocessError) as exc:row['error']=str(exc)
                rows.append(row)
                with (out/'rows.jsonl').open('a') as f:f.write(json.dumps(row,allow_nan=False)+'\n')
        print(f'{i+1}/48',flush=True)
    verify(plan)
    try:summary=assess(rows)
    except (ValueError,KeyError,TypeError) as exc:summary=dict(integrity=False,decision='blocked_invalid_or_changed_evidence',error=str(exc),rows=len(rows),hard_rt_qualified=False)
    summary['plan_sha256']=digest;(out/'summary.json').write_text(json.dumps(summary,indent=2,allow_nan=False)+'\n');return summary

if __name__=='__main__':
    p=argparse.ArgumentParser();s=p.add_subparsers(dest='action',required=True)
    a=s.add_parser('prepare');a.add_argument('--root',type=Path,required=True);a.add_argument('--client',type=Path,required=True);a.add_argument('--baseline',type=Path,required=True);a.add_argument('--candidate',type=Path,required=True);a.add_argument('--output',type=Path,required=True)
    a=s.add_parser('run');a.add_argument('--plan',type=Path,required=True);a.add_argument('--sha256',required=True);a.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    if a.action=='prepare':print(prepare(a.root,a.client,a.baseline,a.candidate,a.output))
    else:raise SystemExit(0 if run(a.plan,a.sha256,a.output)['integrity'] else 2)
