#!/usr/bin/env python3
"""Fixed NSDGT numerical study. This is not a pitch/time quality evaluator."""
from __future__ import annotations
import argparse
import ctypes as ct
import hashlib
import itertools
import json
from pathlib import Path
import resource
import re
import sys
import time
import numpy as np
import comparison_contract as contract
from offline_pv_benchmark import binary_map, file_map

BASE='c8ffe65a24d21e627a3558883497daeb853473de'
PROTOCOL='f4cfab538806cef939341a13b9f8905d5e95050b'
RATES=(22050,48000,96000)
SIGNALS=('first','middle','last','tone61','dc','noise','chirp','zero')
SCHEDULES=('fixed','smooth','abrupt','irregular')
REPEATS=3
P=ct.POINTER(ct.c_float)
D=ct.POINTER(ct.c_double)
class Config(ct.Structure):
    _fields_=[('struct_size',ct.c_uint32),('fft_size',ct.c_uint32),('frames',ct.c_uint64),('memory_limit_bytes',ct.c_uint64)]
class Frame(ct.Structure):
    _fields_=[('center',ct.c_int64),('window_length',ct.c_uint32),('window_offset',ct.c_uint32)]
class Info(ct.Structure):
    _fields_=[('coefficient_count',ct.c_uint64),('storage_estimate_bytes',ct.c_uint64)]+[(k,ct.c_double) for k in ('minimum_diagonal','maximum_diagonal','condition_number','maximum_dual')]
class NativeError(ValueError):
    def __init__(self,code):
        super().__init__(f'native rejection {code}');self.code=code

def phash(x):return hashlib.sha256(np.asarray(x,dtype='<c8').tobytes()).hexdigest()

def pack(n,m,centers,windows,budget=256*1024*1024):
    if type(n)!=int or not 1<=n<=288000 or type(m)!=int or m<16 or m>16384 or m&(m-1):
        raise ValueError('invalid signal/FFT shape')
    if len(centers)!=len(windows) or not 1<=len(centers)<=4096:raise ValueError('invalid schedule count')
    if len(centers)*m>8388608:raise ValueError('coefficient budget')
    fr=(Frame*len(centers))();parts=[];offset=0
    for j,(center,w) in enumerate(zip(centers,windows)):
        if type(center)!=int or not 0<=center<n or (j and center<=centers[j-1]):raise ValueError('invalid centers')
        w=np.asarray(w,dtype=np.float64)
        if w.ndim!=1 or not 2<=len(w)<=m or not np.isfinite(w).all() or np.max(np.abs(w))>1:
            raise ValueError('invalid window')
        fr[j]=Frame(center,len(w),offset);offset+=len(w);parts.append(w)
    win=np.ascontiguousarray(np.concatenate(parts),dtype=np.float64)
    return Config(ct.sizeof(Config),m,n,budget),fr,win

class Native:
    def __init__(self,path,sha):
        path=Path(path).resolve(strict=True)
        if contract.fingerprint(path)!=sha:raise ValueError('library hash mismatch')
        self.lib=ct.CDLL(str(path))
        for name in ('be_nsg_analyze','be_nsg_synthesize'):
            fn=getattr(self.lib,name)
            fn.argtypes=[ct.POINTER(Config),ct.POINTER(Frame),ct.c_uint32,D,ct.c_uint64,P,ct.c_uint64,P,ct.c_uint64,ct.POINTER(Info)]
            fn.restype=ct.c_int
    def call(self,forward,value,shape):
        c,fr,w=shape;size=c.frames if forward else c.fft_size*len(fr)
        raw=np.asarray(value)
        if raw.ndim!=1 or len(raw)!=size or not np.isfinite(raw).all():raise ValueError('invalid source buffer')
        x=np.ascontiguousarray(raw,dtype=np.complex64)
        if not np.isfinite(x).all():raise ValueError('float cast overflow')
        out=np.full(c.fft_size*len(fr) if forward else c.frames,-99+11j,dtype=np.complex64);info=Info()
        fn=self.lib.be_nsg_analyze if forward else self.lib.be_nsg_synthesize
        start=time.perf_counter()
        rc=fn(ct.byref(c),fr,len(fr),w.ctypes.data_as(D),len(w),x.ctypes.data_as(P),len(x),out.ctypes.data_as(P),len(out),ct.byref(info))
        duration=time.perf_counter()-start
        if rc:
            if not np.all(out==np.complex64(-99+11j)):raise RuntimeError('failure modified output')
            raise NativeError(rc)
        if not np.isfinite(out).all():raise ValueError('nonfinite output')
        return out,{k:getattr(info,k) for k,_ in info._fields_},duration

