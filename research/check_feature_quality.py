#!/usr/bin/env python3
"""Retain existing tonal gates for the opt-in centered/rate-scaled configuration."""
import argparse,json,math,tempfile
from pathlib import Path
import numpy as np
import soundfile as sf
from scipy.signal import hilbert
import eval_research_features as e
from check_fuzzy_quality import analyze

def run(build:Path,output:Path)->dict:
    if output.exists():raise ValueError('output exists')
    rows=[]
    with tempfile.TemporaryDirectory(prefix='feature-tonal-') as tmp:
        source,dest=Path(tmp)/'input.wav',Path(tmp)/'output.wav'
        for rate in (48000,96000):
            for band,freqs,shifts,duration in [('low',(55,80,120,220,440),(-12,7,12),2),
                                             ('high',(5500,6500,7500,8500,9500,10500),(7,12),4)]:
                for freq in freqs:
                    t=np.arange(rate*duration)/rate
                    x=(.2*np.sin(2*np.pi*freq*t)).astype('float32')[:,None]
                    sf.write(source,x,rate,subtype='FLOAT')
                    for st in shifts:
                        ratio=float(np.float32(2**(st/12)))
                        for profile in e.PROFILES:
                            cmd=e.command(build,source,dest,profile,'harmonic' if band=='low' else 'off',ratio,rate,'candidate')
                            y,_=e.render(cmd,dest,x.shape,rate)
                            row=dict(rate=rate,band=band,freq=freq,shift=st,profile=profile,peak=float(np.max(np.abs(y))))
                            if band=='low':
                                cents,spur=analyze(y,rate,freq*ratio)
                                row.update(cents=cents,spur_db=spur,passed=abs(cents)<=3 and spur>=22 and row['peak']<=1)
                            else:
                                env=np.abs(hilbert(y[rate//2:-rate//2,0].astype(float)))
                                p5,p95=np.quantile(env,[.05,.95]);ripple=float(20*math.log10(max(p95,1e-30)/max(p5,1e-30)))
                                row.update(ripple95_db=ripple,passed=ripple<=.25 and row['peak']<=.25)
                            rows.append(row)
            print(rate,'completed',flush=True)
    result=dict(schema='boiled-egg.feature-tonal.v1',rows=rows,failed=[r for r in rows if not r['passed']],
                listening_status='not_listened',threshold_policy='unchanged3c22dB0.25dB',
                executables={p.name:e.e.fingerprint(p) for p in (build/'boiled_egg_pv_rt_cli',build/'boiled_egg_multires_rt_cli')})
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    return result
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--build',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();r=run(a.build,a.output);print(f'{len(r["rows"])} tones; {len(r["failed"])} failures');raise SystemExit(bool(r['failed']))
