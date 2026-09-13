#!/usr/bin/env python3
"""Native-pitch matched-input contract, with no derived-baseline fallback.

Prepare reproducible test inputs and requests. Score only a complete external
receipt with exact input/configuration hashes and uncompensated-edit-free WAVs.
Engine metadata are declared provenance, not cryptographic proof of a vendor.
"""
from __future__ import annotations
import argparse, hashlib, json, tempfile
from pathlib import Path
import numpy as np
import soundfile as sf
import eval_audio_quality as q
import eval_research_features as f
import audio_quality_metrics as metrics

SCHEMA='boiled-egg.native-pitch-request.v1'
RATES=(48000,96000)
SHIFTS=(-12,-7,-3,0,3,7,12)
NAMES=('harmonics','inharmonic','attack','noise0','stereo70','vowel_a')

def digest(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def inside(root,relative):
    p=Path(relative)
    if p.is_absolute() or '..' in p.parts or '\\' in relative:raise ValueError('unsafe relative path')
    full=(root/p).resolve(strict=True)
    if not full.is_relative_to(root.resolve()) or not full.is_file():raise ValueError('escaped root')
    return full

def prepare(output):
    if output.exists():raise ValueError('output exists')
    output.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.native-input-',dir=output.parent) as tmp:
        staging=Path(tmp)/'suite';(staging/'inputs').mkdir(parents=True)
        requests=[]
        for name in NAMES:
            for rate in RATES:
                make=f.attack_fixture if name=='attack' else lambda sr,r:q.fixture(name,sr,r)
                x,_=make(rate,1.);relative=f'inputs/{name}-{rate}.wav'
                sf.write(staging/relative,x,rate,subtype='FLOAT')
                sha=digest(staging/relative)
                for mode in (('off','harmonic') if name.startswith('vowel') else ('off',)):
                    for shift in SHIFTS:
                        requests.append(dict(id=f'N{len(requests)+1:04d}',fixture=name,source=relative,source_sha256=sha,
                            rate=rate,channels=x.shape[1],frames=len(x),pitch_semitones=shift,
                            pitch_ratio=float(np.float32(2**(shift/12))),time_ratio=1.,formant=mode,
                            formant_ratio=1.,output=f'renders/N{len(requests)+1:04d}.wav'))
        identity=dict(schema=SCHEMA,requests=requests)
        pack_id=hashlib.sha256(json.dumps(identity,sort_keys=True).encode()).hexdigest()
        manifest=dict(**identity,pack_id=pack_id,pipeline='native_pitch',postprocessing='none',
                      timeline='host_latency_compensated_no_fitted_shift',normalization=False,
                      status='awaiting_native_outputs')
        (staging/'requests.json').write_text(json.dumps(manifest,indent=2)+'\n')
        receipt=dict(schema='boiled-egg.native-pitch-receipt.v1',pack_id=pack_id,pipeline='native_pitch',
            postprocessing='none',timeline=manifest['timeline'],engine_family='elastique',
            host_version='',engine_name='',engine_version='',engine_mode='',
            engine_formant_settings={'off':'','harmonic':''},host_executable_sha256='',
            records=[dict(id=r['id'],source_sha256=r['source_sha256'],pitch_ratio=r['pitch_ratio'],
                time_ratio=r['time_ratio'],formant=r['formant'],formant_ratio=r['formant_ratio'],
                rate=r['rate'],output=r['output'],output_sha256='') for r in requests])
        (staging/'receipt-template.json').write_text(json.dumps(receipt,indent=2)+'\n')
        (staging/'README.txt').write_text('Native comparison inputs only: no zplane output is included.\n'
            'Use a properly licensed/evaluated native elastique engine and record actual host/engine settings.\n'
            'Request time1 and the exact float32 pitch ratio, not a rounded display value.\n'
            'Disable normalization, limiting, dither, fades and other FX; export float WAV.\n'
            'Use host PDC on the specified source interval, not fitted correlation/time warping.\n'
            'Do not resample an Elastique TSM recording and label it native pitch.\n'
            'All98 cells including unity controls are required. Empty receipt fields are rejected.\n')
        staging.rename(output)
    return manifest

def score(suite,receipt_path,render_root):
    manifest=json.loads((suite/'requests.json').read_text());receipt=json.loads(receipt_path.read_text())
    identity=dict(schema=manifest['schema'],requests=manifest['requests'])
    expected_id=hashlib.sha256(json.dumps(identity,sort_keys=True).encode()).hexdigest()
    if manifest['schema']!=SCHEMA or manifest['pack_id']!=expected_id:raise ValueError('invalid request identity')
    if receipt.get('schema')!='boiled-egg.native-pitch-receipt.v1' or receipt.get('pack_id')!=expected_id:
        raise ValueError('wrong receipt identity')
    for field,expected in [('pipeline','native_pitch'),('postprocessing','none'),
                           ('timeline','host_latency_compensated_no_fitted_shift'),('engine_family','elastique')]:
        if receipt.get(field)!=expected:raise ValueError(f'unsupported {field}; no derived fallback')
    for key in ('host_version','engine_name','engine_version','engine_mode'):
        if not isinstance(receipt.get(key),str) or not receipt[key].strip():raise ValueError(f'missing native {key}')
    sha=receipt.get('host_executable_sha256','')
    if len(sha)!=64 or any(c not in '0123456789abcdef' for c in sha):raise ValueError('missing executable identity')
    for mode in ('off','harmonic'):
        if not receipt.get('engine_formant_settings',{}).get(mode):raise ValueError('explicit formant settings required')
    records={}
    for row in receipt['records']:
        if row['id'] in records:raise ValueError('duplicate native cell')
        records[row['id']]=row
    requests=manifest['requests']
    if set(records)!={r['id'] for r in requests}:raise ValueError('incomplete native grid')
    results=[]
    for r in requests:
        row=records[r['id']]
        if any(row.get(k)!=r[k] for k in ('source_sha256','pitch_ratio','time_ratio','formant','formant_ratio','rate','output')):
            raise ValueError('native settings mismatch')
        src=inside(suite,r['source']);out=inside(render_root,row['output'])
        if digest(src)!=r['source_sha256'] or digest(out)!=row['output_sha256']:raise ValueError('audio hash mismatch')
        x,sr=sf.read(out,dtype='float64',always_2d=True)
        if sr!=r['rate'] or x.shape!=(r['frames'],r['channels']) or not np.isfinite(x).all():
            raise ValueError('native sample rate/length/channel/finite mismatch')
        make=f.attack_fixture if r['fixture']=='attack' else lambda sr,p:q.fixture(r['fixture'],sr,p)
        oracle,meta=make(sr,r['pitch_ratio'])
        if meta['family']=='formant' and r['formant']=='off':
            # No fixed-envelope error is scored against intentionally shifted formants.
            values=metrics.temporal(sf.read(src,always_2d=True)[0],x,sr)
        else:values=q.diagnose(x,oracle,meta,sr)
        if r['pitch_semitones']==0:
            source,_=sf.read(src,always_2d=True)
            values['unity_error_db']=float(metrics.db(np.mean((source-x)**2)/np.mean(source**2)))
        results.append(dict(id=r['id'],fixture=r['fixture'],rate=sr,shift=r['pitch_semitones'],
            formant=r['formant'],render_sha256=row['output_sha256'],**values))
    return dict(schema='boiled-egg.native-pitch-scores.v1',pack_id=expected_id,rows=results,
        engine={k:receipt[k] for k in ('host_version','engine_name','engine_version','engine_mode','host_executable_sha256')},
        provenance_status='declared_external_receipt; host logs required for independent attribution',
        no_fitted_alignment=True,mos_transfer=False,listening_status='not_listened')

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest='action',required=True)
    m=sub.add_parser('prepare');m.add_argument('--output',type=Path,required=True)
    m=sub.add_parser('score');
    for name in ('suite','receipt','renders','output'):m.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args()
    if a.action=='prepare':print(prepare(a.output)['pack_id'])
    else:
        if a.output.exists():raise ValueError('output exists')
        result=score(a.suite,a.receipt,a.renders)
        with a.output.open('x') as s:json.dump(result,s,indent=2,allow_nan=False);s.write('\n')
