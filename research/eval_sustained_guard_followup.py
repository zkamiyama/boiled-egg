#!/usr/bin/env python3
"""Paired follow-up of the opt-in frequency-coherence guard, not a native benchmark.

Use identical input WAVs for every compared renderer. The four seeded oscillator
banks are held out from the original two-fixture pilot; no thresholds are fitted.
Scheduled and immediate equivalence is checked separately by CTest/tonal gates.
"""
from __future__ import annotations
import argparse, concurrent.futures as cf, csv, hashlib, json, platform, subprocess, tempfile
from collections import defaultdict
from pathlib import Path
import numpy as np
import soundfile as sf
import eval_audio_quality as q
import eval_research_features as f
import eval_fuzzy_corpus as e
import compare_zplane_outputs as z

SHIFTS=(-12,-7,-3,0,3,7,12)
FIXTURES=(*q.FIXTURES, 'unseen0','unseen1','unseen2','unseen3')
VARIANTS=(('general','baseline'),('transient','baseline'),('fuzzy','baseline'),
          ('fuzzy-noise','baseline'),('fuzzy','guard'),('fuzzy-noise','guard'))


def oscillator_bank(seed: int, rate: int, pitch: float):
    rng=np.random.default_rng(93173+seed)
    # >= 90 Hz source separation; independent phases and a 24-dB amplitude span.
    frequencies=np.cumsum(rng.uniform(90,360,14))+73
    amplitudes=10**(rng.uniform(-24,0,14)/20)
    phases=rng.uniform(-np.pi,np.pi,14)
    t=np.arange(rate*2)/rate
    x=sum(a*np.sin(2*np.pi*fr*pitch*t+ph) for a,fr,ph in zip(amplitudes,frequencies,phases))
    x*=.1/np.sqrt(np.mean(x*x))
    return x.astype('float32')[:,None],dict(family='partials',frequencies=frequencies*pitch)


def fixture(name, rate, pitch):
    if name.startswith('unseen'):return oscillator_bank(int(name[-1]),rate,pitch)
    if name=='attack':return f.attack_fixture(rate,pitch)
    return q.fixture(name,rate,pitch)


def launch(cmd, dest, rate, frames, channels):
    p=subprocess.run(cmd,capture_output=True,text=True,timeout=120)
    if p.returncode:raise RuntimeError(p.stderr)
    y,sr=e.checked_audio(dest)
    if sr!=rate or y.shape!=(frames,channels):raise ValueError('render metadata mismatch')
    return y,e.fingerprint(dest)


def synthetic_job(job):
    name,rate,shift,baseline,guard=job
    pitch=float(np.float32(2**(shift/12)))
    x,_=fixture(name,rate,1);ideal,meta=fixture(name,rate,pitch);rows=[]
    with tempfile.TemporaryDirectory(prefix='guard-followup-') as tmp:
        src,dst=Path(tmp)/'input.wav',Path(tmp)/'render.wav'
        sf.write(src,x,rate,subtype='FLOAT');digest=e.fingerprint(src)
        for mode in (e.FORMANTS if meta['family']=='formant' else ('off',)):
            for profile,variant in VARIANTS:
                build=baseline if variant=='baseline' else guard
                cmd=f.command(build,src,dst,profile,mode,pitch,rate,'candidate')
                y,sha=launch(cmd,dst,rate,len(x),x.shape[1])
                row=dict(fixture=name,family=meta['family'],rate=rate,shift=shift,formant=mode,
                    profile=profile,variant=variant,control_ratio=pitch,frames=len(y),channels=y.shape[1],
                    input_sha256=digest,render_sha256=sha,peak=float(np.max(np.abs(y))),
                    **q.diagnose(y,ideal,meta,rate))
                if shift==0:row['unity_error_db']=float(q.m.db(np.mean((y-x)**2)/np.mean(x.astype(float)**2)))
                rows.append(row)
        if e.fingerprint(src)!=digest:raise ValueError('source mutated')
    return rows


def corpus_job(job):
    cell,refs,tests,baseline,guard=job
    src=e.inside(refs,cell['reference_name']);x,rate=e.checked_audio(src)
    if e.fingerprint(src)!=cell['reference_sha256']:raise ValueError('reference hash mismatch')
    rows=[]
    with tempfile.TemporaryDirectory(prefix='guard-corpus-') as tmp:
        dst=Path(tmp)/'render.wav'
        if cell['family']=='derived':
            test=e.inside(tests,cell['processed_name']);control,sr=e.checked_audio(test)
            if sr!=rate or e.fingerprint(test)!=cell['processed_sha256']:raise ValueError('baseline mismatch')
            operations=(('time_stretch','off'),)
            target=len(control)
            values=z.tsm_metrics(x,control,rate)
            rows.append(dict(operation='time_stretch',source=cell['stem'],condition=cell['condition_id'],
                ratio=cell['control_ratio'],formant='off',profile='provided_elastique',variant='provided',
                frames=target,rate=rate,channels=x.shape[1],input_sha256=cell['reference_sha256'],
                render_sha256=cell['processed_sha256'],peak=float(np.max(np.abs(control))),**values))
        else:
            operations=(('exact_pitch','off'),('exact_pitch','harmonic'))
        for operation,mode in operations:
            for profile,variant in VARIANTS:
                build=baseline if variant=='baseline' else guard
                pitch=1. if operation=='time_stretch' else cell['control_ratio']
                cmd=f.command(build,src,dst,profile,mode,pitch,rate,'candidate')
                frames=len(x)
                if operation=='time_stretch':
                    cmd[cmd.index('--time')+1]=format(cell['control_ratio'],'.9g')
                    frames=round(len(x)*cell['control_ratio'])
                y,sha=launch(cmd,dst,rate,frames,x.shape[1])
                values=z.tsm_metrics(x,y,rate) if operation=='time_stretch' else z.pitch_metrics(x,y,rate)
                # Off pitch envelope is intentionally not an unshifted-timbre target.
                if operation=='exact_pitch' and mode=='off':values.pop('envelope_rmse_db')
                rows.append(dict(operation=operation,source=cell['stem'],condition=cell['condition_id'],
                    ratio=cell['control_ratio'],formant=mode,profile=profile,variant=variant,
                    frames=frames,rate=rate,channels=x.shape[1],input_sha256=cell['reference_sha256'],
                    render_sha256=sha,peak=float(np.max(np.abs(y))),**values))
    return rows


