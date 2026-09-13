#!/usr/bin/env python3
"""Opt-in timing/rate/formant feature evaluation; no native Elastique parity claim.

Legacy reproduces the previous quality run's PV FFT/hop scaling at96k (order40),
with fixed-window Multi-resolution. Candidate centers synthesis and scales FFT,
hop, cepstral order and Multi-resolution FIR. Raw audio is never limited/aligned.
"""
from __future__ import annotations
import argparse
import concurrent.futures as cf
import json
import re
import subprocess
import tempfile
from pathlib import Path
import numpy as np
import soundfile as sf
import audio_quality_metrics as m
import eval_audio_quality as q
import eval_fuzzy_corpus as e

PROFILES=e.PROFILES
PITCHES=(-12,-7,-3,3,7,12)
FIXTURES=('attack','harmonics','inharmonic','vowel_a','vowel_i','stereo70','noise0')


def command(build,src,dst,profile,formant,pitch,rate,variant,formant_ratio=1.):
    if variant not in ('legacy','timing','candidate'):raise ValueError('unknown feature variant')
    cmd=e.command(build/'boiled_egg_pv_rt_cli',build/'boiled_egg_multires_rt_cli',src,dst,profile,formant,pitch,64)
    if variant=='candidate':cmd+=['--timing','centered','--rate-policy','scaled']
    else:
        if profile!='multires' and rate==96000:
            for flag in ('--fft','--hop'):cmd[cmd.index(flag)+1]=str(int(cmd[cmd.index(flag)+1])*2)
        if variant=='timing':cmd+=['--timing','centered']
    if formant_ratio!=1.:cmd+=['--formant-ratio',format(formant_ratio,'.9g')]
    return cmd


def render(cmd,dst,shape,rate):
    proc=subprocess.run(cmd,capture_output=True,text=True,timeout=120)
    if proc.returncode:raise RuntimeError(f'render failed: {proc.stderr}')
    x,sr=e.checked_audio(dst)
    if x.shape!=shape or sr!=rate:raise ValueError('render metadata mismatch')
    return x,e.fingerprint(dst)


def attack_fixture(rate,ratio):
    # Eight positions modulo the 48-kHz hop, spaced by more than 200ms.
    starts=[round(.2*rate)+i*(round(.2*rate)+round(32*rate/48000)) for i in range(8)]
    n=round(2*rate);duration=.002;gate=np.zeros(n)
    for start in starts:
        count=round(duration*rate)
        gate[start:start+count]=np.sin(np.pi*np.arange(count)/count)**2
    x=q.wave(rate,np.array([2113.,3299.,5113.,7331.])*ratio,np.full(4,.12),n)*gate
    return x.astype('float32')[:,None],dict(family='attack',starts=[s/rate for s in starts],duration=duration)


def formant_fixture(name,rate,pitch,envelope):
    f=120*np.arange(1,81)*pitch
    centers=np.array((700,1200,2600) if name=='vowel_a' else (300,2300,3000))*envelope
    widths=np.array((80,130,180))*envelope
    amplitudes=sum(g/(1+((f-c)/w)**2) for c,w,g in zip(centers,widths,(1.,.7,.45)))
    x=q.wave(rate,f,amplitudes,rate*2);x*=.1/np.sqrt(np.mean(x*x))
    return x.astype('float32')[:,None],dict(family='formant',frequencies=f)


def synthetic_job(job):
    name,rate,shift,build,profiles=job
    pitch=float(np.float32(2**(shift/12)))
    make=attack_fixture if name=='attack' else lambda rate,ratio:q.fixture(name,rate,ratio)
    source,_=make(rate,1.);oracle,meta=make(rate,pitch);rows=[]
    with tempfile.TemporaryDirectory(prefix='feature-synth-') as tmp:
        src,dst=Path(tmp)/'source.wav',Path(tmp)/'output.wav'
        sf.write(src,source,rate,subtype='FLOAT');source_hash=e.fingerprint(src)
        for mode in (e.FORMANTS if meta['family']=='formant' else ('off',)):
            for profile in profiles:
                variants=('legacy','timing','candidate') if rate==96000 and name=='attack' else ('legacy','candidate')
                for variant in variants:
                    x,digest=render(command(build,src,dst,profile,mode,pitch,rate,variant),dst,source.shape,rate)
                    row=dict(fixture=name,rate=rate,shift=shift,profile=profile,variant=variant,formant=mode,
                        formant_ratio=1.,**q.diagnose(x,oracle,meta,rate),peak=float(np.max(np.abs(x))),
                        frames=len(x),channels=x.shape[1],render_sha256=digest,source_sha256=source_hash)
                    if shift==0:row['unity_error_db']=float(m.db(np.mean((x-source)**2)/np.mean(source.astype(float)**2)))
                    rows.append(row)
    return rows


