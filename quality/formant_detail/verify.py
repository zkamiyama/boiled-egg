#!/usr/bin/env python3
"""Public low-detail replay and same-work cost check. No vendor/MOS inference.
Existing #67 source families are regression data, not a fresh unseen holdout.
"""
from __future__ import annotations
import argparse,hashlib,itertools,json,os,platform,statistics,subprocess,sys,time
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'eval'))
import offline_pv_benchmark as metrics
import comparison_contract as contract
RATES=(48000,96000)
FAMILIES=('vowel120','vowel220','check83','check173')
SHIFTS=(-12,12)

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(p,v):Path(p).write_text(json.dumps(v,indent=2,allow_nan=False)+'\n')
def key(r):return tuple(r[k] for k in ('family','rate','channels','block','shift','io','detail','repeat'))
def envelope(f,check):
    centers,widths=((590,1630,2710),(115,155,195)) if check else ((650,1200,2500),(95,125,180))
    return .08+sum(a*np.exp(-.5*((np.asarray(f)-c)/w)**2) for a,c,w in zip((1,.8,.6),centers,widths))
def fixture(name,rate,channels=1):
    if name not in FAMILIES or rate not in RATES or channels not in (1,2):raise ValueError('unknown fixture')
    check=name.startswith('check');f0=int(name[5:]);t=np.arange(2*rate)/rate;k=np.arange(1,31)
    amplitudes=.03*envelope(f0*k,check)/k**.7
    x=np.zeros(len(t))
    for j,a in zip(k,amplitudes):x+=a*np.sin(2*np.pi*j*f0*t+(.43*j+.013*j*j if check else .17*j))
    x*=np.minimum(1,np.minimum(t/.03,(2-t)/.03));x=x.astype(np.float32)
    return x if channels==1 else np.stack((x,-.5*x),axis=1)