def paired_summary(rows, keys, metrics, source_key=None):
    groups=defaultdict(dict)
    for r in rows:
        k=tuple(r[x] for x in keys)
        if r['variant'] in groups[k]:raise ValueError('duplicate paired cell')
        groups[k][r['variant']]=r
    result={}
    for metric in metrics:
        pairs=[(d['guard'],d['baseline']) for d in groups.values() if 'guard' in d and 'baseline' in d and metric in d['guard']]
        if not pairs:continue
        differences=np.array([a[metric]-b[metric] for a,b in pairs])
        record=dict(n=len(pairs),baseline_mean=float(np.mean([b[metric] for a,b in pairs])),
            guard_mean=float(np.mean([a[metric] for a,b in pairs])),delta=float(differences.mean()),
            less=int((differences < -1e-9).sum()),greater=int((differences > 1e-9).sum()))
        if source_key:
            clusters=defaultdict(list)
            for (a,b),v in zip(pairs,differences):clusters[a[source_key]].append(v)
            means=np.array([np.mean(v) for _,v in sorted(clusters.items())])
            rng=np.random.default_rng(93173)
            draws=means[rng.integers(0,len(means),size=(4000,len(means)))].mean(axis=1)
            record.update(sources=len(means),ci95=list(map(float,np.quantile(draws,[.025,.975]))))
        result[metric]=record
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for k in ('baseline','guard','output'):p.add_argument('--'+k,type=Path,required=True)
    p.add_argument('--suite',choices=('synthetic','corpus'),required=True)
    for k in ('refs','tests','catalog'):p.add_argument('--'+k,type=Path)
    p.add_argument('--workers',type=int,default=3)
    a=p.parse_args()
    if a.output.exists() or a.workers<1:raise ValueError('new output and positive workers required')
    hashes={f'{label}/{name}':e.fingerprint(b/name) for label,b in [('baseline',a.baseline),('guard',a.guard)]
        for name in ('boiled_egg_pv_rt_cli','boiled_egg_multires_rt_cli')}
    dependencies={Path(m.__file__).name:e.fingerprint(Path(m.__file__)) for m in (q,f,e,z)}
    dependencies[Path(__file__).name]=e.fingerprint(Path(__file__))
    if a.suite=='synthetic':
        jobs=[(n,r,s,a.baseline,a.guard) for n in FIXTURES for r in (48000,96000) for s in SHIFTS]
        fn=synthetic_job
        expected=(len(FIXTURES)+4)*2*len(SHIFTS)*len(VARIANTS)
    else:
        if not all((a.refs,a.tests,a.catalog)):raise ValueError('all corpus paths required')
        sources,processed,cells=e.plan(a.refs,a.tests,a.catalog)
        cells=[c for c in cells if c['scope']=='target']
        jobs=[(c,a.refs,a.tests,a.baseline,a.guard) for c in cells];fn=corpus_job
        expected=sum(2*len(VARIANTS) if c['family']=='exact' else len(VARIANTS)+1 for c in cells)
    rows=[]
    a.output.parent.mkdir(parents=True,exist_ok=True)
    with cf.ProcessPoolExecutor(a.workers) as pool:
        for i,part in enumerate(pool.map(fn,jobs),1):
            rows+=part
            if i%10==0:print(f'{a.suite} {i}/{len(jobs)} ({len(rows)} rows)',flush=True)
    if len(rows)!=expected:raise ValueError(f'incomplete grid: {len(rows)} != {expected}')
    for key,digest in hashes.items():
        label,name=key.split('/');build=a.baseline if label=='baseline' else a.guard
        if e.fingerprint(build/name)!=digest:raise ValueError('renderer changed')
    a.output.mkdir()
    q.write_csv(a.output/'measurements.csv',rows)
    (a.output/'summary.json').write_text(json.dumps(dict(suite=a.suite,rows=len(rows),
        actual_cpp_renders=sum(r['variant']!='provided' for r in rows),executables=hashes,analysis=dependencies,
        measurements_sha256=e.fingerprint(a.output/'measurements.csv'),python=platform.python_version(),
        numpy=np.__version__,notes='Paired diagnostics; no native pitch rendering, MOS or promotion. '
        'Independent oscillator banks use seeds 93173..93176. No perceptual quality thresholds.'),indent=2)+'\n')
    print('complete',len(rows),flush=True)

if __name__=='__main__':main()
