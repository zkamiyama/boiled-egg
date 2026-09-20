#!/usr/bin/env python3
"""Fixed full-band landmark synthesis study; oracle markers are NOT detections."""
from __future__ import annotations
import argparse
import ctypes as ct
import hashlib
import itertools
import json
import math
from pathlib import Path
import resource
import statistics
import struct
import sys
import time
import numpy as np
from scipy import signal
import scipy
import soundfile as sf
import comparison_contract as contract
import offline_pv_benchmark as metrics
import wsola_offline as sdk

BASE = '18e74119694d869e01db22592941da887314795c'
PROTOCOL_COMMIT = '3438d30533a0a1e2f9c7519759fd0e955fe21907'
FAMILIES = ('tone41','tone61','tone83','tone97','harmonic61','bursts_sparse',
            'mixed61','dense83','missed61','offset61','false61','extension53')
ARMS = ('sdk_default','sdk_long_wide','free','snap','owned')
RATES = (48000,96000)
SHIFTS = (-12,0,12)
REPEATS = 3

class Config(ct.Structure):
    _fields_=[('struct_size',ct.c_uint32),('sample_rate',ct.c_uint32),('channels',ct.c_uint32),
              ('mode',ct.c_uint32),('pitch_ratio',ct.c_double),('memory_limit_bytes',ct.c_uint64)]
class Grain(ct.Structure):
    _fields_=[(k,ct.c_int64) for k in ('output_center','source_center','expected_center')]+[
        ('anchor_index',ct.c_int32),('masked_samples',ct.c_uint32),('correlation',ct.c_double)]
class Info(ct.Structure):
    _fields_=[(k,ct.c_uint64) for k in ('frames','grains','masked_samples','workspace_bytes')]+[
        ('min_weight',ct.c_double),('max_weight',ct.c_double)]

def fields(value):
    return {k:getattr(value,k) for k,_ in value._fields_}

class KernelError(ValueError):
    def __init__(self, code):
        super().__init__(f'kernel rejected request: {code}')
        self.code=code

class Native:
    def __init__(self,path:Path,sha:str):
        if contract.fingerprint(path)!=sha:raise ValueError('native hash mismatch')
        self.lib=ct.CDLL(str(path.resolve()))
        self.fn=self.lib.be_anchor_render
        self.fn.argtypes=[sdk.F32P,ct.c_uint64,ct.POINTER(ct.c_int64),ct.c_uint32,ct.POINTER(Config),
                          sdk.F32P,ct.POINTER(Grain),ct.c_uint64,ct.POINTER(Info)]
        self.fn.restype=ct.c_int
    def render(self,x,rate,shift,mode,marks):
        x=sdk.samples(x,rate)
        if mode not in ('free','snap','owned') or not math.isfinite(shift) or not -12<=shift<=12:
            raise ValueError('unsupported request')
        if len(marks)>16 or any(isinstance(a,bool) or not isinstance(a,(int,np.integer)) or not -(2**63)<=a<2**63 for a in marks):
            raise ValueError('at most16 integer sample landmarks')
        ma=np.asarray(marks,dtype=np.int64);y=np.empty_like(x);trace=(Grain*2048)();info=Info()
        c=Config(ct.sizeof(Config),rate,1,('free','snap','owned').index(mode),2**(shift/12),32*1024*1024)
        start=time.perf_counter()
        rc=self.fn(x.ctypes.data_as(sdk.F32P),len(x),ma.ctypes.data_as(ct.POINTER(ct.c_int64)),len(ma),
                   ct.byref(c),y.ctypes.data_as(sdk.F32P),trace,2048,ct.byref(info))
        elapsed=time.perf_counter()-start
        if rc:raise KernelError(rc)
        if info.frames!=len(x) or info.grains>2048 or not np.isfinite(y).all() or np.mean(y.astype(float)**2)<=1e-16:
            raise ValueError('invalid native result')
        return y,dict(**fields(info),render_seconds=elapsed,unity_bypass=shift==0,
                      trace=[fields(trace[i]) for i in range(info.grains)])


