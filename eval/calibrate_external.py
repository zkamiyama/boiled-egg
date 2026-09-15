#!/usr/bin/env python3
"""Real-executable comparison calibration. Not an audio-quality benchmark.

Frozen primary grid: 2-second 440-Hz mono/anti-phase stereo; 48/96k; five
unpitched duration ratios, six pitch shifts, and two coupled operations.
Duration allowance is one frame; settled pitch tolerance is five cents.
The old tempo-direction and PCM16 mistakes are exercised as negative controls.
"""
from __future__ import annotations
import argparse
import csv
import json
import math
from pathlib import Path
import subprocess

import numpy as np
import scipy
from scipy.fft import next_fast_len
import soundfile as sf

import comparison_contract as c

OPERATIONS = tuple([(t,0) for t in (.5,.8,1.,1.25,2.)] +
                   [(1.,s) for s in (-12,-7,-3,3,7,12)] + [(.8,7),(1.25,-7)])


def pitch_cents(audio: np.ndarray, rate: int, expected: float) -> float:
    # Fixed absolute exclusion, no fitted delay or search around expected pitch.
    y = np.asarray(audio, dtype=float)[round(rate*.25):-round(rate*.25)]
    if len(y) < rate // 4:
        raise ValueError("insufficient settled tone for calibration")
    n = next_fast_len(len(y) * 8)
    spec = np.abs(np.fft.rfft((y-y.mean()) * np.hanning(len(y)), n=n))
    k = int(np.argmax(spec[1:])) + 1
    if k >= len(spec)-1 or spec[k] < 1e-10:
        raise ValueError("no measurable interior tone")
    a,b,d = np.log(np.maximum(spec[k-1:k+2],1e-30))
    offset = .5*(a-d)/(a-2*b+d)
    frequency = (k+offset)*rate/n
    return float(1200 * np.log2(frequency / expected))


def negative_controls(root: Path, ffmpeg: str) -> list[dict]:
    source=root/'sources'/'tone-48000-1.wav'
    metadata=c.inspect_audio(source);rows=[]
    for label,tempo,duration,codec in [('old_direction',1.25,1.25,'pcm_f32le'),
                                      ('old_pcm_default',.8,1.25,None)]:
        case=root/'negative'/label;case.mkdir(parents=True)
        out=case/'output.wav'
        cmd=[ffmpeg,'-nostdin','-n','-hide_banner','-loglevel','error','-i',str(source),
             '-af',f'rubberband=tempo={tempo}:pitch=1']
        if codec:cmd+=['-c:a',codec]
        cmd+=[str(out)]
        with (case/'stderr.log').open('w') as err:
            proc=subprocess.run(cmd,stdout=subprocess.DEVNULL,stderr=err,timeout=60)
        if proc.returncode:raise RuntimeError('negative fixture execution failed')
        actual=c.inspect_audio(out)
        errors=c.output_checks(metadata,actual,c.Request(duration))
        # The wrong direction must be a duration error; PCM-only test a subtype error.
        detected=any('duration mismatch' in e for e in errors) if codec else 'output is not float32 WAV' in errors
        row=dict(control=label,command=cmd,detected=detected,errors=errors,output=actual)
        c.json_write(case/'receipt.json',row);rows.append(row)
    return rows


