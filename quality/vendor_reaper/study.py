#!/usr/bin/env python3
"""Fixed first comparison of REAPER-hosted elastique and current SDK.

No MOS, no natural-voice/general parity claim, no new product DSP.
"""
from __future__ import annotations
import argparse, hashlib, itertools, json, math, os, statistics, subprocess, sys, time
from pathlib import Path
import numpy as np
import scipy
from scipy import signal
import soundfile as sf
import contract as host
c=host.c
import offline_pv_benchmark as m
FAMILIES=('low61','vowel120','vowel220','bursts','mixed61')
RATES=(48000,96000)
SHIFTS=(-12,0,12)
SDK={
 'sdk_wsola':('wsola','general','off'),
 'sdk_pv_general_off':('pv','general','off'),
 'sdk_pv_general_harmonic':('pv','general','harmonic'),
 'sdk_pv_general_monophonic':('pv','general','monophonic'),
 'sdk_pv_transient_off':('pv','transient','off'),
}
ENGINES=tuple(host.PROFILES)+tuple(SDK)
REPEATS=3

def envelope(f):
    f=np.asarray(f,dtype=float)
    return .08+np.exp(-.5*((f-650)/95)**2)+.8*np.exp(-.5*((f-1200)/125)**2)+.6*np.exp(-.5*((f-2500)/180)**2)

def fixture(family,rate):
    if family not in FAMILIES or rate not in RATES:raise ValueError('unknown fixture')
    t=np.arange(rate*2)/rate;x=np.zeros_like(t);fade=np.minimum(1,np.minimum(t/.03,(2-t)/.03))
    meta=dict(family=family,rate=rate,frames=len(t),centers=[],frequency=None)
    if family in ('low61','mixed61'):
        a=.2 if family=='low61' else .08;x+=a*np.sin(2*np.pi*61*t+.31)*fade
        meta.update(frequency=61.,amplitude=a)
    if family.startswith('vowel'):
        f0=int(family[5:]);k=np.arange(1,31);amps=.03*envelope(k*f0)/k**.7
        for n,a in zip(k,amps):x+=a*np.sin(2*np.pi*n*f0*t+.17*n)
        x*=fade;meta.update(f0=f0,harmonics=30,source_amplitudes=amps.tolist(),formants=[650,1200,2500])
    if family in ('bursts','mixed61'):
        meta['centers']=[.55,1.35]
        for center in meta['centers']:x+=.18*np.exp(-.5*((t-center)/.0015)**2)*np.cos(2*np.pi*3500*(t-center))
    return x.astype(np.float32),meta

def event_metric(y,rate,centers):
    out=[]
    for center in centers:
        lo,hi=round((center-.08)*rate),round((center+.08)*rate)
        a=y[lo:hi].astype(float);e=a*a;total=float(e.sum());result={'energy':total}
        if total<=1e-16:result.update(missing=True,position_ms=None,width_ms=None)
        else:
            q=np.searchsorted(np.cumsum(e)/total,[.05,.95])
            result.update(missing=False,position_ms=float(np.dot(np.arange(lo,hi)/rate-center,e)/total*1000),
                          width_ms=float((q[1]-q[0])*1000/rate))
        out.append(result)
    return out

