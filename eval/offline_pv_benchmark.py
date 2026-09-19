#!/usr/bin/env python3
"""Fixed exploratory screen. Separate numerical execution from DSP promotion.

Original audio is not the unique ideal output of intentional pitch/time changes.
Whole-file process timing is not callback capacity or hard-real-time evidence.
"""
from __future__ import annotations
import argparse
import itertools
import json
import math
import os
from pathlib import Path
import re
import statistics
import subprocess
import sys
import time

import numpy as np
from scipy.fft import next_fast_len
import scipy
import soundfile as sf
import comparison_contract as c

FAMILIES = ('low', 'harmonic', 'close', 'bursts', 'mixed')
RATES = (48000, 96000)
SHIFTS = (-12, 0, 12)
ENGINES = ('wsola', 'pv_general', 'pv_transient', 'legacy_multires', 'offline_0', 'offline_8', 'offline_32')
REPEATS = 3


def fixture(family: str, rate: int) -> tuple[np.ndarray, dict]:
    if family not in FAMILIES or rate not in RATES:
        raise ValueError('unknown fixture/rate')
    t = np.arange(round(rate * .75)) / rate
    metadata = dict(family=family, rate=rate, frames=len(t), frequencies=[], amplitudes=[])
    if family == 'low': frequencies, amplitudes = [61.], [.2]
    elif family == 'harmonic': frequencies, amplitudes = [223.*k for k in range(1, 9)], [.16/k for k in range(1, 9)]
    elif family == 'close': frequencies, amplitudes = [997., 1031.], [.11, .11]
    else: frequencies, amplitudes = [], []
    x = np.zeros_like(t)
    for f, a in zip(frequencies, amplitudes): x += a * np.sin(2*np.pi*f*t)
    if frequencies:
        fade = np.minimum(1., np.minimum(t/.02, (.75-t)/.02))
        x *= fade
        metadata.update(frequencies=frequencies, amplitudes=amplitudes)
    else:
        for center in (.28, .49):
            x += .18 * np.exp(-.5*((t-center)/.0015)**2) * np.cos(2*np.pi*4000*(t-center))
        metadata['centers'] = [.28, .49]
        if family == 'mixed': x += .08*np.sin(2*np.pi*223*t)
    return x.astype(np.float32), metadata


def valid_vector(y: np.ndarray) -> np.ndarray:
    y = np.asarray(y, dtype=np.float64)
    if y.ndim != 1 or not len(y) or not np.isfinite(y).all() or np.mean(y*y) <= 1e-16:
        raise ValueError('finite nonempty nonzero mono signal required')
    return y


def tone_error(y: np.ndarray, rate: int, expected: float) -> float:
    """Unrestricted strongest spectral peak. Never search only near target pitch."""
    y = valid_vector(y)
    n = next_fast_len(len(y)*8)
    s = np.abs(np.fft.rfft((y-y.mean())*np.hanning(len(y)), n=n))
    k = int(np.argmax(s[1:]))+1
    if k >= len(s)-1 or s[k] < 1e-10: raise ValueError('unmeasurable interior frequency')
    a, b, d = np.log(np.maximum(s[k-1:k+2], 1e-30))
    delta = .5*(a-d)/(a-2*b+d)
    f = (k+delta)*rate/n
    return float(1200*np.log2(f/expected))


def components(y: np.ndarray, rate: int, frequencies: list[float]) -> tuple[list[float], float]:
    """Joint sinusoid projection measures amplitudes; never alters audio/gain/lag."""
    y = valid_vector(y)
    t = np.arange(len(y))/rate
    a = np.stack([fn(2*np.pi*f*t) for f in frequencies for fn in (np.sin, np.cos)], axis=1)
    coefficients = np.linalg.lstsq(a, y, rcond=None)[0]
    amplitudes = np.hypot(coefficients[0::2], coefficients[1::2])
    residual = float(np.sum((y-a@coefficients)**2)/np.sum(y*y))
    return amplitudes.tolist(), residual


def events(y: np.ndarray, rate: int, centers: list[float]) -> list[dict]:
    y = valid_vector(y)
    out=[]
    for center in centers:
        lo, hi = round((center-.08)*rate), round((center+.08)*rate)
        energy = y[lo:hi]**2
        total = energy.sum()
        if total <= 1e-16: raise ValueError('silent/missing expected event')
        times = np.arange(lo, hi)/rate
        cumulative = np.cumsum(energy)/total
        q = [int(np.searchsorted(cumulative, v)) for v in (.05, .95)]
        out.append(dict(position_error_ms=float((np.sum(times*energy)/total-center)*1000),
                        width_ms=float((q[1]-q[0])*1000/rate),
                        outside_10ms_fraction=float(energy[np.abs(times-center)>.01].sum()/total)))
    return out


