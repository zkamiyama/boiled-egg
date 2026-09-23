#!/usr/bin/env python3
"""Fixed same-executable old/new PV comparison; no MOS or vendor evaluation."""
from __future__ import annotations
import argparse, hashlib, itertools, json, math, os, platform, statistics, subprocess, sys
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'quality/formant_detail'))
import verify as detail
BASE='b972e0355ae656a74fb3fb1b1a99429f1668a5e4'
FIELDS=('family','rate','channels','block','shift','io','detail','repeat','side')

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def write(path,data):Path(path).write_text(json.dumps(data,indent=2,allow_nan=False)+'\n')
def key(row):return tuple(row[k] for k in FIELDS)
def specifications(mode):
    if mode=='quality':
        tuples=itertools.product(detail.FAMILIES,detail.RATES,(1,),(64,),detail.SHIFTS,(1,),(0,1),range(3))
    elif mode=='cost':
        tuples=itertools.product(('vowel120',),detail.RATES,(1,2),(32,64),detail.SHIFTS,(1,2),(0,1),range(3))
    else:raise ValueError('unknown fixed mode')
    result=[]
    for values in tuples:
        spec=dict(zip(FIELDS[:-1],values))
        for side in (('before','after') if spec['repeat']%2==0 else ('after','before')):
            result.append(dict(spec,side=side))
    return result

def finite(value):
    if isinstance(value,dict):return all(finite(v) for v in value.values())
    if isinstance(value,list):return all(finite(v) for v in value)
    return math.isfinite(value) if isinstance(value,(int,float)) else True

def validate_row(r):
    if r['status']!='complete' or not finite(r):raise ValueError('failed/nonfinite receipt')
    for field in ('pcm_sha256','receipt_sha256'):
        h=r[field]
        if not isinstance(h,str) or len(h)!=64 or any(c not in '0123456789abcdef' for c in h):raise ValueError('invalid hash')
    info=r['info'];n=2*r['rate']+info['latency'];block=r['block']
    if any(info[k]!=r[k] for k in ('rate','channels','io','detail','repeat')):raise ValueError('wrong identity')
    if info['frames']!=n or info['energy']<=1e-12 or info['peak']<=0:raise ValueError('length or silence')
    if r['channels']==2 and info['proportional_error']!=0:raise ValueError('lost proportional stereo')
    count=(n+block-1)//block
    if type(info['input_blocks'])!=int or info['input_blocks']!=count or len(info['services'])!=count:raise ValueError('missing callback records')
    if any(type(v) not in (float,int) or v<0 for v in info['services']):raise ValueError('invalid duration')
    if info['service_seconds']<=0 or info['setup_seconds']<0 or info['flush_seconds']<0:raise ValueError('invalid total timing')
    if not math.isclose(sum(info['services']),info['service_seconds'],rel_tol=1e-12,abs_tol=1e-12):raise ValueError('wrong sum')
    if max(info['services'])!=info['max_service_seconds']:raise ValueError('wrong maximum')
    periods=[min(block,n-j*block)/r['rate'] for j in range(count)]
    missed=sum(t>p for t,p in zip(info['services'],periods))
    if info['service_period_exceedances']!=missed:raise ValueError('wrong exceedance count')