def measure(y,name,rate,shift):
    y=metrics.valid_vector(y)
    if len(y)!=2*rate:raise ValueError('wrong length')
    k=np.arange(1,31);f=k*int(name[5:])*2**(shift/12);z=y[rate//2:3*rate//2]
    a,residual=metrics.components(z,rate,f.tolist());a=np.asarray(a)
    target=.03*envelope(f,name.startswith('check'))/k**.7
    off=.03*envelope(k*int(name[5:]),name.startswith('check'))/k**.7
    selected=(f>=250)&(f<=3500)&(np.maximum(off,target)>=.00015)
    return dict(rmse_db=float(np.sqrt(np.mean((20*np.log10(np.maximum(a[selected],1e-12)/target[selected]))**2))),
        unexplained_energy=residual,peak=float(abs(y).max()),rms=float(np.sqrt(np.mean(y*y))),
        amplitudes=a.tolist(),frequencies=f.tolist(),selected=selected.tolist(),no_fit=True)
def command(plan,r,out):
    name=f"{r['family']}-{r['rate']}-{r['channels']}";input=Path(plan['inputs'][name]['path']);stem='-'.join(map(str,key(r)))
    output=out/(stem+'.f32');receipt=out/(stem+'.json');log=out/(stem+'.log')
    env=dict(os.environ);env['LD_LIBRARY_PATH']=str(Path(plan['libraries']['before' if r.get('old') else 'after']).parent)
    argv=[plan['runner'],str(input),str(output),str(receipt),str(r['rate']),str(r['channels']),str(r['block']),str(2**(r['shift']/12)),str(r['detail']),str(r['io']),str(r['repeat'])]
    start=time.perf_counter();p=subprocess.run(argv,env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,timeout=60);log.write_text(p.stdout)
    if p.returncode:raise ValueError(f'render exit {p.returncode}: {p.stdout}')
    info=json.loads(receipt.read_text());raw=np.fromfile(output,dtype='<f4').reshape(-1,r['channels'])
    if len(raw)!=2*r['rate']+info['latency'] or not np.isfinite(raw).all() or not np.any(raw):raise ValueError('invalid audio')
    if any(info[k]!=r[k] for k in ('rate','channels','detail','io','repeat')):raise ValueError('receipt identity')
    if len(info['services'])!=info['input_blocks'] or any(not np.isfinite(v) or v<0 for v in info['services']):raise ValueError('invalid timing')
    return dict(**r,status='complete',pcm_sha256=sha(output),output=str(output),receipt=str(receipt),receipt_sha256=sha(receipt),
        info=info,wall_seconds=time.perf_counter()-start,metrics=measure(raw[:2*r['rate'],0],r['family'],r['rate'],r['shift']) if r['io']==1 else None)
def prepare(args):
    args.out.mkdir(parents=True,exist_ok=False);inputs={}
    for family,rate,channels in itertools.product(FAMILIES,RATES,(1,2)):
        p=args.out/f'{family}-{rate}-{channels}.f32';p.write_bytes(fixture(family,rate,channels).astype('<f4').tobytes());inputs[p.stem]=dict(path=str(p.resolve()),sha256=sha(p))
    files={str(p):sha(p) for p in ROOT.rglob('*') if p.is_file() and '.git' not in p.parts and '__pycache__' not in p.parts}
    for p in (args.runner,args.before,args.after):files.update(metrics.binary_map(p.resolve()))
    plan=dict(schema='public-formant-detail-v1',base='086a26daec314534a4246203636bafa84d0c1373',prior_protocol='9f599ca7fcc6ecbdf4dc7105d746b8c05f56c36d',
        files=files,inputs=inputs,runner=str(args.runner.resolve()),libraries=dict(before=str(args.before.resolve()),after=str(args.after.resolve())),
        selection='order80,monophonic; already fixed in Issue67, not reselected',
        quality_attempts=96,old_comparison_attempts=16,cost_attempts=192,
        quality_gate=dict(check_improvements=6,mean_ratio=.9,new_unexplained_failures=0,new_peak_over_one=0),
        cost_gate=dict(max_ratio=1.25,median_ratio=1.10),cpu=min(os.sched_getaffinity(0)),
        environment=dict(python=sys.version,numpy=np.__version__,platform=platform.platform()),
        vendor_execution=False,independent_natural_holdout=False)
    write(args.out/'plan.json',plan);print(sha(args.out/'plan.json'))
def identity(plan):
    for p,h in plan['files'].items():
        if sha(p)!=h:raise ValueError('source/binary changed '+p)
    for v in plan['inputs'].values():
        if sha(v['path'])!=v['sha256']:raise ValueError('input changed')
def evidence_valid(rows):
    try:
        for r in rows:
            if r['status']!='complete':return False
            h=r['pcm_sha256']
            if not isinstance(h,str) or len(h)!=64 or any(x not in '0123456789abcdef' for x in h):return False
            json.dumps(r,allow_nan=False)
            info=r['info']
            if info['peak']<=0 or info['energy']<=1e-12 or info['frames']!=2*r['rate']+info['latency']:return False
            if info['input_blocks']<=0 or len(info['services'])!=info['input_blocks'] or info['service_seconds']<=0:return False
            if any(not isinstance(x,(int,float)) or not np.isfinite(x) or x<0 for x in info['services']):return False
            if r['io']==1:
                m=r['metrics']
                if m['rmse_db']<0 or not 0<=m['unexplained_energy']<=1 or m['peak']<=0 or m['rms']<=0:return False
    except (KeyError,TypeError,ValueError,OverflowError):return False
    return True

def assess_quality(rows):
    expected={(f,r,1,64,s,1,d,rep) for f,r,s,d,rep in itertools.product(FAMILIES,RATES,SHIFTS,(0,1),range(3))}
    keys=[key(r) for r in rows]
    if len(keys)!=len(set(keys)) or set(keys)!=expected:raise ValueError('missing/extra/duplicate quality rows')
    if not evidence_valid(rows):return dict(passed=False,reason='execution-or-malformed-evidence',quality_selection=None)
    groups={}
    for r in rows:groups.setdefault(key(r)[:-1],[]).append(r)
    repeats=all(len({r['pcm_sha256'] for r in v})==1 for v in groups.values())
    one={key(r)[:-1]:r for r in rows if r['repeat']==0};pairs=[]
    for f,rate,shift in itertools.product(FAMILIES,RATES,SHIFTS):
        b=one[(f,rate,1,64,shift,1,0)]['metrics'];a=one[(f,rate,1,64,shift,1,1)]['metrics']
        pairs.append(dict(family=f,rate=rate,shift=shift,before=b,after=a,improved=a['rmse_db']<b['rmse_db']))
    check=[p for p in pairs if p['family'].startswith('check')]
    before=statistics.mean(p['before']['rmse_db'] for p in check);after=statistics.mean(p['after']['rmse_db'] for p in check)
    new_bad=sum(p['before']['unexplained_energy']<=.01<p['after']['unexplained_energy'] for p in check)
    new_peak=sum(p['before']['peak']<=1<p['after']['peak'] for p in check)
    passed=repeats and sum(p['improved'] for p in check)>=6 and after<=.9*before and new_bad==0 and new_peak==0
    return dict(passed=passed,repeats_identical=repeats,check_pairs=len(check),improved=sum(p['improved'] for p in check),
        mean_before=before,mean_after=after,new_unexplained_failures=new_bad,new_peak_over_one=new_peak,pairs=pairs,
        quality_selection='limited-preview-candidate' if passed else None)
def assess_cost(rows):
    expected={('vowel120',r,ch,bl,s,io,d,rep) for r,ch,bl,s,io,d,rep in itertools.product(RATES,(1,2),(32,64),SHIFTS,(1,2),(0,1),range(3))}
    keys=[key(r) for r in rows]
    if len(keys)!=len(set(keys)) or set(keys)!=expected:raise ValueError('incomplete cost grid')
    if not evidence_valid(rows):return dict(passed=False,reason='execution-or-malformed-evidence')
    groups={}
    for r in rows:groups.setdefault(key(r)[:-1],[]).append(r)
    pairs=[]
    for rate,ch,bl,s,io in itertools.product(RATES,(1,2),(32,64),SHIFTS,(1,2)):
        key0=('vowel120',rate,ch,bl,s,io);before=groups[key0+(0,)];after=groups[key0+(1,)]
        repeat_ok=all(len({r['pcm_sha256'] for r in group})==1 for group in (before,after))
        b=statistics.median(r['info']['service_seconds']/r['info']['input_blocks'] for r in before)
        a=statistics.median(r['info']['service_seconds']/r['info']['input_blocks'] for r in after)
        if b<=0 or a<=0 or not np.isfinite(a+b):raise ValueError('invalid timing')
        pairs.append(dict(rate=rate,channels=ch,block=bl,shift=s,io=io,ratio=a/b,repeat_ok=repeat_ok,
            before_max=max(r['info']['max_service_seconds'] for r in before),after_max=max(r['info']['max_service_seconds'] for r in after),
            before_exceedances=sum(r['info']['service_period_exceedances'] for r in before),after_exceedances=sum(r['info']['service_period_exceedances'] for r in after)))
    ratios=[p['ratio'] for p in pairs];passed=max(ratios)<=1.25 and statistics.median(ratios)<=1.10 and all(p['repeat_ok'] for p in pairs)
    return dict(passed=passed,median_ratio=statistics.median(ratios),max_ratio=max(ratios),pairs=pairs,hard_realtime_qualified=False)
def run(args):
    if sha(args.plan)!=args.sha256:raise ValueError('plan sha mismatch')
    plan=json.loads(args.plan.read_text());identity(plan);args.out.mkdir(parents=True,exist_ok=False)
    if args.mode=='cost':os.sched_setaffinity(0,{plan['cpu']})
    env=dict(os.environ,LD_LIBRARY_PATH=str(Path(plan['libraries']['before' if args.mode=='old' else 'after']).parent))
    linked=subprocess.run(['ldd',plan['runner']],env=env,text=True,capture_output=True,check=True,timeout=30).stdout
    resolved=[line.split('=>',1)[1].split()[0] for line in linked.splitlines() if line.strip().startswith('libboiled_egg.so ') and '=>' in line]
    if len(resolved)!=1 or Path(resolved[0]).resolve()!=Path(plan['libraries']['before' if args.mode=='old' else 'after']).resolve():raise ValueError('wrong loaded SDK')
    (args.out/'resolved-library.txt').write_text(linked)

    specs=[]
    if args.mode in ('quality','old'):
        for f,rate,s,d,rep in itertools.product(FAMILIES,RATES,SHIFTS,(0,1) if args.mode=='quality' else (0,),range(3) if args.mode=='quality' else (0,)):
            specs.append(dict(family=f,rate=rate,channels=1,block=64,shift=s,io=1,detail=d,repeat=rep,old=args.mode=='old'))
    else:
        for rate,ch,bl,s,io,rep in itertools.product(RATES,(1,2),(32,64),SHIFTS,(1,2),range(3)):
            for d in ((0,1) if rep%2==0 else (1,0)):specs.append(dict(family='vowel120',rate=rate,channels=ch,block=bl,shift=s,io=io,detail=d,repeat=rep,old=False))
    rows=[]
    for spec in specs:
        try:r=command(plan,spec,args.out)
        except (OSError,ValueError,RuntimeError,subprocess.SubprocessError) as exc:r=dict(**spec,status='failed',error=str(exc))
        rows.append(r)
        with (args.out/'rows.jsonl').open('a') as f:f.write(json.dumps(r,allow_nan=False)+'\n')
        if len(rows)%16==0:print(len(rows),len(specs),flush=True)
    identity(plan)
    result=assess_quality(rows) if args.mode=='quality' else assess_cost(rows) if args.mode=='cost' else dict(passed=all(r['status']=='complete' for r in rows))
    result.update(plan_sha256=args.sha256,rows=rows);write(args.out/'summary.json',result);print({k:v for k,v in result.items() if k not in ('rows','pairs')});return 0 if result['passed'] else 2
if __name__=='__main__':
    p=argparse.ArgumentParser();sub=p.add_subparsers(dest='cmd',required=True)
    s=sub.add_parser('prepare');s.add_argument('--runner',type=Path,required=True);s.add_argument('--before',type=Path,required=True);s.add_argument('--after',type=Path,required=True);s.add_argument('--out',type=Path,required=True)
    s=sub.add_parser('run');s.add_argument('--plan',type=Path,required=True);s.add_argument('--sha256',required=True);s.add_argument('--mode',choices=('quality','cost','old'),required=True);s.add_argument('--out',type=Path,required=True)
    args=p.parse_args();sys.exit(prepare(args) if args.cmd=='prepare' else run(args))