def formant_job(job):
    name,rate,shift,build,profiles=job
    pitch=float(np.float32(2**(shift/12)));source,_=formant_fixture(name,rate,1.,1.);rows=[]
    with tempfile.TemporaryDirectory(prefix='feature-formants-') as tmp:
        src,dst=Path(tmp)/'source.wav',Path(tmp)/'output.wav'
        sf.write(src,source,rate,subtype='FLOAT');source_hash=e.fingerprint(src)
        for mode in ('harmonic','monophonic'):
            for profile in profiles:
                control,control_hash=render(command(build,src,dst,profile,mode,pitch,rate,'candidate'),dst,source.shape,rate)
                for formant_shift in (-12,-7,0,7,12):
                    f=float(np.float32(2**(formant_shift/12)))
                    oracle,meta=formant_fixture(name,rate,pitch,f)
                    if formant_shift==0:x,digest=control,control_hash
                    else:x,digest=render(command(build,src,dst,profile,mode,pitch,rate,'candidate',f),dst,source.shape,rate)
                    measured=q.diagnose(x,oracle,meta,rate);baseline=q.diagnose(control,oracle,meta,rate)
                    rows.append(dict(fixture=name,rate=rate,shift=shift,profile=profile,formant=mode,
                        formant_shift=formant_shift,formant_ratio=f,**measured,
                        control_error_db=baseline['partial_envelope_error_db'],
                        delta_vs_unshifted_formant_db=measured['partial_envelope_error_db']-baseline['partial_envelope_error_db'],
                        peak=float(np.max(np.abs(x))),frames=len(x),channels=x.shape[1],
                        render_sha256=digest,source_sha256=source_hash))
    return rows


