#!/usr/bin/env python3
"""Independent analytic-tone validation of the opt-in continuous pitch timeline.

This is not a perceptual score or native-zplane comparison. Delays are the API's
reported fixed delay: no fitted alignment/DTW/normalization. Steady plateau
frequency is estimated independently by zero-padded Hann interpolation. The
transition trajectory is a diagnostic (STFT response is not sample-instant).
"""
from __future__ import annotations
import argparse, ctypes as c, csv, hashlib, json, math, platform
import concurrent.futures as cf
from pathlib import Path
import numpy as np
from scipy import signal

class Config(c.Structure):
    _fields_=[(name,c.c_uint32) for name in ('size','version','rate','channels','block','window','search','fifo')]
class Backend(c.Structure):
    _fields_=[(name,c.c_uint32) for name in ('size','version','backend','quality','policy','io','flags')]+[(name,c.c_float) for name in ('time','pitch','formant')]+[('reserved',c.c_uint32*2)]
class Runtime(c.Structure):
    _fields_=[(name,c.c_uint32) for name in ('size','rate','channels','block','latency','tail','quantum','capabilities')]
class Event(c.Structure):
    _fields_=[('size',c.c_uint32),('offset',c.c_uint32),('parameter',c.c_uint32),('value',c.c_float)]
FloatPtr=c.POINTER(c.c_float)


def sha(path:Path)->str:return hashlib.sha256(path.read_bytes()).hexdigest()

def library(path):
    lib=c.CDLL(str(path.resolve(strict=True)))
    lib.boiledegg_default_config.argtypes=[c.c_uint32,c.c_uint32];lib.boiledegg_default_config.restype=Config
    lib.boiledegg_default_backend_config.restype=Backend
    lib.boiledegg_create_backend.argtypes=[c.POINTER(Config),c.POINTER(Backend),c.POINTER(c.c_int)];lib.boiledegg_create_backend.restype=c.c_void_p
    lib.boiledegg_destroy.argtypes=[c.c_void_p]
    lib.boiledegg_get_runtime_info.argtypes=[c.c_void_p,c.POINTER(Runtime)]
    lib.boiledegg_process_realtime.argtypes=[c.c_void_p,c.POINTER(FloatPtr),c.POINTER(FloatPtr),c.c_uint32,c.POINTER(Event),c.c_uint32]
    return lib

SHIFTS=(-12,-7,-3,3,7,12,0)
TIMES=(.65,1.30,1.95,2.60,3.25,3.90,4.55)


def render(lib,rate,quality,policy,freq,block):
    config=lib.boiledegg_default_config(rate,2);config.block=257
    backend=lib.boiledegg_default_backend_config();backend.backend=1;backend.quality=quality;backend.policy=policy;backend.io=2;backend.flags=3
    backend.time=backend.pitch=backend.formant=1.
    status=c.c_int();h=lib.boiledegg_create_backend(c.byref(config),c.byref(backend),c.byref(status))
    if not h or status.value:raise ValueError(f'create: {status.value}')
    try:
        rt=Runtime();rt.size=c.sizeof(rt)
        if lib.boiledegg_get_runtime_info(h,c.byref(rt)):raise ValueError('runtime info')
        count=round(rate*5.2);t=np.arange(count)/rate
        source=np.asarray(.2*np.sin(2*np.pi*freq*t),np.float32)
        x=np.zeros((2,count+rt.latency),np.float32);x[0,:count]=source;x[1,:count]=-.5*source
        y=np.zeros_like(x)
        events=[(round(time*rate),float(np.float32(2**(st/12)))) for time,st in zip(TIMES,SHIFTS)]
        for start in range(0,x.shape[1],block):
            size=min(block,x.shape[1]-start)
            inp=(FloatPtr*2)(*[x[ch,start:].ctypes.data_as(FloatPtr) for ch in range(2)])
            out=(FloatPtr*2)(*[y[ch,start:].ctypes.data_as(FloatPtr) for ch in range(2)])
            ev=[Event(c.sizeof(Event),at-start,2,value) for at,value in events if start<=at<start+size]
            array=(Event*len(ev))(*ev)
            if lib.boiledegg_process_realtime(h,inp,out,size,array,len(ev)):raise ValueError('process failure')
        if not np.isfinite(y).all() or np.any(y[:,:rt.latency]):raise ValueError('nonfinite output or invalid delay prefix')
        audio=y[:,rt.latency:]
        return audio,rt.latency,hashlib.sha256(y.tobytes()).hexdigest()
    finally:lib.boiledegg_destroy(h)


def frequency(x,rate,expected):
    x=np.asarray(x,float)
    if len(x)<32 or not np.isfinite(x).all() or np.mean(x*x)<1e-16:raise ValueError('invalid tone')
    nfft=1<<int(np.ceil(np.log2(len(x)*16)))
    power=np.abs(np.fft.rfft(x*signal.windows.hann(len(x),sym=False),nfft))**2
    f=np.fft.rfftfreq(nfft,1/rate)
    mask=(f>.7*expected)&(f<1.3*expected)
    candidates=np.flatnonzero(mask)
    if not len(candidates):raise ValueError('empty frequency interval')
    k=int(candidates[np.argmax(power[mask])])
    q=np.log(np.maximum(power[k-1:k+2],1e-300));delta=.5*(q[0]-q[2])/(q[0]-2*q[1]+q[2])
    return (k+delta)*rate/nfft


