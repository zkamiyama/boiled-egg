#!/usr/bin/env python3
"""Seven preservation presets and bounded extreme baseline; no product DSP changes."""
from __future__ import annotations
import argparse
import hashlib
import itertools
import json
import math
from pathlib import Path
import subprocess
import sys
import time
import numpy as np
import scipy
from scipy import signal
import soundfile as sf
import extreme_contract as e
import study as old
h=e.h;c=h.c;m=old.m
RATES=(48000,96000)
PITCHES=(-24,-12,12,24)
DEVELOP=('vowel120','vowel220')
CONFIRM=('confirm97','confirm311')
BOUNDARY=('low61','bursts','mixed61')
OPERATIONS=((1,0),(.25,0),(.5,0),(2,0),(4,0),(1,-24),(1,24),(2,12),(.5,-12),(1,7),(1.5,-5))
PRESET_ENGINES=tuple(e.PRO)+('sdk_harmonic','sdk_monophonic')
BOUNDARY_ENGINES=('pro_off','sdk_wsola','sdk_pv_off','sdk_pv_transient')
STAGES=('development','confirmation','boundary')
BASE='6f3ed4508a1c0123539f2e32b8fd37dd8ebdb168'
PROTOCOL='201a460f27f1194251042d25955f3faa61d1332a'


def envelope(f, confirm=False):
    if not confirm:return old.envelope(f)
    return .08+np.exp(-.5*((f-730)/110)**2)+.8*np.exp(-.5*((f-1420)/150)**2)+.6*np.exp(-.5*((f-2850)/210)**2)


def fixture(family,rate):
    if family in DEVELOP+BOUNDARY:
        x,meta=old.fixture(family,rate)
    elif family in CONFIRM:
        f0=int(family[7:]);t=np.arange(2*rate)/rate;k=np.arange(1,31)
        amps=.03*envelope(k*f0,True)/k**.7
        x=sum(a*np.sin(2*np.pi*n*f0*t+.29*n) for n,a in zip(k,amps))
        x*=np.minimum(1,np.minimum(t/.03,(2-t)/.03));x=x.astype(np.float32)
        meta=dict(family=family,rate=rate,frames=len(x),frequency=None,centers=[],f0=f0,
                  harmonics=30,source_amplitudes=amps.tolist(),formants=[730,1420,2850])
    else:raise ValueError('unknown source')
    return x,meta


def grid(stage):
    if stage not in STAGES:raise ValueError('unknown stage')
    families=DEVELOP if stage=='development' else CONFIRM if stage=='confirmation' else BOUNDARY
    operations=tuple((1,p) for p in PITCHES) if stage!='boundary' else OPERATIONS
    engines=PRESET_ENGINES if stage!='boundary' else BOUNDARY_ENGINES
    return list(itertools.product(families,RATES,operations,engines,range(3)))


def key(row):return (row['family'],row['rate'],(row['time_ratio'],row['shift']),row['engine'],row['repeat'])


def event_measure(y,meta,request):
    rate=meta['rate'];p=request.pitch_ratio;T=request.duration_ratio
    centers=[a*T for a in meta['centers']];t=np.arange(len(y))/rate
    oracle=sum(.18*np.exp(-.5*((t-a)/(.0015/p))**2)*np.cos(2*np.pi*3500*p*(t-a)) for a in centers)
    filt=signal.butter(4,1000,btype='highpass',fs=rate,output='sos')
    high=signal.sosfiltfilt(filt,y);target=signal.sosfiltfilt(filt,oracle)
    radius=min(.08,.35*T);mask=np.ones(len(y),bool);events=[]
    def one(x,lo,hi,center):
        v=np.asarray(x[lo:hi],float);energy=v*v;total=float(energy.sum())
        if total<=1e-16:return dict(missing=True,energy=total,position_ms=None,width_ms=None)
        q=np.searchsorted(np.cumsum(energy)/total,[.05,.95])
        return dict(missing=False,energy=total,position_ms=float(np.dot(np.arange(lo,hi)/rate-center,energy)/total*1000),width_ms=float((q[1]-q[0])*1000/rate))
    for a in centers:
        lo=max(0,round((a-radius)*rate));hi=min(len(y),round((a+radius)*rate));mask[lo:hi]=False
        v=one(high,lo,hi,a);ref=one(target,lo,hi,a)
        v.update(center_seconds=a,oracle=ref,energy_error_db=float(10*np.log10(max(v['energy'],1e-30)/ref['energy'])))
        v['passed']=not v['missing'] and abs(v['position_ms'])<=1 and v['width_ms']<=1.2*ref['width_ms'] and abs(v['energy_error_db'])<=3
        events.append(v)
    return dict(events=events,outside_energy=float(np.sum(high[mask]**2)),oracle_outside_energy=float(np.sum(target[mask]**2)),
                scope='same highpass; centroid is not onset; mixed output is not a separated event')