def measure(y: np.ndarray, metadata: dict, shift: int) -> dict:
    y = valid_vector(y); rate=metadata['rate']
    if len(y) != metadata['frames']: raise ValueError('exact time1 duration mismatch')
    result=dict(peak=float(np.max(np.abs(y))), rms=float(np.sqrt(np.mean(y*y))))
    settled = y[round(.15*rate):round(.60*rate)]
    frequencies = [f * 2**(shift/12) for f in metadata['frequencies']]
    if frequencies:
        amp, residual = components(settled, rate, frequencies)
        result.update(amplitudes=amp, amplitude_error_db=(20*np.log10(np.maximum(amp, 1e-30)/np.array(metadata['amplitudes']))).tolist(),
                      undesired_energy_fraction=residual)
        levels=[]
        for start in np.arange(.15, .52, .02):
            block=y[round(start*rate):round((start+.08)*rate)]
            amplitude,_=components(block, rate, frequencies)
            levels.append(amplitude)
        levels=np.asarray(levels)
        result['amplitude_cv']=(levels.std(axis=0)/np.maximum(levels.mean(axis=0), 1e-30)).tolist()
        if metadata['family']=='low': result['pitch_error_cents']=tone_error(settled, rate, frequencies[0])
    if metadata['family']=='bursts': result['events']=events(y, rate, metadata['centers'])
    # Mixed components cannot be isolated by subtracting separately rendered audio.
    return result


def file_map(root: Path) -> dict[str, str]:
    return {str(p.resolve()): c.fingerprint(p) for p in sorted(root.rglob('*'))
            if p.is_file() and '.git' not in p.parts and '__pycache__' not in p.parts}


def binary_map(path: Path) -> dict[str, str]:
    path=path.resolve(strict=True)
    # These paths are explicitly supplied freshly compiled trusted project binaries.
    dep=subprocess.run(['ldd', str(path)], text=True, capture_output=True, check=True)
    if 'not found' in dep.stdout: raise ValueError('unresolved binary dependency')
    files={str(path):c.fingerprint(path)}
    for line in dep.stdout.splitlines():
        m=re.search(r'(?:=>\s+)?(/\S+)',line)
        if m:
            p=Path(m[1]).resolve(strict=True);files[str(p)]=c.fingerprint(p)
    return files


def prepare(args) -> dict:
    root=args.output.resolve();root.mkdir(parents=True,exist_ok=False);(root/'sources').mkdir()
    binary={k:str(getattr(args,k).resolve(strict=True)) for k in ('sdk','legacy','offline')}
    files={}
    for value in binary.values():files.update(binary_map(Path(value)))
    files.update(file_map(Path(__file__).resolve().parents[1]/'research/offline_pv'))
    for p in (Path(__file__),Path(c.__file__)):
        files[str(p.resolve())]=c.fingerprint(p)
    source=[]
    for rate,family in itertools.product(RATES,FAMILIES):
        x,meta=fixture(family,rate);p=root/'sources'/f'{family}-{rate}.wav';sf.write(p,x,rate,subtype='FLOAT')
        source.append(dict(path=str(p),metadata=meta,audio=c.inspect_audio(p)))
    plan=dict(schema='boiled-egg.offline-pv-screen.v1',base_main='8143a19b1a7681cc0815b3f14a5c20694f2b052f',
        legacy_ref='dd04c9388443ff3358af34b85ca5a5c880f45e71',engines=list(ENGINES),shifts=list(SHIFTS),repeats=REPEATS,
        expected_cells=210,expected_runs=630,binaries=binary,files=files,sources=source,
        environment=dict(python=sys.version,numpy=np.__version__,scipy=scipy.__version__,soundfile=sf.__version__),
        timing='three serial fresh-process whole-file runs including startup and file IO; not callback capacity',
        quality_selection=None)
    c.json_write(root/'plan.json',plan)
    return plan


def check_identity(plan: dict) -> None:
    for filename, sha in plan['files'].items():
        if c.fingerprint(Path(filename))!=sha: raise ValueError('changed code/binary/dependency')
    for source in plan['sources']:
        if c.inspect_audio(Path(source['path']))!=source['audio']:raise ValueError('changed source')


def command(plan: dict, engine: str, source: Path, case: Path, shift: int) -> tuple[list[str],Path]:
    b=plan['binaries'];out=case/'output.wav'
    if engine.startswith('offline_'):
        out=case/'render'/'output.wav'
        cmd=[b['offline'],str(source),str(case/'render'),'--execution','offline','--allow-experimental',
             '--iterations',engine.split('_')[1],'--time','1','--pitch-semitones',str(shift),'--formant','off']
    elif engine=='legacy_multires':
        cmd=[b['legacy'],str(source),str(out),'--time','1','--pitch-semitones',str(shift),'--formant','off','--block','64','--crossover','6500','--taps','129']
    else:
        quality='transient' if engine=='pv_transient' else 'general'
        cmd=[b['sdk'],str(source),str(out),'--backend','wsola' if engine=='wsola' else 'pv','--quality',quality,
             '--allow-experimental','--formant','off','--time','1','--pitch-semitones',str(shift),'--block','64']
    return cmd,out


