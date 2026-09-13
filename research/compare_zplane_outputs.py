#!/usr/bin/env python3
"""Paired supplied-Elastique TSM and derived pitch diagnostics; never native-pitch/MOS.

TSM compares spectrotemporal features on an affine normalized time axis, NOT
resampled waveforms or elastic/dynamic alignment. Native pitch output was not
supplied. Pitch comparison therefore uses the documented TSM+Fourier resampling
baseline. Primary target ratio[.5,2] and stress(2,4] are separate. No best-of-mode
selection or aggregate perceptual score is manufactured.
"""
from __future__ import annotations
import argparse, concurrent.futures as cf, csv, hashlib, json, math, platform, subprocess, tempfile
from collections import defaultdict
from pathlib import Path
import numpy as np
import scipy
from scipy import signal
import soundfile as sf
import eval_fuzzy_corpus as e
import audio_quality_metrics as aq
from eval_elastique_pitch import metrics as broad_metrics

SCHEMA='boiled-egg.zplane-output-comparison.v1'
# Lower distance values and higher correlation are closer to source features,
# not necessarily perceptually preferable. Pitch chroma/phase are not scored.
DIRECTIONS={'envelope_rmse_db':-1,'onset_corr':1,'rms_shape_db':-1,
            'spectral_distance_db':-1,'spectral_convergence':-1,'chroma_corr':1}