def run(args) -> dict:
    engines=[c.Engine('ffmpeg_rubberband','ffmpeg_rubberband',args.ffmpeg)]
    if args.cli:engines.insert(0,c.Engine('boiled_egg','boiled_egg',str(args.cli)))
    if args.spectral_cli:
        for quality in ('general','transient'):
            engines.append(c.Engine('pv_'+quality,'spectral',str(args.spectral_cli),quality=quality))
    probes={engine.name:engine.probe() for engine in engines}
    if args.output.exists():raise ValueError('new output required')
    args.output.mkdir(parents=True);(args.output/'sources').mkdir()
    rates=(48000,) if args.quick else (48000,96000)
    channels=(1,) if args.quick else (1,2)
    operations=((.8,0),(1.25,0),(1.,-7),(1.,7)) if args.quick else OPERATIONS
    plan=dict(engines=probes,rates=rates,channels=channels,operations=operations,
              pitch_threshold_cents=5.,duration_tolerance_frames=1,
              script_sha256=c.fingerprint(Path(__file__)),contract_sha256=c.fingerprint(Path(c.__file__)),
              numpy=np.__version__,scipy=scipy.__version__,soundfile=sf.__version__)
    c.json_write(args.output/'plan.json',plan)
    sources={}
    for rate in rates:
        for ch in channels:
            tone=.125*np.sin(2*np.pi*440*np.arange(rate*2)/rate)
            x=tone[:,None] if ch==1 else np.c_[tone,-.5*tone]
            p=args.output/'sources'/f'tone-{rate}-{ch}.wav';sf.write(p,x,rate,subtype='FLOAT')
            sources[(rate,ch)]=p
    rows=[]
    for rate in rates:
        for ch in channels:
            for op,(duration,shift) in enumerate(operations):
                request=c.Request.from_semitones(duration,shift)
                for engine in engines:
                    case=args.output/'cases'/f'{rate}-{ch}-{op:02d}-{engine.name}'
                    receipt=c.render_case(engine,probes[engine.name],sources[(rate,ch)],request,case)
                    row=dict(engine=engine.name,rate=rate,channels=ch,duration_ratio=duration,pitch_semitones=shift,
                             status=receipt['status'],case=str(case.relative_to(args.output)),
                             duration_error_frames=receipt.get('duration_error_frames'),cents_error=None,
                             receipt_sha256=c.fingerprint(case/'receipt.json'))
                    if receipt['status']=='passed':
                        y,_=sf.read(case/'output.wav',dtype='float64',always_2d=True)
                        row['cents_error']=pitch_cents(y[:,0],rate,440*request.pitch_ratio)
                        if abs(row['cents_error'])>5:row['status']='pitch_failed'
                    rows.append(row)
                    print(len(rows),engine.name,rate,ch,duration,shift,row['status'],flush=True)
    expected={(e.name,r,ch,d,s) for e in engines for r in rates for ch in channels for d,s in operations}
    actual={(a['engine'],a['rate'],a['channels'],a['duration_ratio'],a['pitch_semitones']) for a in rows}
    if len(actual)!=len(rows) or actual!=expected:raise ValueError('incomplete/duplicate calibration grid')
    negatives=negative_controls(args.output,probes['ffmpeg_rubberband']['executable'])
    stable=all(c.identity_unchanged(p) for p in probes.values())
    passed=all(row['status']=='passed' for row in rows) and all(n['detected'] for n in negatives) and stable
    with (args.output/'measurements.csv').open('x',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    report=dict(schema='boiled-egg.external-calibration.v1',passed=passed,cases=len(rows),
                passed_cases=sum(row['status']=='passed' for row in rows),negative_controls=negatives,
                max_abs_cents=max((abs(r['cents_error']) for r in rows if r['cents_error'] is not None),default=None),
                plan_sha256=c.fingerprint(args.output/'plan.json'),measurements_sha256=c.fingerprint(args.output/'measurements.csv'),
                stable_engine_identities=stable,alignment_verified=False,listening_status='not_listened',
                scope='Two-second settled-tone operation/format calibration, not formant fidelity, all audio lengths, native-zplane or RT qualification.')
    c.json_write(args.output/'summary.json',report)
    return report

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ffmpeg',default='ffmpeg');parser.add_argument('--cli',type=Path)
    parser.add_argument('--spectral-cli',type=Path);parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--quick',action='store_true')
    result=run(parser.parse_args());print(json.dumps({k:result[k] for k in ('passed','cases','passed_cases','max_abs_cents')}))
    raise SystemExit(not result['passed'])
