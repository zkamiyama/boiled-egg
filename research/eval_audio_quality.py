#!/usr/bin/env python3
"""Expanded synthetic-oracle and natural-corpus diagnostics; no perceptual score.

5 synthetic families: attacks, partials, noise, stereo, fixed-formant vowels.
Natural corpus: exact and measured target grids are separate, Harmonic only.
All nonunity comparisons are descriptive. Quality thresholds are not retrofitted.
"""
from __future__ import annotations
import argparse
import concurrent.futures as cf
import csv
import json
import math
import platform
import re
import subprocess
import tempfile
from collections import defaultdict
from pathlib import Path
import numpy as np
import scipy
import soundfile as sf
import audio_quality_metrics as m
import eval_fuzzy_corpus as e

SCHEMA = 'boiled-egg.expanded-audio-quality.v1'
SHIFTS = (-12, -7, -3, 0, 3, 7, 12)
FIXTURES = ('attack', 'harmonics', 'inharmonic', 'noise0', 'noise1', 'noise2',
            'stereo0', 'stereo70', 'stereo100', 'vowel_a', 'vowel_i')


def wave(rate: int, frequencies: np.ndarray, amplitudes: np.ndarray, n: int) -> np.ndarray:
    t = np.arange(n)/rate
    out = np.zeros(n)
    for i, (freq, amp) in enumerate(zip(frequencies, amplitudes)):
        out += amp*np.sin(2*np.pi*freq*t+i*.71)
    return out


