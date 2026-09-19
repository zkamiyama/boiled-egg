#!/usr/bin/env python3
"""Frozen-tone calibration, not a musical MOS/quality or hard-RT claim.

Fixed grid:6 native methods x48/96k x223/997Hz x(-7,0,+7)st.
Pitch diagnostic5cents, envelope-ripple1dB and stereo1e-5 gates are fixed here
before rendering. Retain failures. True source position never enters DSP except
as the explicitly chosen capture anchor, and no output lag/gain is fitted.
"""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import time
import numpy as np
from native import Transport,library_path

def pitch_hz(y,rate):
    y=np.asarray(y,dtype=float)
    if len(y)<32 or not np.isfinite(y).all() or np.mean(y*y)<1e-12:raise ValueError('Measurable finite tone required')
    z=np.abs(np.fft.rfft(y*np.hanning(len(y))));k=int(np.argmax(z[1:]))+1
    if k>=len(z)-1:raise ValueError('Interior peak required')
    a,b,c=np.log(np.maximum(z[k-1:k+2],1e-30));den=a-2*b+c
    d=0.5*(a-c)/den if abs(den)>1e-12 else 0.
    return (k+d)*rate/len(y)

def metrics(y,rate,expected):
    middle=y[round(.35*rate):]
    measured=pitch_hz(middle[:,0],rate)
    win=round(.05*rate);hop=round(.025*rate)
    rms=np.array([np.sqrt(np.mean(middle[i:i+win,0]**2)) for i in range(0,len(middle)-win+1,hop)])
    ripple=20*np.log10(np.quantile(rms,.975)/np.quantile(rms,.025))
    stereo=np.linalg.norm(middle[:,1]+.375*middle[:,0])/np.linalg.norm(middle[:,0])
    return dict(expected_hz=expected,measured_hz=float(measured),cents_error=float(1200*np.log2(measured/expected)),
                envelope_95_ripple_db=float(ripple),stereo_residual=float(stereo),rms=float(np.sqrt(np.mean(middle[:,0]**2))),peak=float(abs(y).max()))

def render(h,total,block=257):
    return np.concatenate([h.render(min(block,total-p)) for p in range(0,total,block)])

def run(output):
    if output.exists():raise FileExistsError('New result directory required')
    output.mkdir(parents=True);rows=[];libraries=library_path()
    # Independent calibrations; cannot pass by producing silence or changing gain.
    for f in (223.,997.,1413.2):
        rate=48000;t=np.arange(rate)/rate
        assert abs(1200*np.log2(pitch_hz(.1*np.cos(2*np.pi*f*t),rate)/f))<.1
    try:pitch_hz(np.zeros(48000),48000)
    except ValueError:pass
    else:raise AssertionError('silent false success')
    for rate in (48000,96000):
      for f in (223.,997.):
        t=np.arange(rate*3)/rate;x=.16*np.cos(2*np.pi*f*t);source=np.c_[x,-.375*x].astype('float32')
        for mode in range(6):
          for semitone in (-7,0,7):
            with Transport(source,rate,mode=mode) as h:
                h.seek(rate);h.set(0,semitone);before=h.info();start=time.perf_counter()
                y=render(h,round(1.1*rate));duration=time.perf_counter()-start;after=h.info()
                m=metrics(y,rate,f*2**(semitone/12))
                row=dict(rate=rate,frequency=f,mode=mode,pitch_semitones=semitone,**m,
                         source_position=after['source_position'],output_frames=after['output_frames'],
                         analysis_frames=after['analysis_frames'],memory_bytes=after['owned_bytes'],
                         pcm_sha256=hashlib.sha256(y.tobytes()).hexdigest(),render_seconds=duration)
                row['clock_memory_passed']=after['source_position']==rate and after['output_frames']==len(y) and after['owned_bytes']==before['owned_bytes']
                row['pitch_passed']=abs(m['cents_error'])<5
                row['ripple_passed']=m['envelope_95_ripple_db']<1
                row['stereo_passed']=m['stereo_residual']<1e-5
                rows.append(row)
        print('completed',rate,f,len(rows),flush=True)
    # Long hold uses constant output buffers, no duration-sized native storage.
    holds=[]
    for mode in range(6):
        rate=48000;t=np.arange(rate*2)/rate;x=.1*np.cos(2*np.pi*997*t);source=np.c_[x,-.375*x].astype('float32')
        with Transport(source,rate,mode=mode) as h:
            h.seek(24000);h.set(0,0);owned=h.info()['owned_bytes'];head=render(h,rate)
            for _ in range(9*rate//4000):h.render(4000)
            tail=render(h,rate);s=h.info()
            holds.append(dict(mode=mode,frames=s['output_frames'],position=s['source_position'],
                              memory_stable=owned==s['owned_bytes'],analysis_frames=s['analysis_frames'],
                              initial_hz=pitch_hz(head[rate//2:,0],rate),final_hz=pitch_hz(tail[rate//2:,0],rate)))
    with (output/'freeze_tones.csv').open('w',newline='') as stream:
        w=csv.DictWriter(stream,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    summary=dict(rows=len(rows),pitch_passes=sum(r['pitch_passed'] for r in rows),ripple_passes=sum(r['ripple_passed'] for r in rows),
                 stereo_passes=sum(r['stereo_passed'] for r in rows),clock_memory_passes=sum(r['clock_memory_passed'] for r in rows),
                 worst_abs_cents=max(abs(r['cents_error']) for r in rows),worst_ripple_db=max(r['envelope_95_ripple_db'] for r in rows),
                 worst_stereo=max(r['stereo_residual'] for r in rows),long_holds=holds,
                 library_sha256=hashlib.sha256(libraries.read_bytes()).hexdigest(),assessor_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                 caveat='Generated steady tones; not full music quality, MOS, all prior algorithms or realtime guarantee.')
    (output/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary,indent=2))
    return summary
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);a=p.parse_args();r=run(a.output)
    raise SystemExit(0 if all(r[k]==r['rows'] for k in ('pitch_passes','ripple_passes','stereo_passes','clock_memory_passes')) else 1)
