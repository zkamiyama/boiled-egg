#!/usr/bin/env python3
"""Fixed Linux host benchmark: sequential, paired, pinned, no best-run selection."""
from __future__ import annotations
import argparse,hashlib,json,math,os,platform,statistics,subprocess,sys,time
from pathlib import Path

def sha(p:Path)->str:return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,v):p.write_text(json.dumps(v,indent=2,allow_nan=False)+'\n')
def load(p):return json.loads(p.read_text())

def prepare(root:Path,output:Path):
 output.mkdir(parents=True,exist_ok=False)
 source=root/'repo';paths=subprocess.check_output(['git','-C',str(source),'ls-files','--cached','--others','--exclude-standard','-z']).decode().strip('\0').split('\0')
 files={str(source/p):sha(source/p) for p in paths}
 for version in ('original','before','after'):
  p=root/f'build-{version}/libboiled_egg.so';files[str(p)]=sha(p)
  linked=subprocess.check_output(['ldd',str(p)],text=True)
  (output/(version+'-ldd.txt')).write_text(linked)
  for line in linked.splitlines():
   if '=>' in line:
    name=line.split('=>',1)[1].split()[0]
    if Path(name).is_file():files[name]=sha(Path(name))
 exe=root/'client/wsola_cost_bench';files[str(exe)]=sha(exe)
 plan={'schema':'wsola-cost-v1','executable':str(exe),'root':str(root),'files':files,'cases':56,'repeats':3,
       'versions':['original','before','after'],'order_rule':'rotate version order by case+repeat modulo3',
       'cpu':min(os.sched_getaffinity(0)),'affinity_available':sorted(os.sched_getaffinity(0)),
       'platform':platform.platform(),'python':sys.version,'cpp':subprocess.check_output(['g++','--version'],text=True),
       'correctness_reference':'local841b1b185be57a4979f7188f2789b1b1b1351848',
       'primary_metrics':['native_per_input_block','wall_seconds','thread_seconds'],
       'primary_gate':'before/after exact PCM, median of 3 at each setting; median paired cost ratio <=1 and maximum <=1.25',
       'notes':'original main failures remain failures, no speed ratio for an incomplete original; no hard-RT claim'}
 write(output/'plan.json',plan)
 return sha(output/'plan.json')

def verify(plan):
 for p,h in plan['files'].items():
  if sha(Path(p))!=h:raise ValueError('changed source/binary/dependency '+p)

def run(planpath:Path,digest:str,output:Path):
 if sha(planpath)!=digest:raise ValueError('wrong plan')
 p=load(planpath);verify(p);output.mkdir(parents=True,exist_ok=False);root=Path(p['root']);rows=[]
 versions=p['versions']
 for index in range(p['cases']):
  for repeat in range(p['repeats']):
   offset=(index+repeat)%3;order=versions[offset:]+versions[:offset]
   for version in order:
    folder=output/f'{index:02d}-{repeat}-{version}';folder.mkdir()
    env=dict(os.environ,LD_LIBRARY_PATH=str(root/f'build-{version}'))
    # taskset changes only this child, not the user's session or global CPU state.
    args=['taskset','-c',str(p['cpu']),p['executable'],str(index),str(folder)]
    try:
     result=subprocess.run(args,env=env,text=True,capture_output=True,timeout=40)
     (folder/'stdout.txt').write_text(result.stdout);(folder/'stderr.txt').write_text(result.stderr)
     row=dict(case=index,repeat=repeat,version=version,returncode=result.returncode,status='failed',folder=folder.name)
     if result.returncode==0:
      metrics=json.loads(result.stdout);assert metrics['case']==index
      row.update(status='complete',metrics=metrics,pcm_sha256=sha(folder/'1.f32'),calls_sha256=sha(folder/'calls.f64'))
    except (subprocess.SubprocessError,ValueError,AssertionError) as exc:
     row=dict(case=index,repeat=repeat,version=version,status='failed',error=str(exc),folder=folder.name)
    rows.append(row)
    with (output/'rows.jsonl').open('a') as f:f.write(json.dumps(row,allow_nan=False)+'\n')
  print(f'{index+1}/56 settings',flush=True)
 verify(p);write(output/'raw.json',{'plan_sha256':digest,'rows':rows})
 result=assess(rows);write(output/'summary.json',result);return result

