"""Matched-input study of three declared offline NSGT ablations."""
import argparse, sys, json, concurrent.futures as cf
from pathlib import Path
import numpy as np
import soundfile as sf
import selective_nsgt_v2 as n
import eval_sustained_guard_followup as s
import eval_audio_quality as q
import compare_zplane_outputs as z
import eval_fuzzy_corpus as e

CONFIGS={'fixed':n.Config(adaptive=False),'adaptive':n.Config(),
         'adaptive-coherent':n.Config(coherence=True)}

def job(item):
 name,rate,shift,operation=item
 pitch=float(np.float32(2**(shift/12)));source,_=s.fixture(name,rate,1.);rows=[]
 for label,cfg in CONFIGS.items():
  if operation=='pitch':
   ideal,meta=s.fixture(name,rate,pitch);y,stats=n.render(source,rate,1,pitch,cfg)
   values=q.diagnose(y,ideal,meta,rate)
  else:
   y,stats=n.render(source,rate,pitch,1,cfg)
   if name=='attack':
    # Attack shape is not stretched, only its start times; define this explicitly.
    _,meta=s.fixture(name,rate,1.)
    meta['starts']=[v*pitch for v in meta['starts']]
    values=q.m.attacks(y,rate,meta['starts'],meta['duration'])
   else:values=z.tsm_metrics(source,y,rate)
  rows.append(dict(fixture=name,rate=rate,shift=shift,operation=operation,variant=label,
   output_frames=len(y),peak=float(np.max(np.abs(y))),input_pcm_sha256=__import__('hashlib').sha256(source.tobytes()).hexdigest(),
   **stats,**values))
 return rows

def corpus_job(item):
 cell,refs,tests=item
 source,sr=e.checked_audio(refs/cell['reference_name']);control,tr=e.checked_audio(tests/cell['processed_name'])
 if e.fingerprint(refs/cell['reference_name'])!=cell['reference_sha256'] or e.fingerprint(tests/cell['processed_name'])!=cell['processed_sha256'] or sr!=tr:
  raise ValueError('source/baseline mismatch')
 rows=[]
 for label,cfg in CONFIGS.items():
  y,stats=n.render(source,sr,cell['control_ratio'],1.,cfg)
  if len(y)!=round(len(source)*cell['control_ratio']):raise ValueError('duration')
  y=y.astype('float32').astype('float64')
  rows.append(dict(source=cell['stem'],condition=cell['condition_id'],ratio=cell['control_ratio'],variant=label,
   input_sha256=cell['reference_sha256'],output_frames=len(y),peak=float(np.max(np.abs(y))),
   output_pcm_sha256=__import__('hashlib').sha256(y.astype('float32').tobytes()).hexdigest(),
   **stats,**z.tsm_metrics(source,y,sr)))
 rows.append(dict(source=cell['stem'],condition=cell['condition_id'],ratio=cell['control_ratio'],variant='provided_elastique',
  input_sha256=cell['reference_sha256'],output_frames=len(control),peak=float(np.max(np.abs(control))),
  render_sha256=cell['processed_sha256'],**z.tsm_metrics(source,control,sr)))
 return rows

if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True)
 p.add_argument('--suite',choices=('synthetic','corpus'),default='synthetic')
 for k in ('refs','tests','catalog'):p.add_argument('--'+k,type=Path)
 p.add_argument('--workers',type=int,default=3);a=p.parse_args()
 if a.output.exists() or a.workers<1:raise ValueError('new output and positive workers required')
 root=a.output
 if a.suite=='synthetic':
  jobs=[(name,rate,shift,'pitch') for name in ('harmonics','inharmonic','unseen0','attack','noise0','stereo70')
        for rate in (48000,96000) for shift in (-12,-7,-3,3,7,12)]
  jobs += [('attack',rate,shift,'time_stretch') for rate in (48000,96000) for shift in (3,7,12)]
  fn=job;expected=len(jobs)*len(CONFIGS)
 else:
  if not all((a.refs,a.tests,a.catalog)):raise ValueError('corpus paths required')
  _,_,cells=e.plan(a.refs,a.tests,a.catalog)
  jobs=[(c,a.refs,a.tests) for c in cells if c['family']=='derived' and c['scope']=='target']
  fn=corpus_job;expected=len(jobs)*(len(CONFIGS)+1)
 rows=[]
 with cf.ProcessPoolExecutor(a.workers) as pool:
  for i,part in enumerate(pool.map(fn,jobs),1):
   rows+=part
   if i%10==0:print(i,len(jobs),flush=True)
 if len(rows)!=expected:raise ValueError('incomplete grid')
 root.mkdir(parents=True)
 q.write_csv(root/'measurements.csv',rows)
 (root/'summary.json').write_text(json.dumps(dict(rows=len(rows),algorithm='SELEBI-inspired adaptation, NOT exact reproduction',
   implementation_sha256=e.fingerprint(Path(n.__file__)),script_sha256=e.fingerprint(Path(__file__)),
   measurements_sha256=e.fingerprint(root/'measurements.csv'),native_baseline=False,
   config={k:vars(v) for k,v in CONFIGS.items()}),indent=2)+'\n')
 print('complete',len(rows))