def schedule(n,m,name):
    if name not in SCHEDULES:raise ValueError('unknown schedule')
    centers=[];center=0;j=0
    while center<n:
        centers.append(center)
        step=m//4 if name=='fixed' else (m//64*(1,3,2,4)[j%4] if name=='irregular' else m//32)
        center+=step;j+=1
    centers=sorted(set(centers+[n-1]));windows=[]
    for j,a in enumerate(centers):
        if name=='fixed':length=m
        elif name=='smooth':length=max(m//8,round(m*(.5625+.4375*np.cos(2*np.pi*a/max(n-1,1)))))
        elif name=='abrupt':length=(m,m//8)[j%2]
        else:length=(m,m//2,m//8,m//4)[j%4]
        w=np.hanning(length)
        if name=='abrupt' and j%2:w=np.sqrt(w)
        if name=='irregular' and j%3==2:w=np.ones(length)
        windows.append(w)
    return centers,windows

def source(n,rate,name):
    t=np.arange(n)/rate;x=np.zeros(n,dtype=np.complex128)
    if name in ('first','middle','last'):x[{'first':0,'middle':n//2,'last':n-1}[name]]=.5
    elif name=='tone61':x=.2*np.sin(2*np.pi*61*t)
    elif name=='dc':x=np.full(n,.1)
    elif name=='noise':
        rng=np.random.default_rng(20260920);x=rng.uniform(-.1,.1,n)+1j*rng.uniform(-.1,.1,n)
    elif name=='chirp':x=.15*np.exp(2j*np.pi*(31*t+53*t*t))
    elif name!='zero':raise ValueError('unknown signal')
    return np.asarray(x,dtype=np.complex64)

def coords(shape):
    c,frames,windows=shape
    for f in frames:
        r=np.arange(f.window_length);t=r-f.window_length//2;l=f.center+t;good=(l>=0)&(l<c.frames)
        yield l[good],np.mod(t[good],c.fft_size),windows[f.window_offset+r[good]]

def reference(x,shape,coeff=None):
    """Independent complex128 FFT and diagonal inverse, no native calls."""
    c,frames,w=shape;coeffs=[];diagonal=np.zeros(c.frames);synthesis=np.zeros(c.frames,dtype=np.complex128);bound=1.
    for j,(l,t,g) in enumerate(coords(shape)):
        frame=np.zeros(c.fft_size,dtype=np.complex128);frame[t]=x[l].astype(np.complex128)*g
        bound=max(bound,float(np.sum(np.abs(frame))))
        z=np.fft.fft(frame);coeffs.append(z);diagonal[l]+=g*g
        to_synthesize=z if coeff is None else coeff[j*c.fft_size:(j+1)*c.fft_size].astype(np.complex128)
        inv=np.fft.ifft(to_synthesize);synthesis[l]+=inv[t]*g
    if np.any(diagonal<=0):raise ValueError('reference coverage hole')
    return np.concatenate(coeffs),synthesis/diagonal,diagonal,bound

def diagnostics(x,z,y,shape,ref):
    rz,ry,diagonal,bound=ref;peak=float(np.max(np.abs(x)))
    if peak==0:
        if np.any(z!=0) or np.any(y!=0):raise ValueError('zero input does not reconstruct zero')
        return dict(zero=True,peak_relative_error=0.,l2_relative_error=0.,coefficient_error=0.,reference_synthesis_error=0.,energy_error=0.,imaginary_residual=0.)
    if np.max(np.abs(y))==0:raise ValueError('all-zero false reconstruction')
    _,from_coeff,_,_=reference(x,shape,z)
    err=np.abs(y.astype(np.complex128)-x)
    target=float(np.sum(diagonal*np.abs(x.astype(np.complex128))**2))
    energy=float(np.sum(np.abs(z.astype(np.complex128))**2)/shape[0].fft_size)
    result=dict(zero=False,peak_relative_error=float(err.max()/peak),
        l2_relative_error=float(np.linalg.norm(err)/np.linalg.norm(x.astype(np.complex128))),
        coefficient_error=float(np.max(np.abs(z-rz))/bound),
        reference_synthesis_error=float(np.max(np.abs(y-from_coeff))/peak),
        energy_error=abs(energy-target)/target,
        imaginary_residual=float(np.max(np.abs(y.imag))) if np.all(x.imag==0) else None)
    for key,limit in [('peak_relative_error',3e-6),('l2_relative_error',3e-6),('coefficient_error',3e-6),('reference_synthesis_error',3e-6),('energy_error',5e-6)]:
        if not np.isfinite(result[key]) or result[key]>limit:raise ValueError(f'{key} gate failed: {result[key]}')
    return result

def grid():
    return [(rate,n,signal,sched) for rate in RATES for n in (17,1001,rate//8+1) for signal,sched in itertools.product(SIGNALS,SCHEDULES)]

def prepare(library,out):
    out=out.resolve();out.mkdir(parents=True,exist_ok=False);(out/'inputs').mkdir();cases=[]
    for i,(rate,n,sig,sch) in enumerate(grid()):
        m={22050:1024,48000:2048,96000:4096}[rate];x=source(n,rate,sig);centers,windows=schedule(n,m,sch)
        shape=pack(n,m,centers,windows);path=out/'inputs'/f'{i:03d}.npz'
        np.savez_compressed(path,input=x,centers=np.array(centers,dtype=np.int64),lengths=np.array([len(w) for w in windows],dtype=np.int64),windows=np.concatenate(windows))
        cases.append(dict(index=i,rate=rate,n=n,signal=sig,schedule=sch,m=m,path=str(path),sha256=contract.fingerprint(path)))
    files=file_map(Path(__file__).resolve().parents[1]);files.update(binary_map(library))
    plan=dict(schema='nsdgt-foundation-v1',base=BASE,protocol_commit=PROTOCOL,files=files,library=str(library.resolve()),
        cases=cases,repeats=REPEATS,expected_cells=288,expected_pairs=864,
        environment=dict(python=sys.version,numpy=np.__version__),quality_selection=None)
    contract.json_write(out/'plan.json',plan)

def identity(plan):
    if plan['schema']!='nsdgt-foundation-v1' or plan['repeats']!=3:raise ValueError('wrong plan schema')
    actual=[(c['rate'],c['n'],c['signal'],c['schedule']) for c in plan['cases']]
    if actual!=grid() or [c['index'] for c in plan['cases']]!=list(range(288)):raise ValueError('incomplete or duplicate input grid')
    for file,sha in plan['files'].items():
        if contract.fingerprint(Path(file))!=sha:raise ValueError(f'changed source/dependency: {file}')
    for case in plan['cases']:
        if contract.fingerprint(Path(case['path']))!=case['sha256']:raise ValueError('changed input')

def load(case):
    with np.load(case['path'],allow_pickle=False) as data:
        x=data['input'];centers=data['centers'].tolist();lengths=data['lengths'].tolist();raw=data['windows'];windows=[];pos=0
        for length in lengths:windows.append(raw[pos:pos+length]);pos+=length
        if pos!=len(raw) or len(x)!=case['n']:raise ValueError('stored shape mismatch')
    return x,pack(case['n'],case['m'],centers,windows)

def assess(rows):
    keys=[(r['index'],r['repeat']) for r in rows]
    expected=list(itertools.product(range(288),range(3)))
    if sorted(keys)!=expected:raise ValueError('missing/duplicate/extra result rows')
    if any(r['status']!='complete' for r in rows):return dict(passed=False,quality_selection=None,errors='numerical/execution failure',maxima=None)
    gates={'peak_relative_error':3e-6,'l2_relative_error':3e-6,'coefficient_error':3e-6,'reference_synthesis_error':3e-6,'energy_error':5e-6}
    for row in rows:
        if any(not isinstance(row.get(k),str) or re.fullmatch('[0-9a-f]{64}',row[k]) is None for k in ('coeff_sha256','output_sha256')):
            return dict(passed=False,quality_selection=None,errors='invalid evidence hash',maxima=None)
        met=row.get('metrics',{})
        if any(type(met.get(k)) not in (int,float) or not np.isfinite(met[k]) or not 0<=met[k]<=limit for k,limit in gates.items()):
            return dict(passed=False,quality_selection=None,errors='invalid or failing numeric evidence',maxima=None)
    groups={i:[r for r in rows if r['index']==i] for i in range(288)}
    same=all(len({(r['coeff_sha256'],r['output_sha256']) for r in group})==1 for group in groups.values())
    maxima={k:max(r['metrics'][k] for r in rows) for k in ('peak_relative_error','l2_relative_error','coefficient_error','reference_synthesis_error','energy_error')}
    return dict(passed=same,repeats_identical=same,complete_pairs=len(rows),maxima=maxima,quality_selection=None,
        decision='numerical foundation only; no pitch/time quality qualification')

def _run(path,sha,out):
    if contract.fingerprint(path)!=sha:raise ValueError('plan hash mismatch')
    plan=json.loads(path.read_text());identity(plan);out=out.resolve();objects=out/'objects';objects.mkdir()
    native=Native(plan['library'],plan['files'][plan['library']]);rows=[]
    for case in plan['cases']:
        x,shape=load(case);ref=reference(x,shape)
        for repeat in range(3):
            row=dict(index=case['index'],repeat=repeat,status='failed',errors=[])
            try:
                z,info,ta=native.call(True,x,shape);y,_,ts=native.call(False,z,shape)
                measures=diagnostics(x,z,y,shape,ref);outsha=phash(y);obj=objects/(outsha+'.c64')
                if not obj.exists():obj.write_bytes(np.asarray(y,dtype='<c8').tobytes())
                row.update(status='complete',coeff_sha256=phash(z),output_sha256=outsha,output=str(obj.relative_to(out)),
                           metrics=measures,info=info,analysis_seconds=ta,synthesis_seconds=ts)
            except (ValueError,RuntimeError,OSError) as e:row['errors']=[str(e)]
            rows.append(row)
            with (out/'rows.jsonl').open('a') as f:f.write(json.dumps(row,allow_nan=False)+'\n')
        if len(rows)%96==0:print(f'{len(rows)}/864 pairs',flush=True)
    identity(plan);summary=assess(rows);summary.update(plan_sha256=sha,rows=rows,peak_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    contract.json_write(out/'summary.json',summary);return summary

def run(path,sha,out):
    out=out.resolve();out.mkdir(parents=True,exist_ok=False)
    try:
        return _run(path,sha,out)
    except (ValueError,RuntimeError,OSError,KeyError,TypeError) as exc:
        report=dict(passed=False,errors=[str(exc)],quality_selection=None,decision='blocked')
        contract.json_write(out/'summary.json',report)
        return report

def main():
    p=argparse.ArgumentParser(description=__doc__);s=p.add_subparsers(dest='action',required=True)
    a=s.add_parser('prepare');a.add_argument('--library',type=Path,required=True);a.add_argument('--output',type=Path,required=True)
    a=s.add_parser('run');a.add_argument('--plan',type=Path,required=True);a.add_argument('--sha256',required=True);a.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    if a.action=='prepare':prepare(a.library,a.output);print(contract.fingerprint(a.output/'plan.json'));return 0
    try:
        return 0 if run(a.plan,a.sha256,a.output)['passed'] else 2
    except OSError as exc:
        print(str(exc),file=sys.stderr);return 2
if __name__=='__main__':raise SystemExit(main())