def fingerprint(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def stretch_features(x,rate):
    x=aq.audio(x)
    if x.shape[1]!=1:raise ValueError('this comparative feature study is explicitly mono')
    g=math.gcd(rate,16000);x=signal.resample_poly(x[:,0],16000//g,rate//g)
    f,_,z=signal.stft(x,fs=16000,nperseg=1024,noverlap=768,nfft=1024,window='hann',boundary='zeros',padded=True)
    mag=np.abs(z).astype(float)
    power=mag**2
    energy=np.sqrt(np.mean(power,axis=0))
    norm=mag/np.maximum(energy[None,:],1e-12)
    chroma=np.zeros((12,mag.shape[1]));mask=f>=50
    notes=np.rint(69+12*np.log2(f[mask]/440)).astype(int)
    for k,note in zip(np.flatnonzero(mask),notes):chroma[note%12]+=power[k]
    chroma/=np.maximum(chroma.sum(axis=0,keepdims=True),1e-24)
    return norm,chroma,energy


def interpolate(a,n):
    return np.vstack([np.interp(np.linspace(0,1,n),np.linspace(0,1,a.shape[1]),row) for row in a])


def tsm_metrics(ref,out,rate):
    """No fitted time delay. -80 dB relative-amplitude log floor; active source
    frame mask -40 dB RMS. Uniform time map is the requested TSM operation."""
    a,ca,energy=stretch_features(ref,rate);b,cb,_=stretch_features(out,rate)
    b=interpolate(b,a.shape[1]);cb=interpolate(cb,ca.shape[1]);mask=energy>energy.max()*.01
    if not mask.any():raise ValueError('silent source')
    x,y=a[:,mask],b[:,mask]
    ca,cb=ca[:,mask],cb[:,mask]
    ca=ca-ca.mean(axis=0);cb=cb-cb.mean(axis=0)
    den=np.sqrt((ca**2).sum(axis=0)*(cb**2).sum(axis=0));valid=den>1e-12
    chroma=float(np.mean(np.sum(ca[:,valid]*cb[:,valid],axis=0)/den[valid])) if valid.any() else None
    if chroma is None:raise ValueError('undefined chroma')
    env,on,_,_=broad_metrics(ref[:,0],out[:,0],rate)
    # Normalized RMS envelopes on a common source-time grid; no audio resampling.
    def rms(a):
        size=max(1,round(rate*.01));p=np.mean(a*a,axis=1);p=np.pad(p,(0,(-len(p))%size)).reshape(-1,size).sum(axis=1)
        return p/max(float(p.sum()),1e-24)
    r,s=rms(ref),rms(out);s=np.interp(np.linspace(0,1,len(r)),np.linspace(0,1,len(s)),s);s/=max(float(s.sum()),1e-24)
    active=r>r.max()*1e-4
    shape=float(np.sqrt(np.mean((10*np.log10(np.maximum(r[active],1e-12))-10*np.log10(np.maximum(s[active],1e-12)))**2)))
    return dict(envelope_rmse_db=float(env),onset_corr=float(on),rms_shape_db=shape,
        spectral_distance_db=float(np.sqrt(np.mean((20*np.log10(np.maximum(x,1e-4))-20*np.log10(np.maximum(y,1e-4)))**2))),
        spectral_convergence=float(np.linalg.norm(x-y)/np.linalg.norm(x)),chroma_corr=chroma)


def pitch_metrics(ref,out,rate):
    env,on,_,_=broad_metrics(ref[:,0],out[:,0],rate);temporal=aq.temporal(ref,out,rate)
    return dict(envelope_rmse_db=float(env),onset_corr=float(on),rms_shape_db=temporal['rms_shape_error_db'],energy_transport_ms=temporal['energy_transport_ms'])


def process(job):
    cell,refs,tests,build,profiles=job
    refpath=e.inside(refs,cell['reference_name']);testpath=e.inside(tests,cell['processed_name'])
    if fingerprint(refpath)!=cell['reference_sha256'] or fingerprint(testpath)!=cell['processed_sha256']:raise ValueError('input hash mismatch')
    ref,rate=e.checked_audio(refpath);test,sr=e.checked_audio(testpath)
    if rate!=sr or ref.shape[1]!=1 or test.shape[1]!=1:raise ValueError('explicit mono/rate contract')
    rows=[]
    with tempfile.TemporaryDirectory(prefix='zplane-compare-') as temp:
        for operation in ('time_stretch','derived_pitch'):
            target=len(test) if operation=='time_stretch' else len(ref)
            baseline=test if operation=='time_stretch' else e.exact_resample(test,len(ref)).astype(float)
            def record(x,name,sha,frame_error):
                values=(tsm_metrics if operation=='time_stretch' else pitch_metrics)(ref,x,rate)
                if not all(math.isfinite(v) for v in values.values()):raise ValueError('nonfinite metric')
                rows.append(dict(operation=operation,scope=cell['scope'],source=cell['stem'],condition=cell['condition_id'],
                    category=cell['review_category'],ratio=cell['measured_ratio'],profile=name,rate=rate,
                    frames=len(x),requested_frames=target,frame_error=frame_error,peak=float(np.max(np.abs(x))),
                    rms_gain_db=float(10*np.log10(np.mean(x*x)/np.mean(ref*ref))),**values,
                    source_sha256=cell['reference_sha256'],provided_sha256=cell['processed_sha256'],render_sha256=sha))
            if operation=='derived_pitch':
                dest=Path(temp)/'derived.wav';sf.write(dest,baseline,rate,subtype='FLOAT');baseline,_=e.checked_audio(dest);digest=fingerprint(dest)
            else:digest=fingerprint(testpath)
            record(baseline,'provided_elastique' if operation=='time_stretch' else 'derived_elastique',digest,0)
            for profile in profiles:
                dest=Path(temp)/(operation+'-'+profile+'.wav')
                cmd=e.command(build/'boiled_egg_pv_rt_cli',build/'boiled_egg_multires_rt_cli',refpath,dest,profile,
                              'off' if operation=='time_stretch' else 'harmonic',cell['control_ratio'],64)
                if operation=='time_stretch':
                    cmd[cmd.index('--time')+1]=format(cell['control_ratio'],'.9g');cmd[cmd.index('--pitch-ratio')+1]='1'
                cmd+=['--timing','centered','--rate-policy','scaled']
                run=subprocess.run(cmd,capture_output=True,text=True,timeout=120)
                if run.returncode:raise RuntimeError(run.stderr)
                x,sr=e.checked_audio(dest)
                expected=round(len(ref)*(cell['control_ratio'] if operation=='time_stretch' else 1.0))
                if sr!=rate or x.shape[1]!=1 or len(x)!=expected:raise ValueError('rate/channel/float32-duration mismatch')
                record(x,profile,fingerprint(dest),len(x)-target)
    return rows


def summarize(rows,profiles):
    keys=[(r['operation'],r['condition'],r['profile']) for r in rows]
    if len(set(keys))!=len(keys):raise ValueError('duplicate comparison row')
    lookup=dict(zip(keys,rows));result=[]
    for operation in ('time_stretch','derived_pitch'):
        baseline='provided_elastique' if operation=='time_stretch' else 'derived_elastique'
        for scope in ('target','stress'):
            controls=[r for r in rows if r['operation']==operation and r['scope']==scope and r['profile']==baseline]
            if not controls:continue
            fields=list(DIRECTIONS) if operation=='time_stretch' else ['envelope_rmse_db','onset_corr','rms_shape_db']
            for profile in profiles:
                for metric in fields:
                    pairs=[(lookup[(operation,b['condition'],profile)],b) for b in controls]
                    d=np.array([a[metric]-b[metric] for a,b in pairs]);groups=defaultdict(list)
                    for (a,b),delta in zip(pairs,d):groups[b['source']].append(delta)
                    cluster=np.array([np.mean(v) for _,v in sorted(groups.items())]);rng=np.random.default_rng(20260913)
                    boot=cluster[rng.integers(0,len(cluster),(4000,len(cluster)))].mean(axis=1)
                    sign=DIRECTIONS[metric];eps=1e-9
                    result.append(dict(operation=operation,scope=scope,profile=profile,metric=metric,n=len(d),sources=len(cluster),
                        candidate_mean=float(np.mean([a[metric] for a,b in pairs])),baseline_mean=float(np.mean([b[metric] for a,b in pairs])),
                        delta=float(d.mean()),source_balanced_delta=float(cluster.mean()),ci95=list(map(float,np.quantile(boot,[.025,.975]))),
                        wins=int(np.sum(d*sign>eps)),losses=int(np.sum(d*sign<-eps)),ties=int(np.sum(np.abs(d)<=eps))))
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for key in ('build','refs','tests','catalog','output'):p.add_argument('--'+key,type=Path,required=True)
    p.add_argument('--workers',type=int,default=2);p.add_argument('--profiles',nargs='+',choices=e.PROFILES,default=list(e.PROFILES))
    args=p.parse_args()
    if args.workers<1 or args.output.exists() or len(set(args.profiles))!=len(args.profiles):raise ValueError('workers/output/profiles')
    sources,processed,cells=e.plan(args.refs,args.tests,args.catalog);cells=[c for c in cells if c['family']=='derived']
    binaries={n:fingerprint(args.build/n) for n in ('boiled_egg_pv_rt_cli','boiled_egg_multires_rt_cli')}
    catalog_hash=fingerprint(args.catalog);args.output.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.zplane-report-',dir=args.output.parent) as temp:
        staging=Path(temp)/'report';staging.mkdir();rows=[]
        with cf.ProcessPoolExecutor(max_workers=args.workers) as pool:
            for i,part in enumerate(pool.map(process,[(c,args.refs,args.tests,args.build,args.profiles) for c in cells]),1):
                rows+=part;print('comparison',i,'/',len(cells),flush=True)
        expected=2*len(cells)*(len(args.profiles)+1)
        if len(rows)!=expected:raise ValueError('incomplete grid')
        comparisons=summarize(rows,args.profiles)
        if fingerprint(args.catalog)!=catalog_hash or any(fingerprint(args.build/n)!=h for n,h in binaries.items()):raise ValueError('provenance changed')
        with (staging/'measurements.csv').open('w',newline='') as stream:
            w=csv.DictWriter(stream,fieldnames=sorted(set.union(*(set(r) for r in rows))));w.writeheader();w.writerows(rows)
        with (staging/'comparison.csv').open('w',newline='') as stream:
            w=csv.DictWriter(stream,fieldnames=list(comparisons[0]));w.writeheader();w.writerows(comparisons)
        report=dict(schema=SCHEMA,comparisons=comparisons,sources=sources,processed=processed,binaries=binaries,
            rows=len(rows),candidate_renders=2*len(cells)*len(args.profiles),catalog_sha256=catalog_hash,
            measurement_sha256=fingerprint(staging/'measurements.csv'),script_sha256=fingerprint(Path(__file__)),
            versions=dict(python=platform.python_version(),numpy=np.__version__,scipy=scipy.__version__,soundfile=sf.__version__),
            baseline_version='not specified in supplied CSV',native_pitch_baseline=False,mos_transfer=False,
            notes='All profiles reported. Source-relative descriptors are not calibrated perceptual scores. '
                  'TSM uses an affine feature-time map, no fitted shift or DTW. Primary ratios .5..2, stress separate. '
                  'Pitch uses TSM+Fourier resampling, not native zplane pitch output. Source bootstrap4000, no multiplicity correction.')
        (staging/'summary.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n');staging.rename(args.output)
if __name__=='__main__':main()
