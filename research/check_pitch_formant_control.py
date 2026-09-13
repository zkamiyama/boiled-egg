#!/usr/bin/env python3
"""Matched no-preservation pitch control: temporal metrics only, no timbre verdict.

Both paths shift timbre along with pitch. The provided path is still TSM plus
Fourier resampling, NOT native zplane pitch. This ablation does not compare an
unshifted source envelope with intentionally shifted timbre as a quality score.
"""
from __future__ import annotations
import argparse,concurrent.futures as cf,csv,json,subprocess,tempfile
from pathlib import Path
import numpy as np
import compare_zplane_outputs as c
from eval_elastique_pitch import feat,corr


def measure(job):
    cell,refs,tests,build=job;source=c.e.inside(refs,cell['reference_name']);provided=c.e.inside(tests,cell['processed_name'])
    if c.fingerprint(source)!=cell['reference_sha256'] or c.fingerprint(provided)!=cell['processed_sha256']:raise ValueError('input changed')
    ref,rate=c.e.checked_audio(source);tsm,sr=c.e.checked_audio(provided)
    if rate!=sr or ref.shape[1]!=1:raise ValueError('mono same-rate control required')
    _,_,ref_onset=feat(ref[:,0],rate);rows=[]
    def record(x,profile,path):
        if x.shape!=ref.shape:raise ValueError('shape mismatch')
        _,_,onset=feat(x[:,0],rate);temporal=c.aq.temporal(ref,x,rate)
        if len(onset)!=len(ref_onset):raise ValueError('onset grid mismatch')
        rows.append(dict(operation='derived_pitch_no_preservation',scope='target',source=cell['stem'],condition=cell['condition_id'],
            profile=profile,formant='off',ratio=cell['control_ratio'],frames=len(x),rate=rate,
            onset_corr=corr(ref_onset,onset),rms_shape_db=temporal['rms_shape_error_db'],
            source_sha256=cell['reference_sha256'],render_sha256=c.fingerprint(path)))
    with tempfile.TemporaryDirectory(prefix='pitch-off-control-') as temp:
        dst=Path(temp)/'render.wav';c.sf.write(dst,c.e.exact_resample(tsm,len(ref)),rate,subtype='FLOAT')
        x,_=c.e.checked_audio(dst);record(x,'derived_elastique',dst)
        for profile in c.e.PROFILES:
            cmd=c.e.command(build/'boiled_egg_pv_rt_cli',build/'boiled_egg_multires_rt_cli',source,dst,profile,'off',cell['control_ratio'],64)
            cmd+=['--timing','centered','--rate-policy','scaled']
            result=subprocess.run(cmd,capture_output=True,text=True,timeout=120)
            if result.returncode:raise RuntimeError(result.stderr)
            x,sr=c.e.checked_audio(dst)
            if sr!=rate:raise ValueError('rate mismatch')
            record(x,profile,dst)
    return rows


def summarize(rows):
    result=[];lookup={}
    for r in rows:
        key=(r['condition'],r['profile'])
        if key in lookup:raise ValueError('duplicate condition')
        lookup[key]=r
    base=[r for r in rows if r['profile']=='derived_elastique']
    if not base:raise ValueError('no baseline')
    for profile in c.e.PROFILES:
        for metric,sign in [('onset_corr',1),('rms_shape_db',-1)]:
            paired=[(lookup[b['condition'],profile],b) for b in base];d=np.array([a[metric]-b[metric] for a,b in paired])
            sources=sorted({b['source'] for a,b in paired});means=np.array([np.mean([a[metric]-b[metric] for a,b in paired if b['source']==s]) for s in sources])
            rng=np.random.default_rng(20260913);boot=means[rng.integers(0,len(means),(4000,len(means)))].mean(axis=1)
            result.append(dict(profile=profile,metric=metric,n=len(base),sources=len(sources),candidate_mean=float(np.mean([a[metric] for a,b in paired])),
                baseline_mean=float(np.mean([b[metric] for a,b in paired])),delta=float(d.mean()),wins=int(np.sum(sign*d>1e-9)),
                ci95=list(map(float,np.quantile(boot,[.025,.975])))))
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('refs','tests','catalog','build','output'):p.add_argument('--'+n,type=Path,required=True)
    p.add_argument('--workers',type=int,default=2);a=p.parse_args()
    if a.workers<1 or a.output.exists():raise ValueError('workers/output')
    _,_,cells=c.e.plan(a.refs,a.tests,a.catalog);cells=[x for x in cells if x['family']=='derived' and x['scope']=='target']
    hashes={n:c.fingerprint(a.build/n) for n in ('boiled_egg_pv_rt_cli','boiled_egg_multires_rt_cli')};rows=[]
    with cf.ProcessPoolExecutor(max_workers=a.workers) as pool:
        for i,out in enumerate(pool.map(measure,[(cell,a.refs,a.tests,a.build) for cell in cells]),1):rows+=out;print(i,len(rows),flush=True)
    if len(rows)!=len(cells)*6 or any(c.fingerprint(a.build/n)!=h for n,h in hashes.items()):raise ValueError('grid/binary mismatch')
    summary=summarize(rows);a.output.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.pitch-control-',dir=a.output.parent) as tmp:
        staging=Path(tmp)/'result';staging.mkdir()
        with (staging/'measurements.csv').open('w',newline='') as f:w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
        report=dict(schema='boiled-egg.pitch-formant-off-control.v1',comparisons=summary,rows=len(rows),candidate_renders=5*len(cells),binaries=hashes,
            catalog_sha256=c.fingerprint(a.catalog),script_sha256=c.fingerprint(Path(__file__)),measurements_sha256=c.fingerprint(staging/'measurements.csv'),
            native_pitch_baseline=False,mos_transfer=False,formant='off',interpretation='Temporal-only control. No spectral-envelope quality verdict. Source bootstrap4000, no multiplicity correction.')
        (staging/'summary.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n');staging.rename(a.output)
