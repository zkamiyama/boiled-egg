#!/usr/bin/env python3
"""Fixed three-way phase-owner study. No native pitch/MOS or best-of selector.

Development sources are sorted positions 0,4,8,12,16. All other sources are the
within-iteration confirmation subset, not a new dataset or pristine holdout.
Use baseline, old guard, and neighbor-refined guard builds of the SAME runtime.
"""
from __future__ import annotations
import argparse
import concurrent.futures as cf
import csv
import hashlib
import json
import platform
import subprocess
import tempfile
from pathlib import Path
import numpy as np
import soundfile as sf
import eval_fuzzy_corpus as e
import eval_research_features as f
import eval_audio_quality as q
import eval_sustained_guard_followup as s
import compare_zplane_outputs as z

VARIANTS=('baseline','guard','refined')
PITCHES=(-12,-7,-3,0,3,7,12)
FIXTURES=(*q.FIXTURES,'unseen0','unseen1','unseen2','unseen3')


def render(build,source,dest,ratio,rate,mode,operation='pitch'):
    cmd=f.command(build,source,dest,'fuzzy',mode,1. if operation=='time_stretch' else ratio,rate,'candidate')
    if operation=='time_stretch':cmd[cmd.index('--time')+1]=format(ratio,'.9g')
    else:
        cmd[cmd.index('--block')+1]='32'
        cmd+=['--execution','scheduled','--simd','on']
    proc=subprocess.run(cmd,capture_output=True,text=True,timeout=120)
    if proc.returncode:raise RuntimeError(f'{build.name}: {proc.stderr}')
    audio,sr=e.checked_audio(dest)
    if sr!=rate:raise ValueError('wrong output sample rate')
    return audio,e.fingerprint(dest)


def synthetic(job):
    name,rate,shift,builds=job
    ratio=float(np.float32(2**(shift/12)))
    x,_=s.fixture(name,rate,1.);oracle,meta=s.fixture(name,rate,ratio)
    rows=[]
    with tempfile.TemporaryDirectory(prefix='owner-synthetic-') as tmp:
        src,dst=Path(tmp)/'source.wav',Path(tmp)/'result.wav'
        sf.write(src,x,rate,subtype='FLOAT');digest=e.fingerprint(src)
        for mode in (e.FORMANTS if meta['family']=='formant' else ('off',)):
            for label,build in zip(VARIANTS,builds):
                y,sha=render(build,src,dst,ratio,rate,mode)
                if y.shape!=x.shape:raise ValueError('synthetic shape mismatch')
                row=dict(fixture=name,family=meta['family'],rate=rate,shift=shift,formant=mode,variant=label,
                    ratio=ratio,frames=len(y),channels=y.shape[1],input_sha256=digest,render_sha256=sha,
                    peak=float(np.max(np.abs(y))),**q.diagnose(y,oracle,meta,rate))
                if shift==0:row['unity_error_db']=float(q.m.db(np.mean((y-x)**2)/np.mean(x.astype(float)**2)))
                rows.append(row)
        if e.fingerprint(src)!=digest:raise ValueError('source changed')
    return rows