def measure(y,meta,shift):
    y=m.valid_vector(y);rate=meta['rate'];p=2**(shift/12)
    if len(y)!=meta['frames']:raise ValueError('length mismatch')
    out=dict(peak=float(np.max(abs(y))),rms=float(np.sqrt(np.mean(y*y))))
    if meta['frequency']:
        z=y if not meta['centers'] else signal.sosfiltfilt(signal.butter(4,500,fs=rate,output='sos'),y)
        z=z[rate//2:rate*3//2];a,residual=m.components(z,rate,[61*p]);cent=m.tone_error(z,rate,61*p)
        db=float(20*np.log10(max(a[0],1e-30)/meta['amplitude']))
        out['tone']=dict(cents=cent,amplitude_db=db,unexplained_energy=residual,
                         passed=abs(cent)<=5 and abs(db)<=1 and residual<=.01,
                         scope='lowpass-mixture-diagnostic' if meta['centers'] else 'pure')
    if 'f0' in meta:
        # Exact one-second interval, all tested target harmonics are integer Hz.
        # Projection is measurement, not correction of output phase/gain/lag.
        z=y[rate//2:rate*3//2];k=np.arange(1,31);f=k*meta['f0']*p
        spectrum=np.fft.rfft(z);a=2*abs(spectrum[np.rint(f).astype(int)])/len(z)
        off=np.asarray(meta['source_amplitudes']);pres=.03*envelope(f)/k**.7
        selected=(f>=250)&(f<=3500)&(np.maximum(off,pres)>=.00015)
        def rmse(target):return float(np.sqrt(np.mean((20*np.log10(np.maximum(a[selected],1e-12)/target[selected]))**2)))
        explained=float(len(z)/2*np.sum(a*a));energy=float(np.dot(z,z))
        out['formant']=dict(off_target_rmse_db=rmse(off),preserved_target_rmse_db=rmse(pres),
            harmonics_measured=int(selected.sum()),measured_amplitudes=a.tolist(),
            unexplained_energy=max(0.,1-explained/energy),target_frequencies=f.tolist(),
            no_gain_or_lag_fit=True)
    if meta['centers']:
        high=signal.sosfiltfilt(signal.butter(4,1000,btype='highpass',fs=rate,output='sos'),y)
        out['events']=event_metric(high,rate,meta['centers'])
        out['event_metric_scope']='highpass centroid/width; centroid is not onset; no time alignment'
    return out

def key(row):return (row['family'],row['rate'],row['shift'],row['engine'],row['repeat'])

def assess(rows):
    wanted=set(itertools.product(FAMILIES,RATES,SHIFTS,ENGINES,range(REPEATS)))
    keys=[key(r) for r in rows]
    if len(keys)!=len(set(keys)) or set(keys)!=wanted:raise ValueError('incomplete/duplicate grid')
    failures=[{k:r[k] for k in ('family','rate','shift','engine','repeat','error')} for r in rows if r['status']!='complete']
    base=dict(attempts=len(rows),completed=len(rows)-len(failures),failures=failures,quality_selection=None)
    if failures:return dict(**base,integrity_pass=False,profiles=None)
    try:
        for r in rows:
            digest=r['pcm_sha256']; metric=r['metrics']
            if not isinstance(digest,str) or len(digest)!=64 or any(ch not in '0123456789abcdef' for ch in digest):raise ValueError('invalid PCM hash')
            json.dumps(metric,allow_nan=False)
            if not math.isfinite(metric['peak']) or not math.isfinite(metric['rms']) or metric['peak']<=0 or metric['rms']<=1e-8:raise ValueError('nonpositive audio')
            if r['family'] in ('low61','mixed61'):
                for name in ('cents','amplitude_db','unexplained_energy'):
                    if not math.isfinite(metric['tone'][name]):raise ValueError('nonfinite tone metric')
                if type(metric['tone']['passed'])!=bool:raise ValueError('invalid gate')
            if r['family'].startswith('vowel'):
                for name in ('off_target_rmse_db','preserved_target_rmse_db'):
                    if not math.isfinite(metric['formant'][name]):raise ValueError('nonfinite envelope metric')
    except (KeyError,ValueError,TypeError):
        return dict(**base,integrity_pass=False,profiles=None,error='malformed complete receipt')
    groups={}
    for r in rows:groups.setdefault(key(r)[:-1],[]).append(r)
    repeat_equal={str(k):len({r['pcm_sha256'] for r in v})==1 for k,v in groups.items()}
    profiles={}
    for engine in ENGINES:
        rr=[r for r in rows if r['engine']==engine and r['repeat']==0]
        tone=[r for r in rr if r['family']=='low61']; forms=[r for r in rr if r['family'].startswith('vowel') and r['shift']!=0]
        profiles[engine]=dict(cells=len(rr),pure_pass=sum(r['metrics']['tone']['passed'] for r in tone),pure_cells=len(tone),
            formant_nonidentity_cells=len(forms),mean_preserved_target_rmse_db=float(np.mean([r['metrics']['formant']['preserved_target_rmse_db'] for r in forms])),
            mean_off_target_rmse_db=float(np.mean([r['metrics']['formant']['off_target_rmse_db'] for r in forms])))
        profiles[engine]['repeat_equal_cells']=sum(len({r['pcm_sha256'] for r in group})==1 for k,group in groups.items() if k[3]==engine)
    return dict(**base,integrity_pass=True,profiles=profiles,repeated_cells=len(groups),repeat_equal_cells=sum(repeat_equal.values()),repeats=repeat_equal)

def prepare(reaper,sdk,out):
    out.mkdir(parents=True,exist_ok=False); inp=out/'input';inp.mkdir()
    files=m.file_map(host.ROOT);files.update(m.binary_map(sdk))
    # Hash vendor originals and loaded module files; never extract a proprietary API.
    for p in (reaper,reaper.parent/'libSwell.so',reaper.parent/'Plugins/elastique3.so'):
        files[str(p.resolve())]=c.fingerprint(p)
    sources=[]
    for family,rate in itertools.product(FAMILIES,RATES):
        x,meta=fixture(family,rate);p=inp/f'{family}-{rate}.wav';sf.write(p,x,rate,subtype='FLOAT')
        sources.append(dict(path=str(p),meta=meta,audio=c.inspect_audio(p)))
    plan=dict(schema='native-reaper-first-v1',base_main='1d01d9a59d4c2f6a9775dd9bc975195667639b4e',
              protocol_commit='40066e5edd24c59d79cee95a3938e3170db3a618',sources=sources,engines=list(ENGINES),profiles=host.PROFILES,sdk_profiles=SDK,shifts=list(SHIFTS),repeats=REPEATS,
              expected_attempts=720,time_ratio=1,files=files,reaper=str(reaper.resolve()),sdk=str(sdk.resolve()),
              environment=dict(python=sys.version,numpy=np.__version__,scipy=scipy.__version__,soundfile=sf.__version__),
              private_binaries_not_redistributed=True,quality_selection=None)
    c.json_write(out/'plan.json',plan);return c.fingerprint(out/'plan.json')

def check_plan(plan):
    if plan['engines']!=list(ENGINES) or plan['shifts']!=list(SHIFTS) or plan['repeats']!=3:raise ValueError('plan grid changed')
    for name,sha in plan['files'].items():
        if c.fingerprint(Path(name))!=sha:raise ValueError('changed source/binary: '+name)
    for s in plan['sources']:
        if c.inspect_audio(Path(s['path']))!=s['audio']:raise ValueError('changed input')

def run(planpath,sha,profile,out):
    if c.fingerprint(planpath)!=sha:raise ValueError('plan hash mismatch')
    plan=json.loads(planpath.read_text());check_plan(plan)
    out.mkdir(parents=True,exist_ok=False);audio=out/'audio';audio.mkdir(); jobs=[];requests=[]
    for source,shift,engine,repeat in itertools.product(plan['sources'],SHIFTS,ENGINES,range(3)):
        meta=source['meta']; identifier=f"{meta['family']}-{meta['rate']}-{shift:+d}-{engine}-{repeat}"
        output=audio/(identifier+'.wav');row=dict(family=meta['family'],rate=meta['rate'],shift=shift,engine=engine,repeat=repeat,id=identifier,status='failed',error=None)
        item=dict(source=source,row=row,output=output)
        if engine in host.PROFILES:
            item['job']=host.job(identifier,Path(source['path']),output,meta['rate'],meta['frames'],shift,engine)
            jobs.append(item['job'])
        requests.append(item)
    c.json_write(out/'request-grid.json',[v['row'] for v in requests])
    process=host.render(Path(plan['reaper']),profile,jobs,out/'reaper-host',sha)
    host_error=None
    try:host.require_process(process,len(jobs))
    except ValueError as exc:host_error=str(exc)
    rows=[]
    for item in requests:
        row=item['row'];meta=item['source']['meta'];output=item['output'];engine=row['engine']
        try:
            if engine in host.PROFILES:
                if host_error:raise ValueError(host_error)
                receipt,info=host.verify(item['job'],sha);row['host_receipt_sha256']=c.fingerprint(Path(item['job']['receipt']));row['render_seconds']=receipt['render_seconds']
            else:
                backend,quality,formant=SDK[engine]
                argv=[plan['sdk'],item['source']['path'],str(output),'--backend',backend,'--quality',quality,'--formant',formant,'--time','1','--pitch-semitones',str(row['shift']),'--block','64']
                if backend=='pv':argv.append('--allow-experimental')
                start=time.perf_counter();result=subprocess.run(argv,capture_output=True,text=True,timeout=30);elapsed=time.perf_counter()-start
                c.json_write(output.with_suffix('.json'),dict(argv=argv,returncode=result.returncode,stdout=result.stdout,stderr=result.stderr,wall_seconds=elapsed,plan_sha256=sha))
                if result.returncode:raise ValueError('SDK render failed: '+result.stderr)
                info=c.inspect_audio(output);errors=c.output_checks(item['source']['audio'],info,c.Request.from_semitones(1,row['shift']))
                if errors or info['rms']<=1e-8:raise ValueError('invalid SDK output '+str(errors))
                row['render_seconds']=elapsed
            y,sr=sf.read(output,dtype='float32');row.update(status='complete',output=str(output.relative_to(out)),audio=info,
                    pcm_sha256=hashlib.sha256(y.astype('<f4').tobytes()).hexdigest(),metrics=measure(y,meta,row['shift']))
        except (ValueError,OSError,KeyError,subprocess.SubprocessError) as exc:row.update(status='failed',error=str(exc))
        rows.append(row)
        with (out/'rows.jsonl').open('a') as f:f.write(json.dumps(row,allow_nan=False)+'\n')
        if len(rows)%60==0:print(len(rows),'/',len(requests),flush=True)
    check_plan(plan);summary=assess(rows);summary.update(plan_sha256=sha,rows=rows)
    c.json_write(out/'summary.json',summary);return summary

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);s=p.add_subparsers(dest='cmd',required=True)
    a=s.add_parser('prepare');a.add_argument('--reaper',type=Path,required=True);a.add_argument('--sdk',type=Path,required=True);a.add_argument('--out',type=Path,required=True)
    a=s.add_parser('run');a.add_argument('--plan',type=Path,required=True);a.add_argument('--sha',required=True);a.add_argument('--profile',type=Path,required=True);a.add_argument('--out',type=Path,required=True)
    a=p.parse_args()
    if a.cmd=='prepare':print(prepare(a.reaper,a.sdk,a.out))
    else:sys.exit(0 if run(a.plan,a.sha,a.profile,a.out)['integrity_pass'] else 2)
