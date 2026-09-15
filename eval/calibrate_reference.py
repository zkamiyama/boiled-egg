#!/usr/bin/env python3
"""Roadmap B prerequisite: direct R2/R3 offline calibration, not vendor quality.
Same frozen 2s 440-Hz grid as calibrate_external; both engines always reported.
"""
import argparse,csv,json
from pathlib import Path
import numpy as np
import soundfile as sf
import comparison_contract as c
from calibrate_external import OPERATIONS,pitch_cents
from reference_rubberband import Reference


def run(args):
    if args.output.exists():raise ValueError('new output required')
    ref=Reference(args.library);args.output.mkdir(parents=True)
    plan=dict(library=str(ref.path),library_sha256=ref.sha256,engines=[2,3],rates=[48000,96000],channels=[1,2],
              operations=OPERATIONS,pitch_threshold_cents=5.,duration_tolerance_frames=1,
              formant='off',block=4096,adapter_sha256=c.fingerprint(Path(__file__).with_name('reference_rubberband.py')),
              script_sha256=c.fingerprint(Path(__file__)),metric_sha256=c.fingerprint(Path(__file__).with_name('calibrate_external.py')),
              contract_sha256=c.fingerprint(Path(c.__file__)))
    c.json_write(args.output/'plan.json',plan);rows=[]
    for rate in plan['rates']:
        for channels in plan['channels']:
            tone=.125*np.sin(2*np.pi*440*np.arange(rate*2)/rate)
            x=tone[:,None] if channels==1 else np.c_[tone,-.5*tone]
            source=args.output/f'source-{rate}-{channels}.wav';sf.write(source,x,rate,subtype='FLOAT')
            metadata=c.inspect_audio(source);x,_=sf.read(source,always_2d=True,dtype='float32')
            for index,(duration,shift) in enumerate(OPERATIONS):
                request=c.Request.from_semitones(duration,shift)
                for engine in (2,3):
                    case=args.output/f'{rate}-{channels}-{index:02}-R{engine}';case.mkdir()
                    row=dict(engine=engine,rate=rate,channels=channels,duration_ratio=duration,pitch_semitones=shift,
                             status='failed',cents_error=None,duration_error_frames=None)
                    receipt=dict(request=vars(request),source=metadata,errors=[])
                    try:
                        y,details=ref.render(x,rate,request,engine)
                        sf.write(case/'output.wav',y,rate,subtype='FLOAT')
                        actual=c.inspect_audio(case/'output.wav');receipt.update(details=details,output=actual)
                        receipt['errors']=c.output_checks(metadata,actual,request)
                        row['duration_error_frames']=details['duration_error_frames']
                        row['cents_error']=pitch_cents(y[:,0],rate,440*request.pitch_ratio)
                        if abs(row['cents_error'])>5:receipt['errors'].append('dominant frequency exceeds 5-cent gate')
                        row['status']='passed' if not receipt['errors'] else 'failed'
                    except (ValueError,RuntimeError,OSError) as exc:receipt['errors'].append(str(exc))
                    if c.fingerprint(source)!=metadata['sha256']:raise RuntimeError('source mutation')
                    receipt['status']=row['status'];c.json_write(case/'receipt.json',receipt)
                    row['case']=case.name;row['receipt_sha256']=c.fingerprint(case/'receipt.json');rows.append(row)
    if len(rows)!=104 or len({(r['engine'],r['rate'],r['channels'],r['duration_ratio'],r['pitch_semitones']) for r in rows})!=104:
        raise RuntimeError('incomplete grid')
    with (args.output/'measurements.csv').open('x',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    report=dict(schema='boiled-egg.direct-reference-calibration.v1',rows=len(rows),
        results=[dict(engine=e,passed=sum(r['status']=='passed' for r in rows if r['engine']==e),total=52,
                      max_abs_cents=max(abs(r['cents_error']) for r in rows if r['engine']==e and r['cents_error'] is not None)) for e in (2,3)],
        measurements_sha256=c.fingerprint(args.output/'measurements.csv'),plan_sha256=c.fingerprint(args.output/'plan.json'),
        library_unchanged=c.fingerprint(ref.path)==ref.sha256,passed=all(r['status']=='passed' for r in rows),
        listening_status='not_listened',scope='Offline direct-library operation calibration only; not native zplane or formant quality.')
    c.json_write(args.output/'summary.json',report);return report

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--library',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True);result=run(p.parse_args());print(json.dumps(result,indent=2))
    raise SystemExit(not result['passed'])
