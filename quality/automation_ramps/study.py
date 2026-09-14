#!/usr/bin/env python3
"""Independent explicit-ramp checks, same-input partition replay, no MOS claim.

W=sum(T), V=sum(T*p) use closed-form per-event curves and long-double sums,
not the SDK recurrence. EOS length is round(W); control targets count input
samples actually accepted. Natural sources remain unmodified and unredistributed.
"""
from __future__ import annotations
import argparse, ctypes as c, csv, hashlib, json, math, sys
import concurrent.futures as cf
from pathlib import Path
import numpy as np
import soundfile as sf
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'dynamic_pitch'))
import evaluate as base

class Ramp(c.Structure):
    _fields_=[('size',c.c_uint32),('offset',c.c_uint32),('parameter',c.c_uint32),
              ('duration',c.c_uint32),('curve',c.c_uint32),('value',c.c_float),('reserved',c.c_uint32*2)]
class Info(c.Structure):
    _fields_=[('size',c.c_uint32),('version',c.c_uint32),('input_frames',c.c_uint64),
              ('output_position',c.c_double),('intermediate_position',c.c_double),
              ('pitch',c.c_double),('time',c.c_double),('pitch_target',c.c_float),('time_target',c.c_float),
              ('pitch_remaining',c.c_uint32),('time_remaining',c.c_uint32)]

def load(path):
    lib=base.library(path)
    lib.boiledegg_process_realtime_ramps.argtypes=[c.c_void_p,c.POINTER(base.FloatPtr),c.POINTER(base.FloatPtr),c.c_uint32,c.POINTER(Ramp),c.c_uint32]
    lib.boiledegg_push_ramps.argtypes=[c.c_void_p,c.POINTER(base.FloatPtr),c.c_uint32,c.POINTER(Ramp),c.c_uint32,c.POINTER(c.c_uint32)]
    lib.boiledegg_pull.argtypes=[c.c_void_p,c.POINTER(base.FloatPtr),c.c_uint32,c.POINTER(c.c_uint32)]
    lib.boiledegg_available.argtypes=[c.c_void_p];lib.boiledegg_available.restype=c.c_uint32
    lib.boiledegg_flush.argtypes=[c.c_void_p]
    lib.boiledegg_get_automation_info.argtypes=[c.c_void_p,c.POINTER(Info)]
    return lib

def curve_values(length,events,parameter):
    """Independent interval formula; a later command replaces the pending one."""
    result=np.empty(length,dtype=np.longdouble);current=np.longdouble(1);target=current
    origin=current;elapsed=0;duration=0;shape=0;pos=0
    selected=[e for e in events if e[1]==parameter]
    for event in [*selected,(length,parameter,1.,0,0)]:
        at,param,v,n,kind=event
        if not pos<=at<=length:raise ValueError('ordered in-range events required')
        count=at-pos
        if count:
            if duration:
                fraction=np.minimum(1,(elapsed+np.arange(1,count+1,dtype=np.longdouble))/duration)
                value=origin*np.exp(np.log(target/origin)*fraction) if shape else origin+(target-origin)*fraction
                result[pos:at]=value;current=value[-1];elapsed+=count
            else:result[pos:at]=target;current=target
        origin=current;target=np.longdouble(np.float32(v));duration=n;elapsed=0;shape=kind
        if not duration:current=target
        pos=at
    return result