def assess(rows):
 required={(i,j,k) for i in range(56) for j in range(3) for k in ('original','before','after')}
 keys=[(r['case'],r['repeat'],r['version']) for r in rows]
 if len(set(keys))!=len(keys) or set(keys)!=required:raise ValueError('incomplete/duplicate grid')
 for r in rows:
  if r['status']=='complete':
   h=r.get('pcm_sha256','')
   if len(h)!=64 or any(c not in '0123456789abcdef' for c in h):raise ValueError('invalid PCM identity')
   for metric in ('native_per_input_block','wall_seconds','thread_seconds','fixture_create_seconds'):
    value=r.get('metrics',{}).get(metric)
    if not isinstance(value,(float,int)) or not math.isfinite(value) or value<=0:raise ValueError('invalid timing receipt')
 by={k:r for k,r in zip(keys,rows)};failure=[];cells=[]
 for i in range(56):
  for j in range(3):
   a,b=by[i,j,'before'],by[i,j,'after']
   if any(x['status']!='complete' for x in (a,b)) or a.get('pcm_sha256')!=b.get('pcm_sha256'):
    failure.append({'case':i,'repeat':j,'reason':'primary failure/PCM changed'})
  for version in ('before','after'):
   rr=[by[i,j,version] for j in range(3)]
   if len({x.get('pcm_sha256') for x in rr})!=1:failure.append({'case':i,'reason':'repeat PCM changed'})
  if any(by[i,j,v]['status']!='complete' for j in range(3) for v in ('before','after')):continue
  cell={'case':i,'io':by[i,0,'before']['metrics']['io'],'ratios':{},'raw_80_percent_exceedances':{}}
  for v in ('original','before','after'):
   if all(by[i,j,v]['status']=='complete' for j in range(3)):
    cell[v]={m:statistics.median(by[i,j,v]['metrics'][m] for j in range(3)) for m in ('native_per_input_block','wall_seconds','thread_seconds','fixture_create_seconds')}
    cell['raw_80_percent_exceedances'][v]=[by[i,j,v]['metrics']['over_80_percent'] for j in range(3)]
    if v=='original':cell['original_pcm_matches_after']=all(by[i,j,v]['pcm_sha256']==by[i,j,'after']['pcm_sha256'] for j in range(3))
  for m in ('native_per_input_block','wall_seconds','thread_seconds'):
   cell['ratios'][m]=cell['after'][m]/cell['before'][m]
  cells.append(cell)
 result={'settings':len(cells),'trials':len(rows),'primary_failures':failure,'original_failures':sum(r['status']!='complete' for r in rows if r['version']=='original'),'cells':cells,'quality_selection':None}
 for scope in ('all','streaming','realtime'):
  cc=[c for c in cells if scope=='all' or c['io']==scope];s={}
  for metric in ('native_per_input_block','wall_seconds','thread_seconds'):
   ratios=[c['ratios'][metric] for c in cc]
   if not ratios:
    s[metric]=None;continue
   s[metric]={'median':statistics.median(ratios),'max':max(ratios),'improved':sum(x<1 for x in ratios),'within_1p25':sum(x<=1.25 for x in ratios),'count':len(ratios)}
  result[scope]=s
 result['same_output_pass']=not failure and len(cells)==56
 gate=result['all']['native_per_input_block']
 result['cost_gate_pass']=bool(gate and gate['median']<=1 and gate['max']<=1.25)
 result['primary_pass']=result['same_output_pass'] and result['cost_gate_pass']
 return result

def main():
 a=argparse.ArgumentParser();sub=a.add_subparsers(dest='cmd',required=True)
 b=sub.add_parser('prepare');b.add_argument('--root',type=Path,required=True);b.add_argument('--output',type=Path,required=True)
 b=sub.add_parser('run');b.add_argument('--plan',type=Path,required=True);b.add_argument('--sha256',required=True);b.add_argument('--output',type=Path,required=True)
 args=a.parse_args()
 if args.cmd=='prepare':print(prepare(args.root,args.output));return
 result=run(args.plan,args.sha256,args.output);print(json.dumps({k:v for k,v in result.items() if k!='cells'},indent=2));raise SystemExit(0 if result['primary_pass'] else 2)
if __name__=='__main__':main()