def fixture(name,rate):
    if name not in FAMILIES or rate not in RATES:raise ValueError('unknown fixture')
    t=np.arange(rate)/rate;x=np.zeros_like(t)
    f=None;amp=None;phase=0.;centers=[];sigma=.0015;carrier=4000.;harmonics=[]
    if name.startswith('tone'):
        f=float(name[4:]);amp=.2;phase=np.pi/3 if name=='tone97' else 0.
    elif name=='harmonic61':harmonics=[61*n for n in (1,2,3,5)]
    elif name=='false61':f=61.;amp=.2
    else:
        centers=[.24,.64]
        if name!='bursts_sparse':f=61.;amp=.08
        if name=='dense83':f=83.;centers=[.420,.447,.650]
        if name=='extension53':f=53.;phase=.37;centers=[.293,.681];sigma=.0025;carrier=3000.
    if f:
        x+=amp*np.sin(2*np.pi*f*t+phase)*np.minimum(1,np.minimum(t/.02,(1-t)/.02))
    if harmonics:
        for fr,a in zip(harmonics,(.12,.06,.03,.015)):x+=a*np.sin(2*np.pi*fr*t)
        x*=np.minimum(1,np.minimum(t/.02,(1-t)/.02))
    for center in centers:x+=.18*np.exp(-.5*((t-center)/sigma)**2)*np.cos(2*np.pi*carrier*(t-center))
    marks=centers.copy()
    if name=='missed61':marks=centers[:1]
    if name=='offset61':marks=[v+.002 for v in centers]
    if name=='false61':marks=[.24,.64]
    meta=dict(name=name,rate=rate,frames=rate,frequency=f,amplitude=amp,phase=phase,
              harmonics=harmonics,centers=centers,sigma=sigma,carrier=carrier,
              marker_condition='incorrect' if name in ('missed61','offset61','false61') else 'declared_correct',
              supplied_marks=[round(v*rate) for v in marks])
    return x.astype(np.float32),meta


def wav_bytes(x,rate):
    raw=np.asarray(x,dtype='<f4').tobytes()
    fmt=struct.pack('<HHIIHH',3,1,rate,rate*4,4,32)
    payload=b'WAVEfmt '+struct.pack('<I',16)+fmt+b'data'+struct.pack('<I',len(raw))+raw
    return b'RIFF'+struct.pack('<I',len(payload))+payload


def pcm_hash(x):return hashlib.sha256(np.asarray(x,dtype='<f4').tobytes()).hexdigest()

def pure(y,rate,f,amp):
    v=y[round(.15*rate):round(.85*rate)]
    a,residual=metrics.components(v,rate,[f])
    return dict(cents=metrics.tone_error(v,rate,f),amplitude_error_db=float(20*np.log10(max(a[0],1e-30)/amp)),
                unexplained_energy=residual)

def tone_pass(m):return abs(m['cents'])<=5 and abs(m['amplitude_error_db'])<=1 and m['unexplained_energy']<=.01

def event_windows(y,oracle,rate,centers):
    out=[]
    for i,center in enumerate(centers):
        left=max(center-.08,(center+centers[i-1])/2 if i else 0)
        right=min(center+.08,(center+centers[i+1])/2 if i+1<len(centers) else len(y)/rate)
        lo,hi=round(left*rate),round(right*rate);t=np.arange(lo,hi)/rate
        def one(value):
            e=value[lo:hi]**2;total=float(e.sum())
            if total<=1e-16:return dict(energy=total,position_ms=None,width_ms=None)
            q=np.searchsorted(np.cumsum(e)/total,[.05,.95])
            return dict(energy=total,position_ms=float((np.dot(e,t)/total-center)*1000),width_ms=float((q[1]-q[0])*1000/rate))
        a,b=one(y),one(oracle)
        a['oracle']=b;a['energy_error_db']=float(10*np.log10(max(a['energy'],1e-30)/b['energy']))
        a['pass']=a['position_ms'] is not None and abs(a['position_ms'])<=1 and a['width_ms']<=1.2*b['width_ms'] and abs(a['energy_error_db'])<=3
        out.append(a)
    return out

def measure(y,meta,shift):
    y=metrics.valid_vector(y);rate=meta['rate'];p=2**(shift/12)
    if len(y)!=meta['frames']:raise ValueError('wrong duration')
    result=dict(peak=float(np.max(np.abs(y))),rms=float(np.sqrt(np.mean(y*y))),max_sample_step=float(np.max(np.abs(np.diff(y)))))
    if meta['frequency'] and not meta['centers']:
        result['pure']=pure(y,rate,meta['frequency']*p,meta['amplitude'])
    if meta['harmonics']:
        a,r=metrics.components(y[round(.15*rate):round(.85*rate)],rate,[f*p for f in meta['harmonics']])
        result['harmonic']=dict(amplitudes=a,unexplained_energy=r)
    if meta['centers']:
        t=np.arange(len(y))/rate;oracle=np.zeros_like(t)
        for center in meta['centers']:
            oracle+=.18*np.exp(-.5*((t-center)*p/meta['sigma'])**2)*np.cos(2*np.pi*meta['carrier']*p*(t-center))
        sos=signal.butter(4,1000,btype='highpass',fs=rate,output='sos')
        high=signal.sosfiltfilt(sos,y);ohigh=signal.sosfiltfilt(sos,oracle)
        result['events']=event_windows(high,ohigh,rate,meta['centers'])
        in_regions=np.zeros(len(y),dtype=bool)
        for center in meta['centers']:in_regions|=np.abs(t-center)<=3*meta['sigma']/p
        result['outside_event_fraction']=float(np.sum(high[~in_regions]**2)/max(np.sum(high**2),1e-30))
        result['oracle_outside_event_fraction']=float(np.sum(ohigh[~in_regions]**2)/np.sum(ohigh**2))
        if meta['name']=='bursts_sparse':result['raw_events']=metrics.events(y,rate,meta['centers'])
        if meta['frequency']:
            low=signal.sosfiltfilt(signal.butter(4,500,btype='lowpass',fs=rate,output='sos'),y)
            result['bass']=pure(low,rate,meta['frequency']*p,meta['amplitude'])
    return result