def natural(job):
    cell,refs,tests,builds,split=job
    src=e.inside(refs,cell['reference_name']);x,rate=e.checked_audio(src)
    if e.fingerprint(src)!=cell['reference_sha256']:raise ValueError('source fingerprint mismatch')
    operation='time_stretch' if cell['family']=='derived' else 'exact_pitch'
    ratio=cell['control_ratio'];rows=[]
    common=dict(source=cell['stem'],condition=cell['condition_id'],operation=operation,split=split,
                ratio=ratio,shift=cell['pitch_semitones'],rate=rate,input_sha256=cell['reference_sha256'])
    if operation=='time_stretch':
        src_baseline=e.inside(tests,cell['processed_name']);provided,sr=e.checked_audio(src_baseline)
        if sr!=rate or e.fingerprint(src_baseline)!=cell['processed_sha256']:raise ValueError('provided baseline mismatch')
        rows.append(dict(**common,formant='off',variant='provided_elastique',frames=len(provided),channels=provided.shape[1],
            render_sha256=cell['processed_sha256'],peak=float(np.max(np.abs(provided))),**z.tsm_metrics(x,provided,rate)))
    with tempfile.TemporaryDirectory(prefix='owner-corpus-') as tmp:
        dst=Path(tmp)/'render.wav'
        for mode in (('off',) if operation=='time_stretch' else e.FORMANTS):
            for label,build in zip(VARIANTS,builds):
                y,sha=render(build,src,dst,ratio,rate,mode,'time_stretch' if operation=='time_stretch' else 'pitch')
                expected=round(len(x)*ratio) if operation=='time_stretch' else len(x)
                if y.shape!=(expected,x.shape[1]):raise ValueError('corpus shape mismatch')
                metric=(z.tsm_metrics if operation=='time_stretch' else z.pitch_metrics)(x,y,rate)
                if operation=='exact_pitch' and mode=='off':metric.pop('envelope_rmse_db')
                rows.append(dict(**common,formant=mode,variant=label,frames=len(y),channels=y.shape[1],
                            render_sha256=sha,peak=float(np.max(np.abs(y))),**metric))
    if e.fingerprint(src)!=cell['reference_sha256']:raise ValueError('reference mutated')
    return rows


def validate_rows(rows,expected_keys,keys):
    actual=[]
    for row in rows:
        actual.append(tuple(row[k] for k in keys))
        for value in row.values():
            if isinstance(value,(float,np.floating)) and not np.isfinite(value):raise ValueError('nonfinite measurement')
    if len(actual)!=len(set(actual)) or set(actual)!=set(expected_keys):raise ValueError('duplicate/incomplete/unexpected grid')


def write_csv(path,rows):
    fields=sorted(set().union(*(r.keys() for r in rows)))
    with path.open('w',newline='',encoding='utf-8') as stream:
        writer=csv.DictWriter(stream,fieldnames=fields);writer.writeheader();writer.writerows(rows)



def cached_run(cache, manifest, fn, jobs, workers):
    serialized=json.dumps(manifest,sort_keys=True,separators=(',',':'))
    identity=hashlib.sha256(serialized.encode()).hexdigest()
    cache.mkdir(parents=True,exist_ok=True)
    header=cache/'manifest.json'
    if header.exists():
        if header.read_text()!=serialized+'\n':raise ValueError('cache identity/configuration mismatch')
    elif any(cache.iterdir()):raise ValueError('unbound nonempty cache')
    else:header.write_text(serialized+'\n')
    results={};missing=[]
    for i,job in enumerate(jobs):
        path=cache/f'cell-{i:04d}.json'
        if path.exists():
            blob=json.loads(path.read_text());payload=json.dumps(blob['rows'],sort_keys=True,separators=(',',':'))
            if blob['identity']!=identity or blob['index']!=i or blob['sha256']!=hashlib.sha256(payload.encode()).hexdigest():
                raise ValueError('cache cell integrity mismatch')
            results[i]=blob['rows']
        else:missing.append((i,job))
    with cf.ProcessPoolExecutor(workers) as pool:
        for done,((i,_),rows) in enumerate(zip(missing,pool.map(fn,[j for i,j in missing])),1):
            payload=json.dumps(rows,sort_keys=True,separators=(',',':'))
            value=dict(identity=identity,index=i,rows=rows,sha256=hashlib.sha256(payload.encode()).hexdigest())
            temp=cache/f'.cell-{i:04d}.tmp';temp.write_text(json.dumps(value,allow_nan=False)+'\n')
            temp.replace(cache/f'cell-{i:04d}.json');results[i]=rows
            if done%10==0:print(f'new cells {done}/{len(missing)}, cached {len(jobs)-len(missing)}',flush=True)
    return [r for i in range(len(jobs)) for r in results[i]]