def measure(y,meta,request):
    y=m.valid_vector(y);rate=meta['rate'];p=request.pitch_ratio;T=request.duration_ratio
    if len(y)!=request.target_frames(meta['frames']):raise ValueError('exact output length mismatch')
    lo,hi=round(.5*T*rate),round(1.5*T*rate)
    result=dict(peak=float(np.max(abs(y))),rms=float(np.sqrt(np.mean(y*y))))
    if meta['frequency']:
        z=y if not meta['centers'] else signal.sosfiltfilt(signal.butter(4,500,fs=rate,output='sos'),y)
        z=z[lo:hi];a,res=m.components(z,rate,[meta['frequency']*p]);cents=m.tone_error(z,rate,meta['frequency']*p)
        db=float(20*np.log10(max(a[0],1e-30)/meta['amplitude']))
        result['tone']=dict(cents=cents,amplitude_db=db,unexplained_energy=res,passed=abs(cents)<=5 and abs(db)<=1 and res<=.01,
                            scope='pure' if not meta['centers'] else 'lowpass mixture diagnostic')
    if 'f0' in meta:
        k=np.arange(1,31);freq=k*meta['f0']*p;valid=freq<.45*rate
        a,res=m.components(y[lo:hi],rate,freq[valid].tolist());a=np.asarray(a)
        off=np.asarray(meta['source_amplitudes'])[valid]
        pres=.03*envelope(freq[valid],meta['family'] in CONFIRM)/k[valid]**.7
        select=(freq[valid]>=250)&(freq[valid]<=3500)&(np.maximum(off,pres)>=.00015)
        if not np.any(select):raise ValueError('no measurable envelope samples')
        def rmse(target):return float(np.sqrt(np.mean((20*np.log10(np.maximum(a[select],1e-12)/target[select]))**2)))
        result['formant']=dict(preserved_target_rmse_db=rmse(pres),off_target_rmse_db=rmse(off),unexplained_energy=res,
            fundamental_amplitude=float(a[0]),fundamental_target=float(pres[0]),harmonics_measured=int(np.sum(select)),
            excluded_harmonics=k[~valid].tolist(),target_frequencies=freq[valid].tolist(),measured_amplitudes=a.tolist(),no_gain_or_lag_fit=True)
    if meta['centers']:result.update(event_measure(y,meta,request))
    return result


def assess(rows,stage):
    keys=[key(r) for r in rows]
    if len(keys)!=len(set(keys)) or set(keys)!=set(grid(stage)):raise ValueError('incomplete/duplicate grid')
    failures=[];unavailable=[];complete=[]
    for r in rows:
        k=key(r);engine=r['engine'];request=e.Request(r['time_ratio'],r['shift'])
        expected=e.expected_status(engine,request) if engine in e.SDK else 0
        if r['status']=='unsupported':
            cap=r.get('capability',{})
            if expected!=7 or cap.get('status')!=7 or cap.get('expected_status')!=7 or r.get('output') or r.get('metrics'):
                failures.append(dict(key=k,error='fabricated unsupported result'))
            else:unavailable.append(k)
        elif r['status']=='complete':
            try:
                if expected!=0:raise ValueError('out-of-scope completion')
                for field in ('pcm_sha256','receipt_sha256'):
                    value=r[field]
                    if not isinstance(value,str) or len(value)!=64 or any(ch not in '0123456789abcdef' for ch in value):raise ValueError('hash')
                metric=r['metrics'];json.dumps(metric,allow_nan=False)
                if not math.isfinite(metric['peak']) or not math.isfinite(metric['rms']) or metric['peak']<=0 or metric['rms']<=1e-8:raise ValueError('empty/nonfinite metric')
                if r['family'] in DEVELOP+CONFIRM:
                    for name in ('preserved_target_rmse_db','off_target_rmse_db','unexplained_energy'):
                        if not math.isfinite(metric['formant'][name]):raise ValueError('formant metric')
                if r['family'] in ('low61','mixed61'):
                    for name in ('cents','amplitude_db','unexplained_energy'):
                        if not math.isfinite(metric['tone'][name]):raise ValueError('tone metric')
                    if type(metric['tone']['passed']) is not bool:raise ValueError('tone gate')
                if r['family'] in ('bursts','mixed61'):
                    if len(metric['events'])!=2:raise ValueError('event count')
                    for ev in metric['events']:
                        if type(ev['missing']) is not bool or type(ev['passed']) is not bool:raise ValueError('event gate')
                        if ev['missing'] and ev['passed']:raise ValueError('missing event passed')
                complete.append(r)
            except (KeyError,ValueError,TypeError):failures.append(dict(key=k,error='malformed completion'))
        else:failures.append(dict(key=k,error=r.get('error','unknown failure')))
    repeated={}
    for r in rows:
        repeated.setdefault(key(r)[:-1],set()).add((r['status'],r.get('pcm_sha256')))
    same=all(len(v)==1 for v in repeated.values())
    return dict(stage=stage,attempts=len(rows),rendered=len(complete),unsupported=len(unavailable),failures=failures,
                integrity_pass=not failures and same,repeats_identical=same,all_requested_rendered=not failures and not unavailable,
                quality_selection=None)