def corpus_job(job):
    cell,refs,tests,build,profiles=job
    src=e.inside(refs,cell['reference_name'])
    if e.fingerprint(src)!=cell['reference_sha256']:raise ValueError('source changed')
    source,rate=e.checked_audio(src);rows=[]
    def record(x,profile,variant,digest):
        metrics=e.measure(source,x,rate)
        rows.append(dict(family=cell['family'],condition_id=cell['condition_id'],stem=cell['stem'],
            rate=rate,shift=cell['pitch_semitones'],control_ratio=cell['control_ratio'],profile=profile,variant=variant,
            formant='harmonic' if profile!=e.BASELINE else 'not_applicable',**m.temporal(source,x,rate),
            env=metrics['env'],onset=metrics['onset'],render_sha256=digest,
            source_sha256=cell['reference_sha256'],frames=len(x),channels=x.shape[1]))
    with tempfile.TemporaryDirectory(prefix='feature-corpus-') as tmp:
        dst=Path(tmp)/'output.wav'
        if cell['family']=='derived':
            test=e.inside(tests,cell['processed_name'])
            if e.fingerprint(test)!=cell['processed_sha256']:raise ValueError('TSM changed')
            x,sr=e.checked_audio(test)
            if sr!=rate:raise ValueError('TSM rate mismatch')
            sf.write(dst,e.exact_resample(x,len(source)),rate,subtype='FLOAT')
            x,_=e.checked_audio(dst);record(x,e.BASELINE,'derived',e.fingerprint(dst))
        for profile in profiles:
            for variant in ('legacy','candidate'):
                x,digest=render(command(build,src,dst,profile,'harmonic',cell['control_ratio'],rate,variant),dst,source.shape,rate)
                record(x,profile,variant,digest)
    return rows


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--build',type=Path,required=True);p.add_argument('--base-commit',required=True)
    p.add_argument('--suite',choices=('synthetic','formant','corpus'),required=True)
    p.add_argument('--output',type=Path,required=True);p.add_argument('--workers',type=int,default=3)
    p.add_argument('--profiles',nargs='+',choices=PROFILES,default=list(PROFILES))
    for key in ('ref-dir','test-dir','catalog'):p.add_argument('--'+key,type=Path)
    a=p.parse_args()
    if not re.fullmatch('[0-9a-f]{40}',a.base_commit) or a.workers<1 or len(set(a.profiles))!=len(a.profiles):
        raise ValueError('valid base commit, workers and unique profiles required')
    if a.output.exists():raise ValueError('output already exists')
    a.build=a.build.resolve(strict=True);code=Path(__file__).resolve().parent
    files=[code/'eval_research_features.py',code/'eval_audio_quality.py',code/'audio_quality_metrics.py',
           code/'eval_fuzzy_corpus.py',*sorted((code/'cpp_pv_rt').rglob('*.cpp')),
           *sorted((code/'cpp_pv_rt').rglob('*.h')),*sorted((code/'cpp_pv_rt').rglob('*.hpp')),
           a.build/'boiled_egg_pv_rt_cli',a.build/'boiled_egg_multires_rt_cli']
    hashes={str(path):e.fingerprint(path) for path in files};sources=processed=[];cells=[]
    if a.suite=='synthetic':
        jobs=[(name,sr,st,a.build,a.profiles) for name in FIXTURES for sr in (48000,96000) for st in (*PITCHES,0)]
        fn=synthetic_job
        expected=sum(len(a.profiles)*(3 if name.startswith('vowel') else 1)*(3 if sr==96000 and name=='attack' else 2)
                     for name,sr,st,build,profiles in jobs)
    elif a.suite=='formant':
        jobs=[(name,sr,st,a.build,a.profiles) for name in ('vowel_a','vowel_i') for sr in (48000,96000) for st in (-7,0,7)]
        fn=formant_job;expected=len(jobs)*len(a.profiles)*2*5
    else:
        if not all((a.ref_dir,a.test_dir,a.catalog)):raise ValueError('three corpus paths required')
        sources,processed,cells=e.plan(a.ref_dir,a.test_dir,a.catalog);cells=[c for c in cells if c['scope']=='target']
        hashes[str(a.catalog)]=e.fingerprint(a.catalog)
        for s in sources:hashes[str(e.inside(a.ref_dir,s['reference_name']))]=s['reference_sha256']
        for s in processed:hashes[str(e.inside(a.test_dir,s['name']))]=s['sha256']
        jobs=[(c,a.ref_dir,a.test_dir,a.build,a.profiles) for c in cells];fn=corpus_job
        expected=sum(2*len(a.profiles)+(c['family']=='derived') for c in cells)
    a.output.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.features-',dir=a.output.parent) as tmp:
        stage=Path(tmp)/'report';stage.mkdir();rows=[]
        with cf.ProcessPoolExecutor(max_workers=a.workers) as pool:
            for i,part in enumerate(pool.map(fn,jobs),1):
                rows.extend(part)
                if i%5==0:print(f'{a.suite}: {i}/{len(jobs)} jobs, {len(rows)} measurements',flush=True)
        if len(rows)!=expected:raise ValueError('incomplete matrix')
        if any(e.fingerprint(Path(path))!=digest for path,digest in hashes.items()):raise ValueError('inputs/code/executables changed')
        q.write_csv(stage/'measurements.csv',rows)
        keys=('family','profile','variant') if a.suite=='corpus' else ('fixture','rate','profile','formant')+(() if a.suite=='formant' else ('variant',))
        summary=dict(schema='boiled-egg.feature-parity.v1',suite=a.suite,base_source_commit=a.base_commit,
            fingerprints=hashes,measurements=len(rows),profiles=a.profiles,sources=sources,processed=processed,
            metric_groups=q.aggregate(rows,keys),metrics_sha256=e.fingerprint(stage/'measurements.csv'),
            exact_duration_measurements=len(rows),listening_status='not_listened',product_promotion=False,
            note='Opt-in research extensions. No limiter, metric retuning or waveform time alignment. '
                 'Formant suite includes reused unity controls, each row represents a unique requested control condition. '
                 'Source commit is the base; actual working code and binaries are independently fingerprinted.')
        (stage/'summary.json').write_text(json.dumps(summary,indent=2,allow_nan=False)+'\n');stage.rename(a.output)
    print(f'{a.suite}: {len(rows)} measurements complete',flush=True)

if __name__=='__main__':main()
