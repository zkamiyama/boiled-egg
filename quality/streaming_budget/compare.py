#!/usr/bin/env python3
"""Complete-grid and byte-level before/after check; baseline faults stay visible."""
from __future__ import annotations
import argparse,array,csv,hashlib,json,math,sys
from pathlib import Path
COUNTS={'repro':36,'corners':2424,'partition':90,'dynamic':72,'pressure':18,'invalid':1,'noalloc':9}
KEYS=('mode','rate','channels','quality','input','block','time','pitch')
def sha(data):return hashlib.sha256(data).hexdigest()
def compare(original:Path,candidate:Path)->dict:
 report={'correct_length_unchanged_pcm':0,'overlong_fixed':0,'stalls_fixed':0,'total':0,'nonempty':0,'outputs':[],'failures':[],'quality_selection':None}
 for mode,count in COUNTS.items():
  a=list(csv.DictReader((original/f'{mode}.csv').open()));b=list(csv.DictReader((candidate/f'{mode}.csv').open()))
  if len(a)!=count or len(b)!=count:raise ValueError('incomplete '+mode)
  for records in [a,b]:
   keys=[tuple(v[k] for k in KEYS) for v in records]
   if len(set(keys))!=len(keys):raise ValueError('duplicate case')
  for i,(x,y) in enumerate(zip(a,b),1):
   if any(x[k]!=y[k] for k in KEYS):raise ValueError('changed case grid')
   if y['error'] or int(y['violations']) or int(y['allocations']) or y['output']!=y['target']:
    report['failures'].append({'mode':mode,'row':i,'reason':'candidate contract failure'});continue
   raw=(candidate/mode/f'{i}.f32').read_bytes();n=int(y['output'])*int(y['channels'])
   if len(raw)!=n*4:raise ValueError('PCM length')
   values=array.array('f');values.frombytes(raw)
   if sys.byteorder!='little':values.byteswap()
   if not all(math.isfinite(v) for v in values) or (n and not any(values)):
    raise ValueError('nonfinite or silent PCM')
   data={'mode':mode,'row':i,'case':{k:y[k] for k in KEYS},'candidate_sha256':sha(raw),'frames':int(y['output'])}
   if x['error']:
    if (original/mode/f'{i}.f32').exists():raise ValueError('failed baseline published PCM')
    report['stalls_fixed']+=1;data['baseline_error']=x['error']
   else:
    before=(original/mode/f'{i}.f32').read_bytes()
    if len(before)!=4*int(x['output'])*int(x['channels']):raise ValueError('baseline PCM length')
    data['baseline_sha256']=sha(before)
    if x['output']==x['target']:
     if before!=raw:report['failures'].append({'mode':mode,'row':i,'reason':'previously correct PCM changed'})
     else:report['correct_length_unchanged_pcm']+=1
    else:
     if int(x['output'])<=int(x['target']):raise ValueError('unclassified original length error')
     # A comparison of original prefix is diagnostic, not output trimming.
     data['original_prefix_identical']=before[:len(raw)]==raw
     report['overlong_fixed']+=1
   report['nonempty']+=bool(raw);report['total']+=1;report['outputs'].append(data)
 if report['total']!=sum(COUNTS.values()):report['failures'].append({'reason':'not all requested cases completed'})
 return report
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('original',type=Path);p.add_argument('candidate',type=Path);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
 if a.output.exists():raise ValueError('new report required')
 r=compare(a.original,a.candidate);a.output.write_text(json.dumps(r,indent=2,allow_nan=False)+'\n')
 print(json.dumps({k:v for k,v in r.items() if k!='outputs'},indent=2));raise SystemExit(1 if r['failures'] else 0)