def run(a):
    if a.workers<1 or a.output.exists():raise ValueError('positive workers and absent output required')
    builds=[getattr(a,label).resolve(strict=True) for label in VARIANTS]
    executable_hashes={label:e.fingerprint(build/'boiled_egg_pv_rt_cli') for label,build in zip(VARIANTS,builds)}
    dependencies={Path(m.__file__).resolve():e.fingerprint(Path(m.__file__)) for m in (e,f,q,s,z,q.m)}
    dependencies[Path(__file__).resolve()]=e.fingerprint(Path(__file__))
    inputs={};sources=[]
    if a.suite=='synthetic':
        jobs=[(name,rate,shift,builds) for name in FIXTURES for rate in (48000,96000) for shift in PITCHES]
        fn=synthetic;keys=('fixture','rate','shift','formant','variant')
        expected={(name,rate,shift,mode,v) for name,rate,shift,_ in jobs
            for mode in (e.FORMANTS if name.startswith('vowel') else ('off',)) for v in VARIANTS}
    else:
        if not all((a.refs,a.tests,a.catalog)):raise ValueError('all three corpus paths required')
        sources,processed,cells=e.plan(a.refs,a.tests,a.catalog)
        cells=[c for c in cells if c['scope']=='target']
        split={r['stem']:('development' if i%4==0 else 'confirmation') for i,r in enumerate(sources)}
        inputs[a.catalog.resolve()]=e.fingerprint(a.catalog)
        for c in cells:
            inputs[e.inside(a.refs,c['reference_name'])]=c['reference_sha256']
            if c['family']=='derived':inputs[e.inside(a.tests,c['processed_name'])]=c['processed_sha256']
        jobs=[(c,a.refs,a.tests,builds,split[c['stem']]) for c in cells]
        fn=natural;keys=('condition','formant','variant')
        expected={(c['condition_id'],mode,v) for c in cells
            for mode in (('off',) if c['family']=='derived' else e.FORMANTS)
            for v in ((*VARIANTS,'provided_elastique') if c['family']=='derived' else VARIANTS)}
    output=a.output.resolve();output.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.phase-owner-study-',dir=output.parent) as tmp:
        staging=Path(tmp)/'report';staging.mkdir();rows=[]
        cache=a.cache.resolve() if a.cache else staging/'cache'
        manifest=dict(suite=a.suite,executables=executable_hashes,
            dependencies={str(p):h for p,h in dependencies.items()},inputs={str(p):h for p,h in inputs.items()},
            expected=[list(k) for k in sorted(expected)])
        rows=cached_run(cache,manifest,fn,jobs,a.workers)
        validate_rows(rows,expected,keys)
        for label,build in zip(VARIANTS,builds):
            if e.fingerprint(build/'boiled_egg_pv_rt_cli')!=executable_hashes[label]:raise ValueError('renderer changed')
        for path,digest in {**dependencies,**inputs}.items():
            if e.fingerprint(path)!=digest:raise ValueError('analysis/input changed during run')
        write_csv(staging/'measurements.csv',rows)
        result=dict(schema='boiled-egg.phase-owner-study.v1',suite=a.suite,rows=len(rows),
            candidate_renders=sum(r['variant'] in VARIANTS for r in rows),executables=executable_hashes,
            analysis_sha256={p.name:h for p,h in dependencies.items()},input_sha256={str(p):h for p,h in inputs.items()},sources=sources,
            python=platform.python_version(),numpy=np.__version__,soundfile=sf.__version__,
            measurements_sha256=e.fingerprint(staging/'measurements.csv'),listening_status='not_listened',
            native_pitch_baseline=False,mos_transfer=False,automatic_promotion=False,
            protocol='Fuzzy only, no winner selection. Fixed nearest-compatible-peak radius4 and half-bin tolerance. '
            'Centered/scaled. Pitch uses scheduled SIMD block32; direct TSM immediate block64. '
            'Formant policies are independent. The 15-source confirmation split is withheld from this iteration only; '
            'the full corpus has been used historically. No trained classifier or new native baseline.')
        (staging/'summary.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
        staging.rename(output)
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for k in (*VARIANTS,'output'):p.add_argument('--'+k,type=Path,required=True)
    p.add_argument('--suite',choices=('synthetic','corpus'),required=True)
    for k in ('refs','tests','catalog'):p.add_argument('--'+k,type=Path)
    p.add_argument('--cache',type=Path)
    p.add_argument('--workers',type=int,default=3)
    r=run(p.parse_args());print(r['candidate_renders'],'renders,',r['rows'],'measurements',flush=True)