def validate_grid(rows: list[dict], plan: dict) -> None:
    expected={(s['metadata']['family'],s['metadata']['rate'],shift,e,r)
              for s in plan['sources'] for shift in plan['shifts'] for e in plan['engines'] for r in range(plan['repeats'])}
    actual=[(r['family'],r['rate'],r['shift'],r['engine'],r['repeat']) for r in rows]
    if len(actual)!=len(set(actual)) or set(actual)!=expected or len(actual)!=plan['expected_runs']:
        raise ValueError('missing/duplicate/extra run; no surviving-subset completion')


def run(args) -> dict:
    plan_path=args.plan.resolve(strict=True)
    if c.fingerprint(plan_path)!=args.plan_sha256:raise ValueError('plan hash mismatch')
    plan=json.loads(plan_path.read_text());check_identity(plan)
    if plan['engines']!=list(ENGINES) or plan['shifts']!=list(SHIFTS) or plan['repeats']!=3:raise ValueError('not fixed protocol grid')
    root=args.output.resolve();root.mkdir(parents=True,exist_ok=False)
    rows=[]
    for source,shift,engine in itertools.product(plan['sources'],plan['shifts'],plan['engines']):
        meta=source['metadata']; family,rate=meta['family'],meta['rate']
        for repeat in range(plan['repeats']):
            case=root/f'{family}-{rate}-{shift:+d}-{engine}'/str(repeat);case.mkdir(parents=True)
            cmd,out=command(plan,engine,Path(source['path']),case,shift)
            row=dict(family=family,rate=rate,shift=shift,engine=engine,repeat=repeat,status='failed',errors=[],
                     case=str(case.relative_to(root)),command=cmd)
            c.json_write(case/'started.json',row)
            start=time.perf_counter()
            try:
                with (case/'stdout.log').open('w') as stdout,(case/'stderr.log').open('w') as stderr:
                    process=subprocess.run(['/usr/bin/time','-f','%e %U %S %M','-o',str(case/'time.txt'),*cmd],
                                           stdout=stdout,stderr=stderr,timeout=180,env={**os.environ,'OMP_NUM_THREADS':'1','OPENBLAS_NUM_THREADS':'1'})
                row['wall_seconds']=time.perf_counter()-start; row['returncode']=process.returncode
                lines=(case/'time.txt').read_text().splitlines();wall,user,system,rss=map(float,lines[-1].split())
                row.update(time_wall_seconds=wall,user_seconds=user,system_seconds=system,max_rss_kib=int(rss))
                if process.returncode:raise ValueError(f'process exit{process.returncode}')
                audio=c.inspect_audio(out)
                if c.output_checks(source['audio'],audio,c.Request(duration_tolerance_frames=0)):raise ValueError('output contract mismatch')
                y,sr=sf.read(out,dtype='float64');row['metrics']=measure(y,meta,shift)
                row.update(output=audio,status='rendered')
                if engine.startswith('offline_'):row['renderer']=json.loads((case/'render'/'report.json').read_text())
            except (ValueError,OSError,RuntimeError,subprocess.TimeoutExpired) as exc:
                row['errors'].append(f'{type(exc).__name__}: {exc}')
                row['elapsed_until_failure']=time.perf_counter()-start
            c.json_write(case/'receipt.json',row);rows.append(row)
        c.json_write(root/'progress.json',dict(completed=len(rows),expected=plan['expected_runs']))
        print(len(rows),family,rate,shift,engine,rows[-1]['status'],flush=True)
    validate_grid(rows,plan);check_identity(plan)
    cells=[]
    for group in (rows[i:i+3] for i in range(0,len(rows),3)):
        complete=all(r['status']=='rendered' for r in group)
        cell={k:group[0][k] for k in ('family','rate','shift','engine')}
        cell.update(rendered=complete,repeat_pcm_equal=complete and len({r['output']['sha256'] for r in group})==1,
                    median_wall_seconds=statistics.median(r['wall_seconds'] for r in group) if complete else None,
                    max_rss_kib=max(r['max_rss_kib'] for r in group) if complete else None)
        if complete:cell.update(metrics=group[0]['metrics'],renderer=group[0].get('renderer'))
        cells.append(cell)
    report=dict(schema=plan['schema'],plan_sha256=args.plan_sha256,execution_complete=all(r['status']=='rendered' for r in rows),
                expected_cells=210,expected_runs=630,rows=rows,cells=cells,quality_selection=None,
                promotion='not decided by execution success; paired quality gates require separate review')
    c.json_write(root/'summary.json',report)
    return report


def main() -> int:
    p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest='action',required=True)
    a=sub.add_parser('prepare')
    for k in ('sdk','legacy','offline','output'):a.add_argument('--'+k,type=Path,required=True)
    a=sub.add_parser('run');a.add_argument('--plan',type=Path,required=True);a.add_argument('--plan-sha256',required=True);a.add_argument('--output',type=Path,required=True)
    args=p.parse_args()
    if args.action=='prepare':prepare(args);print(c.fingerprint(args.output/'plan.json'));return 0
    result=run(args);return 0 if result['execution_complete'] else 2

if __name__=='__main__':raise SystemExit(main())