def assess(rows,mode):
    expected={key(r) for r in specifications(mode)}
    try:keys=[key(r) for r in rows]
    except (KeyError,TypeError) as exc:raise ValueError('malformed identity') from exc
    if len(keys)!=len(set(keys)) or set(keys)!=expected:raise ValueError('missing/duplicate/unexpected grid')
    result=dict(attempts=len(rows),mode=mode,integrity_pass=False,cost_goal_pass=None,hard_realtime_qualified=False)
    try:
        for r in rows:validate_row(r)
    except (KeyError,ValueError,TypeError,OverflowError) as exc:return dict(result,error=str(exc),pairs=None)
    by={key(r):r for r in rows};pairs=[]
    for k,r in by.items():
        if k[-1]!='before':continue
        other=by[k[:-1]+('after',)]
        if r['pcm_sha256']!=other['pcm_sha256']:return dict(result,error='PCM differs',pairs=None)
        for name in ('frames','latency','tail','energy','peak','proportional_error'):
            if r['info'][name]!=other['info'][name]:return dict(result,error='metadata differs: '+name,pairs=None)
        if mode=='quality' and r['metrics']!=other['metrics']:return dict(result,error='acoustic measurement differs',pairs=None)
    groups={}
    for r in rows:groups.setdefault(key(r)[:-2],{}).setdefault(r['side'],[]).append(r)
    for k,sides in groups.items():
        if any(len({r['pcm_sha256'] for r in v})!=1 for v in sides.values()):return dict(result,error='repeat PCM differs',pairs=None)
        if mode!='cost':continue
        def summary(rr):
            timing=[r['info'] for r in rr]
            max_ratios=[]
            for i in timing:
                n=i['frames'];periods=[min(k[3],n-j*k[3])/k[1] for j in range(i['input_blocks'])]
                max_ratios.append(max(t/p for t,p in zip(i['services'],periods)))
            return dict(median_per_block=statistics.median(i['service_seconds']/i['input_blocks'] for i in timing),
                median_full=statistics.median(i['service_seconds']+i['flush_seconds'] for i in timing),
                max_service_seconds=max(i['max_service_seconds'] for i in timing),
                per_run_max_period_ratio=max_ratios,best_max_period_ratio=min(max_ratios),
                max_period_ratio=max(max_ratios),period_exceedances=sum(i['service_period_exceedances'] for i in timing),
                all_period_runs=sum(x<=1 for x in max_ratios),
                per_run_p99=[float(np.quantile(i['services'],.99)) for i in timing],
                median_setup=statistics.median(i['setup_seconds'] for i in timing))
        b=summary(sides['before']);a=summary(sides['after'])
        pairs.append(dict(zip(FIELDS[:-2],k),before=b,after=a,ratio=a['median_per_block']/b['median_per_block'],full_ratio=a['median_full']/b['median_full']))
    result.update(integrity_pass=True,pcm_pairs=len(rows)//2,repeats_identical=True,pairs=pairs)
    if mode=='cost':
        ratios=[p['ratio'] for p in pairs]
        result.update(median_ratio=statistics.median(ratios),max_ratio=max(ratios),faster=sum(r<1 for r in ratios),
            cost_goal_pass=statistics.median(ratios)<=1 and max(ratios)<=1.25)
        strata=[]
        for rate,io in itertools.product(detail.RATES,(1,2)):
            subset=[p for p in pairs if p['rate']==rate and p['io']==io]
            s=dict(rate=rate,io=io,settings=len(subset),median_ratio=statistics.median(p['ratio'] for p in subset),max_ratio=max(p['ratio'] for p in subset))
            for side in ('before','after'):
                s[side]=dict(best_max_80_pass=sum(p[side]['best_max_period_ratio']<=.8 for p in subset),
                    state_worst_best_max_ratio=max(p[side]['best_max_period_ratio'] for p in subset),
                    period_exceedances=sum(p[side]['period_exceedances'] for p in subset),all_period_runs=sum(p[side]['all_period_runs'] for p in subset))
            strata.append(s)
        result['strata']=strata
    return result

def identity(plan):
    if plan['base']!=BASE or plan['schema']!='pv-ring-cost-v1':raise ValueError('wrong protocol')
    for path,digest in plan['files'].items():
        if sha(path)!=digest:raise ValueError('changed source or binary: '+path)
    for record in plan['inputs'].values():
        if sha(record['path'])!=record['sha256']:raise ValueError('changed input')

def prepare(args):
    args.out.mkdir(parents=True,exist_ok=False)
    inputs={}
    for f,rate,ch in itertools.product(detail.FAMILIES,detail.RATES,(1,2)):
        p=(args.out/f'{f}-{rate}-{ch}.f32').resolve();p.write_bytes(detail.fixture(f,rate,ch).astype('<f4').tobytes());inputs[p.stem]=dict(path=str(p),sha256=sha(p))
    files={str(p.resolve()):sha(p) for p in ROOT.rglob('*') if p.is_file() and '.git' not in p.parts and '__pycache__' not in p.parts}
    for path in (args.runner,args.before,args.after):files.update(detail.metrics.binary_map(path.resolve()))
    plan=dict(schema='pv-ring-cost-v1',base=BASE,protocol_commit='9f1f212065a1ca4ba359b5fc43b235f248ff5a54',
        files=files,inputs=inputs,runner=str(args.runner.resolve()),libraries=dict(before=str(args.before.resolve()),after=str(args.after.resolve())),
        cpu=min(os.sched_getaffinity(0)),quality_runs=192,cost_runs=384,cost_gates=dict(median=1.0,maximum=1.25),
        environment=dict(python=sys.version,numpy=np.__version__,platform=platform.platform()),quality_claim='same PCM only',vendor_execution=False)
    write(args.out/'plan.json',plan);print(sha(args.out/'plan.json'))

def run(args):
    if sha(args.plan)!=args.sha256:raise ValueError('plan hash mismatch')
    plan=json.loads(args.plan.read_text());identity(plan);args.out.mkdir(parents=True,exist_ok=False)
    os.sched_setaffinity(0,{plan['cpu']})
    envs={}
    for side,lib in plan['libraries'].items():
        env=dict(os.environ,LD_LIBRARY_PATH=str(Path(lib).parent));envs[side]=env
        text=subprocess.run(['ldd',plan['runner']],env=env,text=True,capture_output=True,check=True,timeout=15).stdout
        paths=[x.split('=>',1)[1].split()[0] for x in text.splitlines() if x.strip().startswith('libboiled_egg.so ') and '=>' in x]
        if len(paths)!=1 or Path(paths[0]).resolve()!=Path(lib):raise ValueError('wrong SDK resolution')
        (args.out/f'{side}-ldd.txt').write_text(text)
    rows=[];specs=specifications(args.mode)
    for spec in specs:
        stem='-'.join(map(str,key(spec)));out=args.out/(stem+'.f32');receipt=args.out/(stem+'.json')
        source=plan['inputs'][f"{spec['family']}-{spec['rate']}-{spec['channels']}"]['path']
        argv=[plan['runner'],source,str(out),str(receipt),str(spec['rate']),str(spec['channels']),str(spec['block']),str(2**(spec['shift']/12)),str(spec['detail']),str(spec['io']),str(spec['repeat'])]
        row=dict(spec,status='failed')
        try:
            p=subprocess.run(argv,env=envs[spec['side']],capture_output=True,text=True,timeout=30)
            (args.out/(stem+'.log')).write_text(p.stdout+p.stderr)
            if p.returncode:raise ValueError('renderer exit '+str(p.returncode))
            info=json.loads(receipt.read_text());raw=np.fromfile(out,dtype='<f4').reshape(-1,spec['channels'])
            if len(raw)!=2*spec['rate']+info['latency'] or not np.isfinite(raw).all() or not np.any(raw):raise ValueError('invalid PCM')
            row.update(status='complete',output=str(out),receipt=str(receipt),pcm_sha256=sha(out),receipt_sha256=sha(receipt),info=info)
            validate_row(row)
            row['metrics']=detail.measure(raw[:,0],spec['family'],spec['rate'],spec['shift']) if args.mode=='quality' else None
        except (ValueError,RuntimeError,OSError,KeyError,subprocess.SubprocessError) as exc:row.update(status='failed',error=str(exc))
        rows.append(row)
        with (args.out/'rows.jsonl').open('a') as f:f.write(json.dumps(row,allow_nan=False)+'\n')
        if len(rows)%16==0:print(len(rows),len(specs),flush=True)
    identity(plan);result=assess(rows,args.mode);result.update(plan_sha256=args.sha256,rows=rows);write(args.out/'summary.json',result)
    print({k:v for k,v in result.items() if k not in ('rows','pairs')},flush=True)
    return 0 if result['integrity_pass'] and (args.mode!='cost' or result['cost_goal_pass']) else 2

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);sub=parser.add_subparsers(dest='cmd',required=True)
    p=sub.add_parser('prepare')
    for name in ('runner','before','after','out'):p.add_argument('--'+name,type=Path,required=True)
    p=sub.add_parser('run');p.add_argument('--plan',type=Path,required=True);p.add_argument('--sha256',required=True);p.add_argument('--mode',choices=('quality','cost'),required=True);p.add_argument('--out',type=Path,required=True)
    args=parser.parse_args()
    if args.cmd=='prepare':prepare(args)
    else:sys.exit(run(args))