def prepare(native,library,out):
    out.mkdir(parents=True,exist_ok=False);src=out/'input';src.mkdir()
    files=metrics.file_map(Path(__file__).resolve().parents[1])
    for binary in (native,library):files.update(metrics.binary_map(binary))
    sources=[]
    for name,rate in itertools.product(FAMILIES,RATES):
        x,meta=fixture(name,rate);path=src/f'{name}-{rate}.wav';path.write_bytes(wav_bytes(x,rate))
        markfile=src/f'{name}-{rate}.marks.json';contract.json_write(markfile,meta['supplied_marks'])
        sources.append(dict(path=str(path.resolve()),marks=str(markfile.resolve()),metadata=meta,
                            audio=contract.inspect_audio(path),marks_sha256=contract.fingerprint(markfile)))
    plan=dict(schema='anchor-ownership-v1',base=BASE,protocol_commit=PROTOCOL_COMMIT,
        native=str(native.resolve()),sdk=str(library.resolve()),files=files,sources=sources,
        arms=list(ARMS),shifts=list(SHIFTS),repeats=3,cells=360,runs=1080,
        environment=dict(python=sys.version,numpy=np.__version__,scipy=scipy.__version__,soundfile=sf.__version__),
        quality_selection=None,marker_claim='supplied diagnostic markers; NOT a detector')
    contract.json_write(out/'plan.json',plan)

def identity(plan):
    if plan['schema']!='anchor-ownership-v1' or plan['arms']!=list(ARMS) or plan['shifts']!=list(SHIFTS) or plan['repeats']!=3:
        raise ValueError('wrong fixed grid')
    keys=[(s['metadata']['name'],s['metadata']['rate']) for s in plan['sources']]
    if len(keys)!=len(set(keys)) or set(keys)!=set(itertools.product(FAMILIES,RATES)):raise ValueError('missing/duplicate input grid')
    for path,sha in plan['files'].items():
        if contract.fingerprint(Path(path))!=sha:raise ValueError(f'changed source/binary: {path}')
    for s in plan['sources']:
        if contract.inspect_audio(Path(s['path']))!=s['audio'] or contract.fingerprint(Path(s['marks']))!=s['marks_sha256']:
            raise ValueError('changed input/marks')

def row_key(r):return (r['family'],r['rate'],r['shift'],r['arm'],r['repeat'])

def assess(rows):
    expected=set(itertools.product(FAMILIES,RATES,SHIFTS,ARMS,range(REPEATS)))
    keys=[row_key(r) for r in rows]
    if len(keys)!=len(set(keys)) or set(keys)!=expected:raise ValueError('incomplete/duplicate output grid')
    grouped={}
    for r in rows:grouped.setdefault(row_key(r)[:-1],[]).append(r)
    repeat_equal=all(len({(r['status'],r.get('pcm_sha256'),tuple(r['errors'])) for r in rr})==1 for rr in grouped.values())
    unique=[r for r in rows if r['repeat']==0];by={(r['family'],r['rate'],r['shift'],r['arm']):r for r in unique}
    profiles={}
    for arm in ARMS:
        rr=[r for r in unique if r['arm']==arm]
        tones=[r for r in rr if r['family'].startswith('tone')]
        positive=[r for r in rr if r['family'] in ('bursts_sparse','mixed61','dense83','extension53')]
        mixtures=[r for r in positive if r['family']!='bursts_sparse']
        def done(r):return r['status']=='complete'
        stops=[]
        for r in positive:
            base=by[r['family'],r['rate'],r['shift'],'sdk_default']
            if not done(r):
                stops.append(dict(family=r['family'],rate=r['rate'],shift=r['shift'],rejected=r['status']));continue
            for i,(e,b) in enumerate(zip(r['metrics']['events'],base['metrics']['events'])):
                if e['position_ms'] is None or b['position_ms'] is None or abs(e['position_ms'])>abs(b['position_ms'])+1 or e['width_ms']>1.2*b['width_ms']:
                    stops.append(dict(family=r['family'],rate=r['rate'],shift=r['shift'],event=i))
        def bass_ok(r):return done(r) and tone_pass(r['metrics']['bass'])
        def events_ok(r):return done(r) and all(e['pass'] for e in r['metrics']['events'])
        times=[statistics.median(v['timing_seconds'] for v in gr) for k,gr in grouped.items() if k[-1]==arm and all(done(v) for v in gr)]
        profiles[arm]=dict(total_cells=len(rr),rendered_cells=sum(done(r) for r in rr),
            rejected_cells=[dict(family=r['family'],rate=r['rate'],shift=r['shift'],status=r['status']) for r in rr if not done(r)],
            pure_cells=len(tones),pure_pass=sum(done(r) and tone_pass(r['metrics']['pure']) for r in tones),
            max_pure_cents=max((abs(r['metrics']['pure']['cents']) for r in tones if done(r)),default=None),
            mixture_cells=len(mixtures),bass_pass=sum(bass_ok(r) for r in mixtures),
            correct_event_cells=len(positive),event_cells_pass=sum(events_ok(r) for r in positive),
            joint_mixture_pass=sum(bass_ok(r) and events_ok(r) for r in mixtures),
            default_relative_stops=stops,
            timing_rendered_cells=len(times),median_rendered_cell_time=statistics.median(times) if times else None)
    integrity=all(r['status'] in ('complete','rejected_uncovered') for r in rows) and repeat_equal
    return dict(grid_complete=True,execution_complete=all(r['status']=='complete' for r in rows),
                integrity_pass=integrity,repeats_identical=repeat_equal,
                rendered=sum(r['status']=='complete' for r in rows),
                uncovered=sum(r['status']=='rejected_uncovered' for r in rows),
                profiles=profiles,quality_selection=None,decision='research_only_no_product_promotion',real_time_qualified=False)


