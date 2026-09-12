#!/usr/bin/env python3
"""Pure-tone regression, not listening quality. Reuse existing 3c/22dB/0.25dB gates."""
from __future__ import annotations
import argparse,json,math,subprocess
from pathlib import Path
import numpy as np
import soundfile as sf
from scipy.signal import hilbert
from eval_fuzzy_corpus import command
from eval_multires_corpus import checked_audio,fingerprint


def analyze(x: np.ndarray, rate: int, target: float) -> tuple[float,float]:
    x=x[rate//2:-rate//2,0].astype('float64')
    size=1<<int(np.ceil(np.log2(len(x)*8)))
    p=np.abs(np.fft.rfft(x*np.hanning(len(x)),size))**2
    f=np.fft.rfftfreq(size,1/rate); mask=(f>20)&(f<rate/2-100)
    hz=f[np.flatnonzero(mask)[np.argmax(p[mask])]]
    wanted=np.sum(p[(f>target-3)&(f<target+3)])
    return float(1200*np.log2(hz/target)),float(10*np.log10((wanted+1e-30)/max(np.sum(p[mask])-wanted,1e-30)))


def run(cli: Path, output: Path, rates: list[int], scale_window: bool = False) -> dict:
    output.mkdir(parents=True,exist_ok=False)
    rows=[]
    for rate in rates:
        for band,freqs,shifts,duration in [('low',(55,80,120,220,440),(-12,7,12),2),
                                          ('high',(5500,6500,7500,8500,9500,10500),(7,12),4)]:
            for freq in freqs:
                t=np.arange(rate*duration)/rate
                source=output/'input.wav';sf.write(source,(.2*np.sin(2*np.pi*freq*t)).astype('float32'),rate,subtype='FLOAT')
                for st in shifts:
                    ratio=float(np.float32(2**(st/12)));target=freq*ratio
                    for profile in ('transient','fuzzy-noise','fuzzy'):
                        dest=output/'render.wav'
                        cmd=command(cli,cli,source,dest,profile,'harmonic' if band=='low' else 'off',ratio,64)
                        fft=2048 if scale_window and rate==96000 else 1024
                        cmd[cmd.index('--fft')+1]=str(fft);cmd[cmd.index('--hop')+1]=str(fft//4)
                        subprocess.run(cmd,
                                       check=True,capture_output=True,text=True,timeout=120)
                        x,sr=checked_audio(dest)
                        if sr!=rate or x.shape!=(len(t),1):raise ValueError('metadata mismatch')
                        row=dict(rate=rate,fft=fft,hop=fft//4,band=band,freq=freq,shift=st,profile=profile,peak=float(np.max(np.abs(x))))
                        if band=='low':
                            cents,spur=analyze(x,rate,target)
                            row.update(cents=cents,spur_db=spur,passed=abs(cents)<=3 and spur>=22 and row['peak']<=1)
                        else:
                            env=np.abs(hilbert(x[rate//2:-rate//2,0].astype('float64')))
                            p5,p95=np.quantile(env,[.05,.95]);ripple=float(20*math.log10(max(p95,1e-30)/max(p5,1e-30)))
                            row.update(ripple95_db=ripple,passed=ripple<=.25 and row['peak']<=.25)
                        rows.append(row)
    result=dict(schema='boiled-egg.fuzzy-tonal-quality.v1',cli_sha256=fingerprint(cli),scale_window=scale_window,rows=rows,
                failed=[r for r in rows if not r['passed']],listening_status='not_listened')
    (output/'summary.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    (output/'input.wav').unlink();(output/'render.wav').unlink()
    return result

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--cli',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True);p.add_argument('--rates',type=int,nargs='+',choices=(48000,96000),default=[48000])
    p.add_argument('--scale-window',action='store_true',help='Explicitly use 2048/512 at 96 kHz, not a default change')
    a=p.parse_args();r=run(a.cli.resolve(strict=True),a.output,a.rates,a.scale_window)
    print(f'{len(r["rows"])} tones; {len(r["failed"])} failures',flush=True)
    raise SystemExit(bool(r['failed']))
