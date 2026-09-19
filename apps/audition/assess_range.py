#!/usr/bin/env python3
"""Supplementary full-control-range tone audit, not natural-music qualification.

6 modes x 2 rates x speeds(0,.001,.25,1,4) x pitch(-24,0,+24) = 180 outputs.
Uses an analytic223Hz source and the existing5-cent diagnostic; no tuning or
latency/gain fitting. The steady score is after0.6s of a1s output, so it does not
measure transition quality. Hold/ramp/boundary tests remain separate.
"""
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np
import native
import assess_freeze


def run(directory):
    directory=Path(directory)
    directory.mkdir(parents=True,exist_ok=False)
    dependencies=[Path(__file__),Path(native.__file__),Path(assess_freeze.__file__),native.library_path()]
    hashes={str(p.resolve()):hashlib.sha256(p.read_bytes()).hexdigest() for p in dependencies}
    rows=[]
    for rate in (48000,96000):
        t=np.arange(rate*5)/rate;x=.1*np.cos(2*np.pi*223*t)
        source=np.c_[x,-.375*x].astype('float32')
        for mode in range(6):
            for speed in (0.,.001,.25,1.,4.):
                for pitch in (-24.,0.,24.):
                    with native.Transport(source,rate,mode) as h:
                        h.seek(rate/2);h.set(speed,pitch)
                        y=assess_freeze.render(h,rate);info=h.info()
                        measured=assess_freeze.pitch_hz(y[round(.6*rate):,0],rate)
                        expected=223*2**(pitch/12)
                        row=dict(rate=rate,mode=mode,speed=speed,pitch_semitones=pitch,
                                 cents_error=float(1200*np.log2(measured/expected)),
                                 finite=bool(np.isfinite(y).all()),
                                 position_error=info['source_position']-(rate/2+speed*rate),
                                 peak=float(abs(y).max()),
                                 output_sha256=hashlib.sha256(y.tobytes()).hexdigest())
                        row['passed']=row['finite'] and abs(row['cents_error'])<5 and abs(row['position_error'])<1e-8
                        rows.append(row)
    for path,h in hashes.items():
        if hashlib.sha256(Path(path).read_bytes()).hexdigest()!=h:raise ValueError('Dependency changed during audit')
    summary=dict(rows=len(rows),passes=sum(r['passed'] for r in rows),
                 worst_abs_cents=max(abs(r['cents_error']) for r in rows),
                 worst_position_error=max(abs(r['position_error']) for r in rows),dependencies=hashes,
                 caveat='Steady generated tone; not all possible source/rate/content/transition combinations.')
    (directory/'rows.json').write_text(json.dumps(rows,indent=2,allow_nan=False)+'\n')
    (directory/'summary.json').write_text(json.dumps(summary,indent=2,allow_nan=False)+'\n')
    return summary

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True)
    result=run(p.parse_args().output);print(json.dumps(result,indent=2))
    raise SystemExit(0 if result['passes']==result['rows']==180 else 1)
