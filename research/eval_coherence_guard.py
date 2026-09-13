#!/usr/bin/env python3
"""Evaluate an explicitly patched Fuzzy build, reusing immutable baseline CSVs.

Includes independent seeded partial banks. Pilot fixtures informed development;
random banks and natural comparison do not tune the frozen half-bin guard.
"""
from __future__ import annotations
import argparse, concurrent.futures as cf, csv, json, tempfile
from collections import defaultdict
from pathlib import Path
from unittest.mock import patch
import numpy as np
import soundfile as sf
import eval_adaptive_nsgt as v
import eval_audio_quality as q
import eval_research_features as f
import eval_fuzzy_corpus as e

PROFILES=('fuzzy','fuzzy-noise')

def synth(job):
    # One actual source file is shared by both builds. FLOAT WAV PEAK chunks
    # contain timestamps, so separately regenerated file hashes are not valid
    # sample-identity evidence across runs. Never waive the hash check.
    name,rate,shift,base,candidate=job
    ratio=float(np.float32(2**(shift/12)))
    make=f.attack_fixture if name=='attack' else lambda sr,p:q.fixture(name,sr,p)
    source,_=make(rate,1.);oracle,meta=make(rate,ratio)
    groups={'baseline':[],'guard':[]}
    with tempfile.TemporaryDirectory(prefix='guard-paired-synth-') as tmp:
        src,dst=Path(tmp)/'in.wav',Path(tmp)/'out.wav';sf.write(src,source,rate,subtype='FLOAT');sha=v.digest(src)
        for mode in (e.FORMANTS if meta['family']=='formant' else ('off',)):
            for profile in PROFILES:
                for variant,build in (('baseline',base),('guard',candidate)):
                    x,receipt=v.render(source,rate,src,dst,build,profile,mode,ratio,1.)
                    groups[variant].append(dict(suite='synthetic',condition=f'{name}/{rate}/{shift}/{mode}',fixture=name,
                        family=meta['family'],rate=rate,shift=shift,formant=mode,profile=profile,source_sha256=sha,
                        input_samples_sha256=__import__('hashlib').sha256(source.astype('<f4').tobytes()).hexdigest(),
                        **receipt,**q.diagnose(x,oracle,meta,rate)))
    return groups

def natural(job):
    with patch.object(v,'PROFILES',PROFILES):return v.natural(job)

def random_job(job):
    seed,rate,shift,base,candidate=job
    rng=np.random.default_rng(44010+seed)
    frequencies=np.r_[rng.uniform(85,155),np.zeros(11)]
    frequencies[1:]=frequencies[0]+np.cumsum(rng.uniform(60,180,11))
    amplitudes=rng.uniform(.2,1,12)
    pitch=float(np.float32(2**(shift/12)))
    source=q.wave(rate,frequencies,amplitudes,2*rate);source*=.1/np.sqrt(np.mean(source**2));source=source.astype('float32')[:,None]
    oracle=q.wave(rate,frequencies*pitch,amplitudes,2*rate);oracle*=.1/np.sqrt(np.mean(oracle**2));oracle=oracle[:,None]
    meta=dict(family='partials',frequencies=frequencies*pitch)
    rows=[]
    with tempfile.TemporaryDirectory(prefix='guard-random-') as tmp:
        src,dst=Path(tmp)/'in.wav',Path(tmp)/'out.wav';sf.write(src,source,rate,subtype='FLOAT')
        for label,build in (('baseline',base),('guard',candidate)):
            x,receipt=v.render(source,rate,src,dst,build,'fuzzy','off',pitch,1.)
            rows.append(dict(seed=seed,rate=rate,shift=shift,variant=label,source_sha256=v.digest(src),
                frequencies=frequencies.tolist(),**receipt,**q.diagnose(x,oracle,meta,rate)))
    return rows

def read_csv(path):
    with path.open(newline='') as s:rows=list(csv.DictReader(s))
    for r in rows:
        for k,value in list(r.items()):
            if value=='':r[k]=None
            elif k not in ('suite','operation','condition','fixture','family','formant','profile','source','source_sha256','render_sha256'):
                try:r[k]=float(value)
                except ValueError:pass
    return rows

