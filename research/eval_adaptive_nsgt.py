#!/usr/bin/env python3
"""Offline adaptive/fixed NSGT vs unchanged C++ and supplied TSM diagnostics.

No native-pitch baseline is substituted. Every declared cell must complete.
Fixed NSGT ablation isolates adaptation; C++ comparison also changes window,
FFT grid, linked phase policy and Fourier vs sinc resampling, explicitly noted.
"""
from __future__ import annotations
import argparse, concurrent.futures as cf, csv, hashlib, json, platform, subprocess, tempfile, time
from collections import defaultdict
from pathlib import Path
import numpy as np
import scipy
import soundfile as sf
import adaptive_nsgt as a
import eval_audio_quality as q
import eval_research_features as f
import eval_fuzzy_corpus as e
import compare_zplane_outputs as z

PROFILES=(*e.PROFILES,'nsgt-fixed','nsgt-adaptive')
FIXTURES=('harmonics','inharmonic','attack','noise0','stereo70','vowel_a')
PITCHES=(-12,-7,-3,3,7,12)

def digest(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def render(x,rate,src,dst,build,profile,mode,pitch,time_ratio):
    started=time.perf_counter()
    info={}
    if profile.startswith('nsgt-'):
        y,info=a.render(x,rate,time_ratio,pitch,a.Config(adapt=profile=='nsgt-adaptive',formant=mode))
        sf.write(dst,y,rate,subtype='FLOAT')
    else:
        cmd=f.command(build,src,dst,profile,mode,pitch,rate,'candidate')
        cmd[cmd.index('--time')+1]=format(time_ratio,'.9g')
        run=subprocess.run(cmd,capture_output=True,text=True,timeout=180)
        if run.returncode:raise RuntimeError(f'{profile}: {run.stderr}')
    y,sr=e.checked_audio(dst)
    if sr!=rate or y.shape!=(int(np.floor(len(x)*time_ratio+.5)),x.shape[1]):
        raise ValueError('render metadata/length mismatch')
    return y,dict(render_sha256=digest(dst),frames=len(y),channels=y.shape[1],
                  peak=float(np.max(np.abs(y))),render_wall_seconds=time.perf_counter()-started,
                  adapted_frames=info.get('adapted_frames',0),detected_events=info.get('detected_events',0),
                  min_window=info.get('min_window',0),max_window=info.get('max_window',0))

def synthetic(job):
    name,rate,shift,build=job
    ratio=float(np.float32(2**(shift/12)))
    maker=f.attack_fixture if name=='attack' else lambda sr,r:q.fixture(name,sr,r)
    source,_=maker(rate,1.);oracle,meta=maker(rate,ratio)
    rows=[]
    with tempfile.TemporaryDirectory(prefix='nsgt-synth-') as tmp:
        src,dst=Path(tmp)/'input.wav',Path(tmp)/'output.wav'
        sf.write(src,source,rate,subtype='FLOAT');sha=digest(src)
        for mode in (e.FORMANTS if meta['family']=='formant' else ('off',)):
            for profile in PROFILES:
                y,receipt=render(source,rate,src,dst,build,profile,mode,ratio,1.)
                rows.append(dict(suite='synthetic',condition=f'{name}/{rate}/{shift}/{mode}',fixture=name,
                    family=meta['family'],rate=rate,shift=shift,formant=mode,profile=profile,control_ratio=ratio,
                    source_sha256=sha,**receipt,**q.diagnose(y,oracle,meta,rate)))
    return rows

def natural(job):
    cell,build,refs,tests=job
    src=e.inside(refs,cell['reference_name']);source,rate=e.checked_audio(src)
    if digest(src)!=cell['reference_sha256']:raise ValueError('source changed')
    is_tsm=cell['family']=='derived'
    operation='time_stretch' if is_tsm else 'pitch_shift'
    ratio=cell['control_ratio'];pitch=1. if is_tsm else ratio;tempo=ratio if is_tsm else 1.
    mode='off' if is_tsm else 'harmonic'
    metric=z.tsm_metrics if is_tsm else z.pitch_metrics
    rows=[]
    def record(y,profile,receipt):
        rows.append(dict(suite='corpus',operation=operation,condition=cell['condition_id'],source=cell['stem'],
            family=cell['family'],rate=rate,shift=cell['pitch_semitones'],formant=mode,profile=profile,
            control_ratio=ratio,source_sha256=cell['reference_sha256'],**receipt,**metric(source,y,rate)))
    with tempfile.TemporaryDirectory(prefix='nsgt-natural-') as tmp:
        dst=Path(tmp)/'output.wav'
        if is_tsm:
            path=e.inside(tests,cell['processed_name'])
            if digest(path)!=cell['processed_sha256']:raise ValueError('provided baseline changed')
            y,sr=e.checked_audio(path)
            if sr!=rate:raise ValueError('baseline rate mismatch')
            record(y,'provided_elastique',dict(render_sha256=digest(path),frames=len(y),channels=y.shape[1],peak=float(np.max(np.abs(y)))))
        for profile in PROFILES:
            y,receipt=render(source,rate,src,dst,build,profile,mode,pitch,tempo)
            record(y,profile,receipt)
    if digest(src)!=cell['reference_sha256']:raise ValueError('source changed during run')
    return rows

def aggregate(rows,keys):
    groups=defaultdict(list)
    ignored={'rate','shift','control_ratio','frames','channels','render_wall_seconds','min_window','max_window','analyzed_partials'}
    for r in rows:groups[tuple(r[k] for k in keys)].append(r)
    result=[]
    for key,group in sorted(groups.items()):
        numeric={k for k in set.intersection(*(set(r) for r in group)) if k not in ignored and all(type(r[k]) in (float,int) for r in group)}
        values={k:dict(mean=float(np.mean([r[k] for r in group])),minimum=float(min(r[k] for r in group)),maximum=float(max(r[k] for r in group))) for k in sorted(numeric)}
        result.append(dict(zip(keys,key),n=len(group),metrics=values))
    return result

def pair(rows,baseline):
    lookup={(r['condition'],r['profile']):r for r in rows}
    if len(lookup)!=len(rows):raise ValueError('duplicate grid row')
    comparisons=[]
    for operation in sorted({r['operation'] for r in rows}):
        base=[r for r in rows if r['operation']==operation and r['profile']==baseline]
        if not base:continue
        fields=['envelope_rmse_db','onset_corr','rms_shape_db']+(['spectral_distance_db','spectral_convergence','chroma_corr'] if operation=='time_stretch' else [])
        for p in PROFILES:
            if p==baseline:continue
            for field in fields:
                groups=defaultdict(list);deltas=[]
                for b in base:
                    r=lookup[(b['condition'],p)];d=r[field]-b[field];deltas.append(d);groups[b['source']].append(d)
                cluster=np.array([np.mean(v) for _,v in sorted(groups.items())]);rng=np.random.default_rng(20260913)
                boot=cluster[rng.integers(0,len(cluster),(4000,len(cluster)))].mean(axis=1)
                sign=1 if field in ('onset_corr','chroma_corr') else -1
                comparisons.append(dict(operation=operation,profile=p,baseline=baseline,metric=field,n=len(base),
                    mean_delta=float(np.mean(deltas)),wins=int(np.sum(np.array(deltas)*sign>1e-9)),
                    source_ci95=list(map(float,np.quantile(boot,[.025,.975])))))
    return comparisons

def save_csv(path,rows):
    with path.open('w',newline='',encoding='utf-8') as s:
        w=csv.DictWriter(s,fieldnames=sorted(set.union(*(set(r) for r in rows))));w.writeheader();w.writerows(rows)

def run(args):
    if args.output.exists() or args.workers<1:raise ValueError('output must be absent; workers positive')
    binaries={p.name:digest(p) for p in (args.build/'boiled_egg_pv_rt_cli',args.build/'boiled_egg_multires_rt_cli')}
    code={p.name:digest(p) for p in (Path(__file__),Path(a.__file__),Path(q.__file__),Path(z.__file__))}
    sources,processed,cells=e.plan(args.refs,args.tests,args.catalog)
    cells=[c for c in cells if c['scope']=='target']
    jobs=[(name,rate,shift,args.build) for name in FIXTURES for rate in (48000,96000) for shift in PITCHES]
    args.output.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.nsgt-eval-',dir=args.output.parent) as tmp:
        staging=Path(tmp)/'report';staging.mkdir();syn=[];cor=[]
        with cf.ProcessPoolExecutor(max_workers=args.workers) as pool:
            for i,part in enumerate(pool.map(synthetic,jobs),1):
                syn+=part
                if i%6==0:print(f'synthetic {i}/{len(jobs)} ({len(syn)} outputs)',flush=True)
            save_csv(staging/'synthetic.csv',syn)
            for i,part in enumerate(pool.map(natural,[(c,args.build,args.refs,args.tests) for c in cells]),1):
                cor+=part
                if i%10==0:print(f'corpus {i}/{len(cells)} ({len(cor)} measurements)',flush=True)
        expected_syn=sum(3 if n.startswith('vowel') else 1 for n in FIXTURES)*12*len(PROFILES)
        expected_cor=sum(len(PROFILES)+(c['family']=='derived') for c in cells)
        if len(syn)!=expected_syn or len(cor)!=expected_cor:raise ValueError('incomplete grid')
        if any(digest(args.build/n)!=h for n,h in binaries.items()) or any(digest(Path(__file__).parent/n)!=h for n,h in code.items()):raise ValueError('code/binary changed')
        save_csv(staging/'corpus.csv',cor)
        report=dict(schema='boiled-egg.nsgt-comparison.v1',profiles=PROFILES,synthetic_rows=len(syn),corpus_rows=len(cor),
            candidate_renders=len(syn)+sum(r['profile']!='provided_elastique' for r in cor),sources=sources,
            binary_sha256=binaries,analysis_sha256=code,catalog_sha256=digest(args.catalog),
            versions=dict(python=platform.python_version(),numpy=np.__version__,scipy=scipy.__version__,soundfile=sf.__version__),
            synthetic=aggregate(syn,('family','rate','profile','formant')),
            corpus=aggregate(cor,('operation','profile')),
            paired=pair(cor,'transient')+pair(cor,'nsgt-fixed')+pair(cor,'provided_elastique'),
            files={p.name:digest(p) for p in staging.iterdir()},listening_status='not_listened',native_pitch_baseline=False,
            limitations='Offline SELEBI-inspired adaptation, not exact reproduction or realtime SDK. Fixed ablation is the same NSGT kernel without variable windows. Comparisons to C++ additionally change Hann window, FFT grid, phase policy and Fourier resampling. Supplied TSM baseline version unspecified; no derived pitch is called native. Source-cluster intervals descriptive, not perceptual significance; no MOS transfer or profile selection per file.')
        (staging/'summary.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
        staging.rename(args.output)
    return report

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('build','refs','tests','catalog','output'):p.add_argument('--'+n,type=Path,required=True)
    p.add_argument('--workers',type=int,default=3)
    r=run(p.parse_args());print(r['synthetic_rows'],r['corpus_rows'],flush=True)