def measure(audio,rate,freq):
    x=audio[0].astype(float);rows=[]
    err=audio[1].astype(float)+.5*x
    stereo=float(np.sqrt(np.sum(err*err)/(np.sum(x*x)+1e-30)))
    for time,shift in zip(TIMES,SHIFTS):
        expected=freq*float(np.float32(2**(shift/12)))
        segment=x[round((time+.23)*rate):round((time+.57)*rate)]
        actual=frequency(segment,rate,expected)
        cents=1200*math.log2(actual/expected)
        envelope=np.abs(signal.hilbert(segment))[round(.03*rate):-round(.03*rate)]
        ripple=float(20*np.log10(np.quantile(envelope,.975)/np.quantile(envelope,.025)))
        rows.append(dict(shift=shift,target_hz=expected,measured_hz=float(actual),error_cents=cents,
                         plateau_ripple_db=ripple,stereo_relative_error=stereo,
                         peak=float(np.max(np.abs(audio)))))
    # Diagnostic only: compare 20-ms median Hilbert frequency to the independent
    # input-clock ramp over whole signal, excluding first/last 200 ms.
    pitch=np.ones(len(x));current=1.;target=1.;step=0.;remaining=0;index=0
    events=[(round(t*rate),float(np.float32(2**(st/12)))) for t,st in zip(TIMES,SHIFTS)]
    ramp=rate//100
    for i in range(len(x)):
        if index<len(events) and i==events[index][0]:
            target=events[index][1];remaining=ramp;step=(target-current)/ramp;index+=1
        if remaining:current=target if remaining==1 else current+step;remaining-=1
        pitch[i]=current
    phase=np.unwrap(np.angle(signal.hilbert(x)))
    derivative=np.diff(phase)*rate/(2*np.pi)
    # No smoothing across arbitrary block boundaries; summarize fixed 20ms bins.
    shape=[];hop=round(.02*rate)
    for start in range(round(.2*rate),len(derivative)-round(.2*rate),hop):
        actual=np.median(derivative[start:start+hop]);target=freq*np.median(pitch[start:start+hop])
        if actual>0:shape.append(abs(1200*np.log2(actual/target)))
    return rows,dict(trajectory_median_abs_cents=float(np.median(shape)),trajectory_p95_abs_cents=float(np.quantile(shape,.95)))


def one_case(job):
    path,rate,quality,policy,f0=job
    lib=library(path)
    a,delay,hash_a=render(lib,rate,quality,policy,f0,32)
    b,other,hash_b=render(lib,rate,quality,policy,f0,257)
    if delay!=other or hash_a!=hash_b or not np.array_equal(a,b):raise ValueError('block partition changes audio')
    measured,trajectory=measure(a,rate,f0)
    return ([dict(rate=rate,quality=quality,policy=policy,input_hz=f0,delay_frames=delay,output_sha256=hash_a,**r) for r in measured],
            dict(rate=rate,quality=quality,policy=policy,input_hz=f0,**trajectory))


def run(args):
    if args.output.exists() or not 1<=args.workers<=4:raise ValueError('new output and 1..4 workers required')
    digest=sha(args.library);rows=[];trajectories=[];pairs=0
    # Predeclared settled-tone guard:5cents and stereo1e-5. High-tone plateau
    # ripple is reported, not retrofitted to pass a transition integration test.
    jobs=[(args.library,rate,q,p,f) for rate in (48000,96000) for q in (0,1) for p in (0,1,2) for f in (55.,220.,6200.)]
    with cf.ProcessPoolExecutor(args.workers) as pool:
        for measured,trajectory in pool.map(one_case,jobs):
            rows.extend(measured);trajectories.append(trajectory);pairs+=1
            print(f'{pairs}/36 paired trajectories',flush=True)
    if sha(args.library)!=digest:raise ValueError('library changed during measurement')
    if len(rows)!=252:raise ValueError('incomplete measurement grid')
    failed=[r for r in rows if abs(r['error_cents'])>5 or r['stereo_relative_error']>1e-5]
    args.output.mkdir(parents=True)
    with (args.output/'plateaus.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    result=dict(schema='boiled-egg.dynamic-pitch-tone.v1',library_sha256=digest,script_sha256=sha(Path(__file__)),
                paired_renders=pairs,actual_renders=2*pairs,plateaus=len(rows),failures=failed,
                max_abs_cents=max(abs(r['error_cents']) for r in rows),max_stereo_error=max(r['stereo_relative_error'] for r in rows),
                trajectories=trajectories,passed=not failed,
                limits=dict(settled_pitch_cents=5.,relative_link_error=1e-5),
                notes='No fitted alignment: API delay only. 10ms input-ratio ramp; audible spectral response has window spread. '
                'Hann spectral estimator and Hilbert trajectory are analytic diagnostics, not perceptual/native-vendor scores. '
                'Plateau ripple is measured but no new pass threshold is fitted.',
                python=platform.python_version(),numpy=np.__version__,plateaus_sha256=sha(args.output/'plateaus.csv'))
    (args.output/'summary.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    return result

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--library',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--workers',type=int,default=3)
    result=run(p.parse_args());print('max cents',result['max_abs_cents'],'failures',len(result['failures']));raise SystemExit(not result['passed'])