def band_noise(rate: int, n: int, low: float, high: float, seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    f = np.fft.rfftfreq(n, 1/rate)
    z = np.fft.rfft(rng.standard_normal(n))
    z[(f < low) | (f > high)] = 0
    x = np.fft.irfft(z, n=n)
    return .1*x/np.sqrt(np.mean(x*x))


def fixture(name: str, rate: int, ratio: float) -> tuple[np.ndarray, dict]:
    n = round(rate*2.0)
    meta = {}
    if name == 'attack':
        starts, duration = [.3, .7, 1.1, 1.5], .002
        f = np.array([2113., 3299., 5113., 7331.])*ratio
        x = wave(rate, f, np.full(4, .12), n)
        gate = np.zeros(n)
        for start in starts:
            count = round(duration*rate)
            gate[round(start*rate):round(start*rate)+count] = np.sin(np.pi*np.arange(count)/count)**2
        x *= gate
        meta.update(starts=starts, duration=duration, family='attack')
    elif name.startswith('noise') or name.startswith('stereo'):
        seed = int(name[-1]) if name.startswith('noise') else 11
        x = band_noise(rate, n, 1800*ratio, 7000*ratio, seed+100)
        meta.update(band=(2200*ratio, 6200*ratio), family='noise')
        if name.startswith('stereo'):
            rho = {'stereo0':0., 'stereo70':.7, 'stereo100':-1.}[name]
            independent = band_noise(rate, n, 1800*ratio, 7000*ratio, 888)
            x = np.c_[x, rho*x+np.sqrt(1-rho*rho)*independent]
            meta.update(family='stereo', rho=rho)
    else:
        if name.startswith('vowel'):
            f = 120*np.arange(1, 81)*ratio
            centers = (700,1200,2600) if name == 'vowel_a' else (300,2300,3000)
            # Known positive resonant envelope, fixed in Hz, not a human voice.
            amplitudes = sum(g/(1+((f-c)/w)**2) for c,w,g in zip(centers,(80,130,180),(1.,.7,.45)))
            meta['family'] = 'formant'
        elif name == 'harmonics':
            f = 110*np.arange(1, 17)*ratio
            amplitudes = 1/np.sqrt(np.arange(1,17))
            meta['family'] = 'partials'
        elif name == 'inharmonic':
            f = np.array([173.,257.3,389.1,587.9,887.3,1337.1,2017.9,3044.3,4592.9])*ratio
            amplitudes = np.ones(len(f))
            meta['family'] = 'partials'
        else:
            raise ValueError('unknown fixture')
        x = wave(rate, f, amplitudes, n)
        x *= .1/np.sqrt(np.mean(x*x))
        meta['frequencies'] = f
    x = m.audio(x)
    return x.astype('float32'), meta


def diagnose(x: np.ndarray, oracle: np.ndarray, meta: dict, rate: int) -> dict:
    m.paired(x, oracle, rate)
    family = meta['family']
    if family == 'attack':
        result = m.attacks(x, rate, meta['starts'], meta['duration'])
        target = m.attacks(oracle, rate, meta['starts'], meta['duration'])
        result['width_excess_ms'] = result['attack_width_ms']-target['attack_width_ms']
        result['oracle_width_ms'] = target['attack_width_ms']
    elif family in ('partials','formant'):
        result = m.partials(x, oracle, rate, meta['frequencies'])
    elif family == 'noise':
        result = m.noise(x,rate,meta['band']); target = m.noise(oracle,rate,meta['band'])
        for field in list(result):
            result['oracle_'+field] = target[field]
            result[field+'_delta'] = result[field]-target[field]
    else:
        result = m.stereo(x,rate,meta['band']); target = m.stereo(oracle,rate,meta['band'])
        for field in list(result):
            result['oracle_'+field] = target[field]
            result[field+'_abs_error'] = abs(result[field]-target[field])
    if not all(np.isfinite(v) for v in result.values()):
        raise ValueError('non-finite quality metric')
    return result


def synth_job(job: tuple) -> list[dict]:
    name, rate, shift, pv, multi, block, profiles = job
    ratio = float(np.float32(2**(shift/12)))
    source, _ = fixture(name, rate, 1.)
    oracle, meta = fixture(name, rate, ratio)
    rows = []
    with tempfile.TemporaryDirectory(prefix='audio-quality-synth-') as tmp:
        src, dst = Path(tmp)/'source.wav', Path(tmp)/'render.wav'
        sf.write(src, source, rate, subtype='FLOAT')
        source_hash = e.fingerprint(src)
        for formant in (e.FORMANTS if meta['family']=='formant' else ('off',)):
            for profile in profiles:
                command = e.command(pv,multi,src,dst,profile,formant,ratio,block)
                scale = rate//48000
                if profile != 'multires':
                    fft = (2048 if profile=='general' else 1024)*scale
                    command[command.index('--fft')+1] = str(fft)
                    command[command.index('--hop')+1] = str(256*scale)
                proc = subprocess.run(command, capture_output=True, text=True, timeout=120)
                if proc.returncode:
                    raise RuntimeError(f'{name}/{profile}: {proc.stderr}')
                x, out_rate = e.checked_audio(dst)
                if out_rate != rate or x.shape != source.shape:
                    raise ValueError('synthetic render metadata mismatch')
                row = dict(fixture=name,family=meta['family'],rate=rate,shift=shift,
                    profile=profile,formant=formant,block=block,control_ratio=ratio,
                    window_policy='fixed_multires' if profile=='multires' else 'rate_scaled',
                    source_sha256=source_hash,render_sha256=e.fingerprint(dst),
                    frames=len(x),channels=x.shape[1],duration_error_frames=0,
                    peak=float(np.max(np.abs(x))),**diagnose(x,oracle,meta,rate))
                if shift == 0:
                    # Here the oracle equals the input, so waveform SNR is valid.
                    err = np.mean((x.astype(float)-source)**2)
                    row['unity_error_db'] = float(m.db(err/np.mean(source.astype(float)**2)))
                rows.append(row)
    return rows


def natural_job(job: tuple) -> list[dict]:
    cell, refs, tests, pv, multi, block, profiles = job
    src = e.inside(refs, cell['reference_name'])
    if e.fingerprint(src) != cell['reference_sha256']:
        raise ValueError('source changed after plan')
    source, rate = e.checked_audio(src)
    rows = []
    def record(x, profile, digest):
        if x.shape != source.shape:
            raise ValueError('natural shape mismatch')
        rows.append(dict(family=cell['family'],stem=cell['stem'],condition_id=cell['condition_id'],
            shift=cell['pitch_semitones'],rate=rate,profile=profile,
            formant='not_applicable' if profile==e.BASELINE else 'harmonic',block=block,
            source_sha256=cell['reference_sha256'],render_sha256=digest,
            frames=len(x),channels=x.shape[1],duration_error_frames=0,
            **m.temporal(source,x,rate)))
    with tempfile.TemporaryDirectory(prefix='audio-quality-corpus-') as tmp:
        dst = Path(tmp)/'render.wav'
        if cell['family']=='derived':
            test = e.inside(tests,cell['processed_name'])
            if e.fingerprint(test)!=cell['processed_sha256']:
                raise ValueError('TSM input changed')
            x, sr = e.checked_audio(test)
            if sr!=rate:
                raise ValueError('TSM sample rate mismatch')
            sf.write(dst,e.exact_resample(x,len(source)),rate,subtype='FLOAT')
            x, _ = e.checked_audio(dst); record(x,e.BASELINE,e.fingerprint(dst))
        for profile in profiles:
            cmd = e.command(pv,multi,src,dst,profile,'harmonic',cell['control_ratio'],block)
            proc = subprocess.run(cmd,capture_output=True,text=True,timeout=120)
            if proc.returncode:
                raise RuntimeError(proc.stderr)
            x,sr = e.checked_audio(dst)
            if sr!=rate:
                raise ValueError('render sample rate mismatch')
            record(x,profile,e.fingerprint(dst))
    return rows


def aggregate(rows: list[dict], keys: tuple[str,...]) -> list[dict]:
    groups = defaultdict(list)
    for row in rows:
        groups[tuple(row[k] for k in keys)].append(row)
    report=[]
    ignored = {*keys,'rate','shift','block','control_ratio','active_bins','analyzed_partials','frames','channels','duration_error_frames'}
    for key, selected in sorted(groups.items()):
        fields = set.intersection(*(set(r) for r in selected))
        values={}
        for field in sorted(fields-ignored):
            v=[r[field] for r in selected]
            if all(type(i) in (int,float) for i in v):
                values[field]=dict(mean=float(np.mean(v)),median=float(np.median(v)),
                    p95=float(np.quantile(v,.95)),min=float(min(v)),max=float(max(v)))
        report.append(dict(zip(keys,key),n=len(selected),metrics=values))
    return report


def cluster_differences(rows: list[dict]) -> list[dict]:
    """Paired source-cluster bootstrap; retain all pitches inside each source.

Descriptive 95% percentile intervals, fixed 4000 draws; no multiple-testing
correction or population/perceptual inference. Duplicate rows are rejected.
"""
    index={}
    for r in rows:
        k=(r['family'],r['stem'],r['condition_id'],r['profile'])
        if k in index: raise ValueError('duplicate corpus measurement')
        index[k]=r
    result=[]
    for family in sorted({r['family'] for r in rows}):
        base=[r for r in rows if r['family']==family and r['profile']=='transient']
        for profile in sorted({r['profile'] for r in rows if r['family']==family}-{'transient'}):
            for metric in ('rms_shape_error_db','energy_transport_ms'):
                clusters=defaultdict(list)
                for b in base:
                    c=index[(family,b['stem'],b['condition_id'],profile)]
                    clusters[b['stem']].append(c[metric]-b[metric])
                d=np.array([np.mean(v) for _,v in sorted(clusters.items())])
                rng=np.random.default_rng(20260913)
                draws=d[rng.integers(0,len(d),size=(4000,len(d)))].mean(axis=1)
                result.append(dict(family=family,profile=profile,metric=metric,sources=len(d),
                    conditions=len(base),delta_vs_transient=float(d.mean()),
                    ci95=list(map(float,np.quantile(draws,[.025,.975])))))
    return result


def write_csv(path: Path, rows: list[dict]) -> None:
    fields=sorted(set.union(*(set(r) for r in rows)))
    with path.open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)