def paired(cand,base,synthetic=False):
    lookup={(r['condition'],r['profile']):r for r in base}
    groups=defaultdict(list)
    for r in cand:
        if r['profile'] not in PROFILES:continue
        b=lookup[(r['condition'],r['profile'])]
        if r['source_sha256']!=b['source_sha256']:raise ValueError('baseline source mismatch')
        if synthetic:
            names={'partials':('partial_envelope_error_db','off_partial_energy_db'),
                   'formant':('partial_envelope_error_db',),'attack':('width_excess_ms','centroid_bias_ms'),
                   'stereo':('lr_correlation_abs_error','coherence_abs_error'),
                   'noise':('noise_flatness','noise_lag_peak','noise_rms_cv')}[r['family']]
            group=(r['family'],r['rate'],r['profile'],r['formant'])
        else:
            names=('envelope_rmse_db','onset_corr','rms_shape_db')+(('spectral_distance_db','spectral_convergence','chroma_corr') if r['operation']=='time_stretch' else ())
            group=(r['operation'],r['profile'])
        for name in names:groups[(*group,name)].append((r,b,r[name]-b[name]))
    out=[]
    for key,pairs in sorted(groups.items()):
        cluster=defaultdict(list)
        for r,b,d in pairs:cluster[r.get('source',r.get('fixture'))].append(d)
        means=np.array([np.mean(d) for _,d in sorted(cluster.items())]);rng=np.random.default_rng(20260913)
        boot=means[rng.integers(0,len(means),(4000,len(means)))].mean(axis=1)
        name=key[-1];sign=1 if name in ('onset_corr','chroma_corr','noise_flatness') else -1
        out.append(dict(group=key[:-1],metric=name,n=len(pairs),baseline_mean=float(np.mean([b[name] for r,b,d in pairs])),
            candidate_mean=float(np.mean([r[name] for r,b,d in pairs])),mean_delta=float(np.mean([d for r,b,d in pairs])),
            direction_wins=sum(d*sign>1e-9 for r,b,d in pairs),source_ci95=list(map(float,np.quantile(boot,[.025,.975])))))
    return out

def run(args):
    if args.output.exists() or args.workers<1:raise ValueError('output/workers')
    roots={'base':args.baseline_build,'guard':args.candidate_build}
    hashes={label+'/'+name:v.digest(build/name) for label,build in roots.items() for name in ('boiled_egg_pv_rt_cli','boiled_egg_multires_rt_cli')}
    old=json.loads((args.baseline_results/'summary.json').read_text())
    for name,sha in old['files'].items():
        if v.digest(args.baseline_results/name)!=sha:raise ValueError('baseline metrics tampered')
    sources,processed,cells=e.plan(args.refs,args.tests,args.catalog);cells=[c for c in cells if c['scope']=='target']
    jobs=[(name,rate,shift,args.baseline_build,args.candidate_build) for name in v.FIXTURES for rate in (48000,96000) for shift in v.PITCHES]
    randoms=[(seed,rate,shift,args.baseline_build,args.candidate_build) for seed in range(10) for rate in (48000,96000) for shift in v.PITCHES]
    args.output.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.guard-eval-',dir=args.output.parent) as tmp:
        staging=Path(tmp)/'report';staging.mkdir();sy=[];sybase=[];co=[];ra=[]
        with cf.ProcessPoolExecutor(max_workers=args.workers) as pool:
            for i,part in enumerate(pool.map(synth,jobs),1):
                sy+=part['guard'];sybase+=part['baseline']
                if i%12==0:print('guard synthetic',i,'/',len(jobs),flush=True)
            for i,part in enumerate(pool.map(natural,[(c,args.candidate_build,args.refs,args.tests) for c in cells]),1):
                co+=part
                if i%20==0:print('guard corpus',i,'/',len(cells),flush=True)
            for i,part in enumerate(pool.map(random_job,randoms),1):
                ra+=part
                if i%20==0:print('independent partial banks',i,'/',len(randoms),flush=True)
        if len(sy)!=192 or len(co)!=420 or len(ra)!=240:raise ValueError('incomplete grid')
        for key,sha in hashes.items():
            label,name=key.split('/')
            if v.digest(roots[label]/name)!=sha:raise ValueError('executable changed')
        for name,rows in [('synthetic.csv',sy),('synthetic_baseline.csv',sybase),('corpus.csv',co),('random_partials.csv',ra)]:v.save_csv(staging/name,rows)
        report=dict(schema='boiled-egg.coherence-guard-study.v1',synthetic_rows=len(sy),corpus_rows=len(co),random_rows=len(ra),
            new_renders=len(sy)+len(sybase)+sum(r['profile'] in PROFILES for r in co)+len(ra),binaries=hashes,
            baseline_summary_sha256=v.digest(args.baseline_results/'summary.json'),script_sha256=v.digest(Path(__file__)),
            synthetic=paired(sy,sybase,True),
            corpus=paired(co,read_csv(args.baseline_results/'corpus.csv')),
            random_partials=v.aggregate(ra,('rate','variant')),files={p.name:v.digest(p) for p in staging.iterdir()},
            limitations='Experimental C++ Fuzzy frequency-coherence guard; not the SELEBI algorithm. Thresholds chosen using recorded pilot fixtures before natural/random runs. Existing five-profile defaults are untouched outside the explicitly patched build. New random seeds are not listening evidence. Descriptive source-cluster intervals, no perceptual/MOS/native-pitch claim.')
        (staging/'summary.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n');staging.rename(args.output)
    return report
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('baseline-build','candidate-build','baseline-results','refs','tests','catalog','output'):p.add_argument('--'+n,type=Path,required=True)
    p.add_argument('--workers',type=int,default=3)
    r=run(p.parse_args());print(r['new_renders'],flush=True)