def event_plan(length,rate,kind,shape,analytic):
    times=base.TIMES if analytic else tuple((i+1)/9*length/rate for i in range(7))
    pitches=[float(np.float32(2**(s/12))) for s in base.SHIFTS] if kind=='pitch' else [.5,.75,1.25,1.,.667,1.2,.8]
    times_ratio=[.5,1.5,.75,1.25,.6,1.5,1.]
    events=[]
    for i,(seconds,pitch) in enumerate(zip(times,pitches)):
        at=round(seconds*rate);duration=min(round(.15*rate), max(1,length//30))
        if i==2:duration=1
        if i==5:duration=0
        events.append((at,2,pitch,duration,shape))
        if kind=='time':events.append((at,1,times_ratio[i],duration+1 if duration else 0,shape))
    return sorted(events,key=lambda e:e[0])

def render(lib,x,rate,quality,policy,kind,shape,block,analytic=False):
    x=np.ascontiguousarray(x.T,dtype=np.float32);length=x.shape[1]
    config=lib.boiledegg_default_config(rate,x.shape[0]);config.block=257
    backend=lib.boiledegg_default_backend_config();backend.backend=1;backend.quality=quality;backend.policy=policy
    backend.io=2 if kind=='pitch' else 1;backend.flags=3 if kind=='pitch' else 7
    status=c.c_int();h=lib.boiledegg_create_backend(c.byref(config),c.byref(backend),c.byref(status))
    if not h or status.value:raise ValueError(f'create status {status.value}')
    events=event_plan(length,rate,kind,shape,analytic);pitch=curve_values(length,events,2);time=curve_values(length,events,1)
    expected_w=float(np.sum(time,dtype=np.longdouble));expected_v=float(np.sum(time*pitch,dtype=np.longdouble))
    try:
        rt=base.Runtime();rt.size=c.sizeof(rt)
        if lib.boiledegg_get_runtime_info(h,c.byref(rt)):raise ValueError('runtime info')
        delay=rt.latency if kind=='pitch' else 0
        src=np.pad(x,((0,0),(0,delay)));out=np.empty((x.shape[0],8192),np.float32);pieces=[]
        op=(base.FloatPtr*x.shape[0])(*[ch.ctypes.data_as(base.FloatPtr) for ch in out])
        def drain():
            while lib.boiledegg_available(h):
                n=c.c_uint32()
                if lib.boiledegg_pull(h,op,8192,c.byref(n)) or n.value==0:raise ValueError('pull progress')
                pieces.append(out[:,:n.value].copy())
        def info():
            s=Info();s.size=c.sizeof(s)
            if lib.boiledegg_get_automation_info(h,c.byref(s)):raise ValueError('automation info')
            return s
        pos=0;snapshot=None;calls=0
        while pos<src.shape[1]:
            n=min(block,src.shape[1]-pos)
            if pos<length:n=min(n,length-pos)
            ip=(base.FloatPtr*x.shape[0])(*[ch[pos:].ctypes.data_as(base.FloatPtr) for ch in src])
            ev=[Ramp(c.sizeof(Ramp),at-pos,p,d,sh,v,(0,0)) for at,p,v,d,sh in events if pos<=at<pos+n]
            array=(Ramp*len(ev))(*ev)
            if kind=='pitch':
                if lib.boiledegg_process_realtime_ramps(h,ip,op,n,array,len(ev)):raise ValueError('realtime ramps')
                used=n;pieces.append(out[:,:n].copy())
            else:
                accepted=c.c_uint32();s=lib.boiledegg_push_ramps(h,ip,n,array,len(ev),c.byref(accepted))
                if s not in (0,3):raise ValueError(f'push status {s}')
                used=accepted.value;drain()
                if used==0:raise ValueError('unexpected stalled drain')
            pos+=used;calls+=1
            if pos==length:snapshot=info()
        if kind=='time':
            before=info()
            if lib.boiledegg_flush(h):raise ValueError('flush')
            drain();after=info()
            if before.input_frames!=after.input_frames or before.time_remaining!=after.time_remaining or before.pitch_remaining!=after.pitch_remaining:raise ValueError('EOS advanced controls')
        y=np.concatenate(pieces,axis=1) if pieces else np.empty((x.shape[0],0),np.float32)
        if not np.isfinite(y).all() or np.any(y[:,:delay]):raise ValueError('nonfinite or delay-prefix error')
        y=y[:,delay:]
        if y.shape[1]!=math.floor(expected_w+.5):raise ValueError('independent output duration mismatch')
        clock_error=max(abs(snapshot.output_position-expected_w),abs(snapshot.intermediate_position-expected_v))
        if clock_error>2e-5:raise ValueError(f'independent map mismatch {clock_error}')
        return y,dict(delay=delay,clock_error=clock_error,frames=y.shape[1],peak=float(np.max(np.abs(y))),
             input_sha256=hashlib.sha256(x.tobytes()).hexdigest(),output_sha256=hashlib.sha256(y.tobytes()).hexdigest()),events,time
    finally:lib.boiledegg_destroy(h)

def case(job):
    path,rate,q,p,kind,shape,item=job;lib=load(path)
    analytic=isinstance(item,float)
    if analytic:
        t=np.arange(round(rate*5.2))/rate;s=(.2*np.sin(2*np.pi*item*t)).astype('float32');x=np.c_[s,-.5*s]
    else:
        x,sr=sf.read(item,dtype='float32',always_2d=True)
        if sr!=rate:raise ValueError('source rate changed')
    a,stats,events,time=render(lib,x,rate,q,p,kind,shape,32,analytic)
    b,other,_,_=render(lib,x,rate,q,p,kind,shape,257,analytic)
    if not np.array_equal(a,b) or stats['delay']!=other['delay']:raise ValueError('partition changes output')
    row=dict(rate=rate,quality=q,policy=p,kind=kind,curve=shape,source=str(item),**stats)
    if analytic:
        W=np.r_[0,np.cumsum(time,dtype=np.longdouble)];errors=[];ripples=[]
        pitch_events=[e for e in events if e[1]==2]
        for at,param,target,dur,curve in pitch_events:
            lo=int(W[min(len(time),at+round(.23*rate))]);hi=int(W[min(len(time),at+round(.57*rate))])
            expected=item*float(np.float32(target));f=base.frequency(a[0,lo:hi],rate,expected)
            errors.append(abs(1200*math.log2(f/expected)))
        stereo=float(np.linalg.norm(a[1].astype(float)+.5*a[0])/max(np.linalg.norm(a[0]),1e-30))
        row.update(plateaus=len(errors),max_cents=max(errors),stereo_error=stereo,passed=max(errors)<5 and stereo<1e-5)
    return row

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--library',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True);parser.add_argument('--refs',type=Path);parser.add_argument('--workers',type=int,default=2)
    args=parser.parse_args()
    if args.output.exists() or not 1<=args.workers<=4:raise ValueError('absent output and 1..4 workers required')
    library_hash=base.sha(args.library);files=sorted(args.refs.glob('*.wav')) if args.refs else None
    jobs=[];source_hashes={}
    for item in (files if files is not None else (55.,220.,6200.)):
        rates=[sf.info(item).samplerate] if files is not None else [48000,96000]
        if files is not None:source_hashes[str(item)]=base.sha(item)
        for rate in rates:
            for q in (0,1):
                for p in (0,1,2):
                    for kind in ('pitch','time'):
                        for shape in (0,1):jobs.append((args.library,rate,q,p,kind,shape,item))
    if not jobs:raise ValueError('empty input grid')
    rows=[]
    with cf.ProcessPoolExecutor(args.workers) as pool:
        for i,r in enumerate(pool.map(case,jobs),1):
            rows.append(r)
            if i%24==0:print(i,'/',len(jobs),flush=True)
    if base.sha(args.library)!=library_hash or any(base.sha(Path(p))!=h for p,h in source_hashes.items()):raise ValueError('inputs changed')
    args.output.mkdir(parents=True)
    with (args.output/'results.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    summary=dict(pairs=len(rows),renders=2*len(rows),passed=all(r.get('passed',True) for r in rows),
                 library_sha256=library_hash,script_sha256=base.sha(Path(__file__)),dependency_sha256=base.sha(Path(base.__file__)),
                 results_sha256=base.sha(args.output/'results.csv'),source_hashes=source_hashes,
                 max_clock_error=max(r['clock_error'] for r in rows),max_cents=max((r.get('max_cents',0) for r in rows)),
                 notes='Independent map/settled-tone checks and same-kernel partition replay. No perceptual/native-vendor claim.')
    (args.output/'summary.json').write_text(json.dumps(summary,indent=2,allow_nan=False)+'\n')
    print(json.dumps(summary));return 0 if summary['passed'] else 1
if __name__=='__main__':raise SystemExit(main())