def run(args: argparse.Namespace) -> dict:
    if (not re.fullmatch('[0-9a-f]{40}',args.source_commit) or args.workers<1 or
        not 1<=args.block<=16384 or not args.rates or set(args.rates)-{48000,96000} or
        not args.shifts or set(args.shifts)-set(SHIFTS) or not args.fixtures or
        set(args.fixtures)-set(FIXTURES) or not args.profiles or set(args.profiles)-set(e.PROFILES)):
        raise ValueError('invalid grid or execution arguments')
    for values in (args.rates,args.shifts,args.fixtures,args.profiles):
        if len(set(values))!=len(values): raise ValueError('duplicate grid entry')
    pv,multi=[p.resolve(strict=True) for p in (args.pv_cli,args.multires_cli)]
    hashes=dict(pv=e.fingerprint(pv),multires=e.fingerprint(multi))
    analysis_hashes={p.name:e.fingerprint(p) for p in (Path(__file__),Path(m.__file__))}
    catalog_hash=e.fingerprint(args.catalog) if args.catalog else None
    sources=processed=cells=[]
    if any((args.ref_dir,args.test_dir,args.catalog)):
        if not all((args.ref_dir,args.test_dir,args.catalog)):
            raise ValueError('all three corpus paths required')
        sources,processed,cells=e.plan(args.ref_dir,args.test_dir,args.catalog)
        cells=[c for c in cells if c['scope']=='target']
    output=args.output.resolve()
    if output.exists(): raise ValueError('output must not exist')
    output.parent.mkdir(parents=True,exist_ok=True)
    jobs=[(f,sr,st,pv,multi,args.block,args.profiles)
          for f in args.fixtures for sr in args.rates for st in args.shifts]
    expected=sum(len(args.profiles)*(3 if f.startswith('vowel') else 1)
                 for f in args.fixtures)*len(args.rates)*len(args.shifts)
    with tempfile.TemporaryDirectory(prefix='.quality-',dir=output.parent) as tmp:
        staging=Path(tmp)/'report';staging.mkdir()
        synth=[];corpus=[]
        with cf.ProcessPoolExecutor(max_workers=args.workers) as pool:
            for i,part in enumerate(pool.map(synth_job,jobs),1):
                synth.extend(part)
                if i%10==0: print(f'synthetic {i}/{len(jobs)}',flush=True)
            natural=[(c,args.ref_dir,args.test_dir,pv,multi,args.block,args.profiles) for c in cells]
            for i,part in enumerate(pool.map(natural_job,natural),1):
                corpus.extend(part)
                if i%10==0: print(f'natural {i}/{len(natural)}',flush=True)
        if len(synth)!=expected or len(corpus)!=sum(len(args.profiles)+(c['family']=='derived') for c in cells):
            raise ValueError('incomplete grid')
        if hashes!=dict(pv=e.fingerprint(pv),multires=e.fingerprint(multi)):
            raise ValueError('renderer changed during run')
        if any(e.fingerprint(Path(__file__).parent/name)!=digest for name,digest in analysis_hashes.items()):
            raise ValueError('analysis code changed during run')
        if cells and (e.fingerprint(args.catalog)!=catalog_hash or
            any(e.fingerprint(e.inside(args.ref_dir,s['reference_name']))!=s['reference_sha256'] for s in sources) or
            any(e.fingerprint(e.inside(args.test_dir,s['name']))!=s['sha256'] for s in processed)):
            raise ValueError('corpus input changed during run')
        write_csv(staging/'synthetic.csv',synth)
        if corpus: write_csv(staging/'corpus.csv',corpus)
        report=dict(schema=SCHEMA,base_source_commit=args.source_commit,executables=hashes,
            analysis_files_sha256=analysis_hashes,catalog_sha256=catalog_hash,
            versions=dict(python=platform.python_version(),numpy=np.__version__,scipy=scipy.__version__,soundfile=sf.__version__),
            rates=args.rates,shifts=args.shifts,profiles=args.profiles,fixtures=args.fixtures,block=args.block,
            synthetic_renders=len(synth),corpus_renders=len(corpus),sources=sources,processed=processed,
            synthetic=aggregate([r for r in synth if r['shift']!=0],('family','rate','profile','formant')),
            unity=aggregate([r for r in synth if r['shift']==0],('profile','formant')),
            corpus=aggregate(corpus,('family','profile')) if corpus else [],
            corpus_paired_intervals=cluster_differences(corpus) if corpus and 'transient' in args.profiles else [],
            files={p.name:e.fingerprint(p) for p in staging.iterdir()},listening_status='not_listened',
            automatic_promotion=False,mos_transfer=False,
            limitations='Research diagnostics, not validated perceptual ratings. Raw output untouched. '
                'Synthetic oracles are analytical/statistical definitions, not recordings. '
                'Only steady tests crop 250ms edges; attack/corpus tests keep timing without alignment. '
                'PV windows scaled at96k, Multi-resolution existing fixed windows explicitly retained. '
                'Derived baseline is TSM plus Fourier resampling, not native pitch output. '
                'Natural temporal measures are source-relative diagnostics, not ideal-output errors. '
                'Intervals resample sources, not pitch cells; no multiple-comparison correction.')
        (staging/'summary.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n',encoding='utf-8')
        staging.rename(output)
    return report


def main() -> None:
    p=argparse.ArgumentParser(description=__doc__)
    for flag in ('pv-cli','multires-cli','output'):
        p.add_argument('--'+flag,type=Path,required=True)
    for flag in ('ref-dir','test-dir','catalog'):
        p.add_argument('--'+flag,type=Path)
    p.add_argument('--source-commit',required=True,help='Base Git source; analysis files are independently fingerprinted')
    p.add_argument('--rates',nargs='+',type=int,default=[48000,96000])
    p.add_argument('--shifts',nargs='+',type=int,default=list(SHIFTS))
    p.add_argument('--fixtures',nargs='+',default=list(FIXTURES))
    p.add_argument('--profiles',nargs='+',default=list(e.PROFILES))
    p.add_argument('--workers',type=int,default=2);p.add_argument('--block',type=int,default=64)
    r=run(p.parse_args())
    print(f'{r["synthetic_renders"]} synthetic + {r["corpus_renders"]} natural renders',flush=True)

if __name__=='__main__': main()