def run(plan_path,sha,out):
    if contract.fingerprint(plan_path)!=sha:raise ValueError('plan SHA mismatch')
    plan=json.loads(plan_path.read_text());identity(plan)
    out.mkdir(parents=True,exist_ok=False);objects=out/'objects';objects.mkdir()
    native=Native(Path(plan['native']),plan['files'][plan['native']]);old=sdk.Native(Path(plan['sdk']),plan['files'][plan['sdk']])
    x,_=fixture('tone61',48000)
    _,cold=old.render(x,48000,0,'default',64);contract.json_write(out/'sdk-cold.json',cold)
    rows=[]
    for s,shift,arm in itertools.product(plan['sources'],SHIFTS,ARMS):
        x,rate=sdk.read_input(Path(s['path']));marks=json.loads(Path(s['marks']).read_text())
        for repeat in range(REPEATS):
            row=dict(family=s['metadata']['name'],rate=rate,shift=shift,arm=arm,repeat=repeat,status='failed',errors=[],
                     input_sha256=s['audio']['sha256'],marks_sha256=s['marks_sha256'])
            try:
                if arm.startswith('sdk_'):
                    y,info=old.render(x,rate,shift,arm[4:],64);elapsed=info['host_render_seconds']
                else:
                    y,info=native.render(x,rate,shift,arm,[] if arm=='free' else marks);elapsed=info['render_seconds']
                raw=wav_bytes(y,rate);h=hashlib.sha256(raw).hexdigest();path=objects/(h+'.wav')
                if not path.exists():path.write_bytes(raw)
                row.update(status='complete',output=str(path.relative_to(out)),wav_sha256=h,pcm_sha256=pcm_hash(y),
                           timing_seconds=elapsed,native=info,metrics=measure(y,s['metadata'],shift))
            except KernelError as e:
                row['status']='rejected_uncovered' if e.code==4 else 'failed';row['errors']=[str(e)]
            except (ValueError,RuntimeError,OSError) as e:row['status']='failed';row['errors']=[str(e)]
            rows.append(row)
            with (out/'rows.jsonl').open('a') as f:f.write(json.dumps(row,allow_nan=False)+'\n')
        if len(rows)%90==0:print(f'{len(rows)}/1080',flush=True)
    identity(plan);summary=assess(rows);summary.update(plan_sha256=sha,rows=rows,peak_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    contract.json_write(out/'summary.json',summary);return summary


def main():
    p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest='cmd',required=True)
    a=sub.add_parser('prepare');a.add_argument('--native',type=Path,required=True);a.add_argument('--sdk',type=Path,required=True);a.add_argument('--output',type=Path,required=True)
    a=sub.add_parser('run');a.add_argument('--plan',type=Path,required=True);a.add_argument('--plan-sha256',required=True);a.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    if a.cmd=='prepare':prepare(a.native,a.sdk,a.output);print(contract.fingerprint(a.output/'plan.json'));return 0
    result=run(a.plan,a.plan_sha256,a.output)
    return 0 if result['integrity_pass'] else 2
if __name__=='__main__':raise SystemExit(main())