def select(summary,output):
    if summary['stage']!='development':raise ValueError('selection must use development only')
    result=assess(summary['rows'],'development')
    if not result['integrity_pass']:raise ValueError('development failed')
    choices={}
    for shift in PITCHES:
        choices[str(shift)]={}
        for group,engines in [('vendor',tuple(e.PRO)),('sdk',('sdk_harmonic','sdk_monophonic'))]:
            scores={}
            for engine in engines:
                rr=[r for r in summary['rows'] if r['engine']==engine and r['shift']==shift and r['repeat']==0]
                if len(rr)!=4:raise ValueError('missing development group')
                if all(r['status']=='complete' for r in rr):scores[engine]=float(np.mean([r['metrics']['formant']['preserved_target_rmse_db'] for r in rr]))
            best=min(scores,key=lambda engine:(scores[engine],engines.index(engine))) if scores else None
            choices[str(shift)][group]=dict(engine=best,development_scores=scores)
    record=dict(schema='extreme-preset-selection-v1',plan_sha256=summary['plan_sha256'],development_sources=list(DEVELOP),
                choices=choices,objective='mean preserved-envelope RMSE; diagnostic only, not MOS or product selection',quality_selection=None)
    if output.exists():raise ValueError('selection already frozen')
    c.json_write(output,record);return c.fingerprint(output)


def prepare(reaper,sdk,out):
    out.mkdir(parents=True,exist_ok=False);inp=out/'inputs';inp.mkdir()
    files=m.file_map(h.ROOT);files.update(m.binary_map(sdk));lib=sdk.parent/'libboiled_egg.so'
    cap=e.Capability(lib,c.fingerprint(lib));files.update(m.binary_map(lib))
    for p in (reaper,reaper.parent/'libSwell.so',reaper.parent/'Plugins/elastique3.so'):
        files[str(p.resolve())]=c.fingerprint(p)
    sources={}
    for family,rate in itertools.product(DEVELOP+CONFIRM+BOUNDARY,RATES):
        x,meta=fixture(family,rate);p=inp/f'{family}-{rate}.wav';sf.write(p,x,rate,subtype='FLOAT')
        sources[f'{family}-{rate}']=dict(path=str(p.resolve()),meta=meta,audio=c.inspect_audio(p))
    if len({v['audio']['sha256'] for v in sources.values()})!=len(sources):raise ValueError('duplicate source bytes')
    plan=dict(schema='extreme-presets-v1',base_main=BASE,protocol_commit=PROTOCOL,sources=sources,files=files,
        reaper=str(reaper.resolve()),sdk=str(sdk.resolve()),library=str(lib.resolve()),backend_inventory=cap.inventory,
        grids={stage:[list((a,b,list(op),d,r)) for a,b,op,d,r in grid(stage)] for stage in STAGES},
        vendor_profiles=e.VENDOR,sdk_profiles=e.SDK,expected_attempts=1656,
        environment=dict(python=sys.version,numpy=np.__version__,scipy=scipy.__version__,soundfile=sf.__version__),quality_selection=None)
    c.json_write(out/'plan.json',plan);return c.fingerprint(out/'plan.json')


def check_plan(plan):
    if plan.get('schema')!='extreme-presets-v1':raise ValueError('unknown plan')
    for stage in STAGES:
        actual=[(a,b,tuple(op),d,r) for a,b,op,d,r in plan['grids'][stage]]
        if actual!=grid(stage):raise ValueError('changed registered grid')
    for path,sha in plan['files'].items():
        if c.fingerprint(Path(path))!=sha:raise ValueError('changed source/binary '+path)
    for source in plan['sources'].values():
        if c.inspect_audio(Path(source['path']))!=source['audio']:raise ValueError('changed input')


def run(planpath,sha,profile,out,stage,selection=None,selection_sha=None):
    if c.fingerprint(planpath)!=sha:raise ValueError('plan identity mismatch')
    plan=json.loads(planpath.read_text());check_plan(plan)
    if stage=='confirmation':
        if selection is None or c.fingerprint(selection)!=selection_sha:raise ValueError('frozen selection required')
        lock=json.loads(selection.read_text())
        if lock['plan_sha256']!=sha or lock['development_sources']!=list(DEVELOP):raise ValueError('selection identity')
    out.mkdir(parents=True,exist_ok=False);audio=out/'audio';audio.mkdir();requests=[];jobs=[]
    cap=e.Capability(Path(plan['library']),plan['files'][plan['library']])
    for family,rate,(T,shift),engine,repeat in grid(stage):
        source=plan['sources'][f'{family}-{rate}'];req=e.Request(T,shift)
        identifier=f'{family}-{rate}-t{T}-p{shift}-{engine}-{repeat}'
        output=audio/(identifier+'.wav')
        row=dict(id=identifier,family=family,rate=rate,time_ratio=T,shift=shift,engine=engine,repeat=repeat,status='failed')
        item=dict(source=source,row=row,output=output,request=req)
        if engine in e.VENDOR:
            item['job']=e.job(identifier,Path(source['path']),output,rate,source['meta']['frames'],req,engine);jobs.append(item['job'])
        else:
            row['capability']=cap.validate(engine,rate,req)
            if row['capability']['status']==7:row['status']='unsupported'
        requests.append(item)
    c.json_write(out/'request-grid.json',[i['row'] for i in requests])
    process=h.render(Path(plan['reaper']),profile,jobs,out/'reaper-host',sha)
    host_error=None
    try:h.require_process(process,len(jobs))
    except ValueError as exc:host_error=str(exc)
    rows=[]
    for item in requests:
        row=item['row'];source=item['source'];output=item['output'];engine=row['engine'];req=item['request']
        try:
            if row['status']=='unsupported':
                c.json_write(output.with_suffix('.json'),dict(**row,plan_sha256=sha,not_rendered=True))
            else:
                if engine in e.VENDOR:
                    if host_error:raise ValueError(host_error)
                    receipt,info=e.verify(item['job'],sha);row['render_seconds']=receipt['render_seconds']
                else:
                    backend,quality,policy=e.SDK[engine]
                    argv=[plan['sdk'],source['path'],str(output),'--backend',backend,'--quality',quality,'--formant',policy,
                          '--time',str(req.duration_ratio),'--pitch-ratio',format(row['capability']['pitch_float32'],'.17g'),'--block','64']
                    if backend=='pv':argv.append('--allow-experimental')
                    started=time.perf_counter();p=subprocess.run(argv,text=True,capture_output=True,timeout=60);elapsed=time.perf_counter()-started
                    c.json_write(output.with_suffix('.json'),dict(argv=argv,returncode=p.returncode,stdout=p.stdout,stderr=p.stderr,wall_seconds=elapsed,plan_sha256=sha))
                    if p.returncode:raise ValueError('SDK failed: '+p.stderr)
                    info=c.inspect_audio(output);errors=c.output_checks(source['audio'],info,req)
                    if errors or info['rms']<=1e-8:raise ValueError('invalid SDK output '+repr(errors))
                    row['render_seconds']=elapsed
                y,sr=sf.read(output,dtype='float32')
                row.update(status='complete',output=str(output.relative_to(out)),audio=info,
                           pcm_sha256=hashlib.sha256(y.astype('<f4').tobytes()).hexdigest(),metrics=measure(y,source['meta'],req))
            row['receipt']=str(output.with_suffix('.json').relative_to(out));row['receipt_sha256']=c.fingerprint(output.with_suffix('.json'))
        except (ValueError,OSError,KeyError,subprocess.SubprocessError) as exc:
            row.update(status='failed',error=str(exc))
        rows.append(row)
        with (out/'rows.jsonl').open('a') as f:f.write(json.dumps(row,allow_nan=False)+'\n')
        if len(rows)%72==0:print(stage,len(rows),'/',len(requests),flush=True)
    check_plan(plan)
    if stage=='confirmation' and c.fingerprint(selection)!=selection_sha:raise ValueError('selection changed during confirmation')
    summary=assess(rows,stage);summary.update(rows=rows,plan_sha256=sha,selection_sha256=selection_sha)
    c.json_write(out/'summary.json',summary);return summary


def main():
    parser=argparse.ArgumentParser(description=__doc__);sub=parser.add_subparsers(dest='cmd',required=True)
    p=sub.add_parser('prepare');p.add_argument('--reaper',type=Path,required=True);p.add_argument('--sdk',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    p=sub.add_parser('run');p.add_argument('--plan',type=Path,required=True);p.add_argument('--sha',required=True);p.add_argument('--profile',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--stage',choices=STAGES,required=True);p.add_argument('--selection',type=Path);p.add_argument('--selection-sha')
    p=sub.add_parser('select');p.add_argument('--summary',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    a=parser.parse_args()
    if a.cmd=='prepare':print(prepare(a.reaper,a.sdk,a.out));return 0
    if a.cmd=='select':print(select(json.loads(a.summary.read_text()),a.out));return 0
    return 0 if run(a.plan,a.sha,a.profile,a.out,a.stage,a.selection,a.selection_sha)['integrity_pass'] else 2
if __name__=='__main__':raise SystemExit(main())
