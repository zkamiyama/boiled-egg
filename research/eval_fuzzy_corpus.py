#!/usr/bin/env python3
"""Causal fuzzy ablations vs unchanged profiles, exact and measured TSM grids.

No MOS transfer. Derived Elastique is supplied TSM plus Fourier resampling, NOT
native pitch-shifter output. Exact semitone and measured-ratio cells stay separate.
All raw float WAVs remain unlimited. Publish only a complete fingerprinted grid.
"""
from __future__ import annotations
import argparse
import concurrent.futures as cf
import csv
import json
import math
import re
import subprocess
import tempfile
from collections import defaultdict
from pathlib import Path
import numpy as np
import scipy
import soundfile as sf
from audit_tsm_inputs import score_rows
from eval_elastique_pitch import category, exact_resample
from eval_multires_corpus import checked_audio, fingerprint
from eval_reference_profiles import FORMANTS, PITCHES, measure, preflight
from make_reference_profile_pack import inside

SCHEMA = 'boiled-egg.fuzzy-corpus.v1'
PROFILES = ('general', 'transient', 'multires', 'fuzzy-noise', 'fuzzy')
BASELINE = 'derived_elastique'


def plan(ref_dir: Path, test_dir: Path, catalog: Path) -> tuple[list[dict], list[dict], list[dict]]:
    sources = preflight(ref_dir, catalog)
    by_name = {s['reference_name']: s for s in sources}
    if len({s['stem'].casefold() for s in sources}) != len(sources):
        raise ValueError('ambiguous source basenames')
    index = {r['test_name']: r for r in score_rows(catalog)}
    processed, derived = [], defaultdict(list)
    for path in sorted(test_dir.glob('*.wav')):
        row = index.get(path.name)
        if row is None or row['ref_name'] not in by_name:
            raise ValueError(f'unmatched test/reference: {path.name}')
        source = by_name[row['ref_name']]
        path = inside(test_dir, path.name)
        audio, rate = checked_audio(path)
        if rate != source['sample_rate'] or audio.shape[1] != source['channels']:
            raise ValueError(f'test rate/channel mismatch: {path.name}')
        record = dict(name=path.name, sha256=fingerprint(path), frames=len(audio),
                      reference_name=row['ref_name'], method=row['method'], tsm=row['TSM'])
        processed.append(record)
        if row['method'] == 'Elastique':
            derived[row['ref_name']].append(record)
    if not processed or any(not derived[name] for name in by_name):
        raise ValueError('each supplied reference requires an exact catalog Elastique pair')
    cells = []
    for source in sources:
        choices = [('exact', float(2.0**(st/12.0)), None) for st in PITCHES]
        choices += [('derived', p['frames']/source['frames'], p) for p in derived[source['reference_name']]]
        for family, ratio, test in choices:
            if not .25 <= ratio <= 4:
                raise ValueError('measured pitch outside renderer range')
            pitch = 12*math.log2(ratio)
            cells.append(dict(**source, condition_id=f'C{len(cells)+1:04d}', family=family,
                scope='target' if abs(pitch) <= 12.0001 else 'stress', pitch_semitones=pitch,
                control_ratio=float(np.float32(ratio)), measured_ratio=ratio,
                review_category=category(source['stem']),
                processed_name=test['name'] if test else '',
                processed_sha256=test['sha256'] if test else ''))
    return sources, processed, cells


def command(pv: Path, multi: Path, source: Path, dest: Path,
            profile: str, formant: str, ratio: float, block: int) -> list[str]:
    if profile not in PROFILES or formant not in FORMANTS:
        raise ValueError('invalid profile/formant')
    cmd = [str(multi if profile == 'multires' else pv), str(source), str(dest),
           '--time', '1', '--pitch-ratio', format(ratio, '.9g'), '--formant', formant,
           '--block', str(block)]
    if profile != 'multires':
        cmd += ['--fft', '2048' if profile == 'general' else '1024', '--hop', '256',
                '--mode', profile if profile.startswith('fuzzy') else 'locked']
    return cmd


def job(args: tuple) -> list[dict]:
    cell, refs, tests, pv, multi, output, formants, block = args
    source = inside(refs, cell['reference_name'])
    if fingerprint(source) != cell['reference_sha256']:
        raise ValueError('reference changed after preflight')
    reference, rate = checked_audio(source)
    folder = output/'renders'/cell['condition_id']
    folder.mkdir(parents=True)
    rows = []

    def record(path: Path, profile: str, formant: str) -> None:
        audio, out_rate = checked_audio(path)
        if out_rate != rate or audio.shape != reference.shape:
            raise ValueError(f'render metadata mismatch: {path}')
        frame, channel = np.unravel_index(np.argmax(np.abs(audio)), audio.shape)
        rows.append(dict(**cell, profile=profile, formant=formant, **measure(reference, audio, rate),
            duration_error_frames=0, peak_time_seconds=float(frame/rate), peak_channel=int(channel),
            samples_above_unity=int(np.count_nonzero(np.abs(audio)>1)),
            render_path=path.relative_to(output).as_posix(), render_sha256=fingerprint(path)))

    if cell['family'] == 'derived':
        test = inside(tests, cell['processed_name'])
        if fingerprint(test) != cell['processed_sha256']:
            raise ValueError('processed audio changed after preflight')
        audio, test_rate = checked_audio(test)
        if test_rate != rate or audio.shape[1] != reference.shape[1] or len(audio)/len(reference) != cell['measured_ratio']:
            raise ValueError('derived ratio/metadata mismatch')
        dest = folder/(BASELINE+'.wav')
        sf.write(dest, exact_resample(audio, len(reference)), rate, subtype='FLOAT')
        record(dest, BASELINE, 'not_applicable')
    for formant in formants:
        for profile in PROFILES:
            dest = folder/f'{profile}_{formant}.wav'
            cmd = command(pv, multi, source, dest, profile, formant, cell['control_ratio'], block)
            run = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            if run.returncode:
                raise RuntimeError(f'{cell["condition_id"]}/{profile}/{formant}: {run.stderr}')
            record(dest, profile, formant)
    return rows


def validate(rows: list[dict], cells: list[dict], formants: list[str]) -> dict:
    expected = {(c['condition_id'], p, f) for c in cells for f in formants for p in PROFILES}
    expected |= {(c['condition_id'], BASELINE, 'not_applicable') for c in cells if c['family']=='derived'}
    if len({c['condition_id'] for c in cells}) != len(cells):
        raise ValueError('duplicate planned cell')
    planned = {c['condition_id']: c for c in cells}
    actual = {}
    for row in rows:
        key = row['condition_id'], row['profile'], row['formant']
        if key in actual or key not in expected:
            raise ValueError('duplicate/unexpected grid row')
        if any(row[k] != v for k,v in planned[row['condition_id']].items()):
            raise ValueError('row provenance differs from planned cell')
        if row['duration_error_frames'] != 0 or any(not math.isfinite(row[k]) for k in ('env','onset','rms','peak')):
            raise ValueError('invalid duration or nonfinite metrics')
        actual[key] = row
    if not expected or set(actual) != expected:
        raise ValueError('incomplete grid')
    return actual


def summarize(rows: list[dict], cells: list[dict], formants: list[str]) -> dict:
    indexed = validate(rows, cells, formants)
    comparisons = []
    peaks = []
    for family, scope in sorted({(c['family'],c['scope']) for c in cells}):
        selected = [c for c in cells if c['family']==family and c['scope']==scope]
        for formant in formants:
            for baseline in ('transient','multires',BASELINE) if family=='derived' else ('transient','multires'):
                for profile in PROFILES:
                    if profile == baseline: continue
                    pairs = [(indexed[(c['condition_id'],profile,formant)], indexed[(c['condition_id'],baseline,
                              'not_applicable' if baseline==BASELINE else formant)]) for c in selected]
                    de = [a['env']-b['env'] for a,b in pairs]
                    do = [a['onset']-b['onset'] for a,b in pairs]
                    comparisons.append(dict(family=family,scope=scope,formant=formant,baseline=baseline,
                        profile=profile,conditions=len(pairs),mean_env_delta=float(np.mean(de)),
                        mean_onset_delta=float(np.mean(do)),env_wins=sum(v<0 for v in de),
                        onset_wins=sum(v>0 for v in do)))
            for profile in PROFILES:
                group = [indexed[(c['condition_id'],profile,formant)] for c in selected]
                base = [indexed[(c['condition_id'],'transient',formant)] for c in selected]
                ratios = [a['peak']/b['peak'] for a,b in zip(group,base) if b['peak']>0]
                peaks.append(dict(family=family,scope=scope,formant=formant,profile=profile,
                    max_peak=max(r['peak'] for r in group),above_unity=sum(r['peak']>1 for r in group),
                    peak_ratio_p95=float(np.quantile(ratios,.95)) if ratios else None,
                    ratio_above_1_1=sum(r>1.1 for r in ratios)))
    return dict(measurements=len(rows),dsp_renders=sum(r['profile']!=BASELINE for r in rows),
        derived_renders=sum(r['profile']==BASELINE for r in rows),exact_duration_renders=len(rows),
        conditions=len(cells),comparisons=comparisons,peak_review=peaks)


def run(args: argparse.Namespace) -> dict:
    if not re.fullmatch('[0-9a-f]{40}',args.source_commit) or not 1<=args.block<=16384 or args.workers<1:
        raise ValueError('invalid commit/block/workers')
    if not args.formants or len(set(args.formants))!=len(args.formants) or set(args.formants)-set(FORMANTS):
        raise ValueError('invalid/duplicate formants')
    output = args.output.resolve()
    if output.exists(): raise ValueError('output must not exist')
    refs,tests,pv,multi = [p.resolve(strict=True) for p in (args.ref_dir,args.test_dir,args.pv_cli,args.multires_cli)]
    catalog_hash = fingerprint(args.catalog)
    sources,processed,cells = plan(refs,tests,args.catalog)
    executables = {'pv':fingerprint(pv),'multires':fingerprint(multi)}
    output.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.fuzzy-corpus-',dir=output.parent) as tmp:
        staging = Path(tmp)/'complete'; staging.mkdir()
        jobs = [(c,refs,tests,pv,multi,staging,args.formants,args.block) for c in cells]
        rows = []
        with cf.ProcessPoolExecutor(max_workers=args.workers) as executor:
            for n, part in enumerate(executor.map(job,jobs),1):
                rows.extend(part); print(f'condition {n}/{len(jobs)}; measurements {len(rows)}',flush=True)
        result = summarize(rows,cells,args.formants)
        if executables != {'pv':fingerprint(pv),'multires':fingerprint(multi)} or fingerprint(args.catalog)!=catalog_hash:
            raise ValueError('executable/catalog changed during evaluation')
        if any(fingerprint(inside(refs,s['reference_name']))!=s['reference_sha256'] for s in sources) or any(
                fingerprint(inside(tests,p['name']))!=p['sha256'] for p in processed):
            raise ValueError('input audio changed during evaluation')
        with (staging/'metrics.csv').open('w',newline='',encoding='utf-8') as stream:
            writer=csv.DictWriter(stream,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
        result.update(schema=SCHEMA,source_commit=args.source_commit,executables=executables,
            catalog_sha256=catalog_hash,metrics_sha256=fingerprint(staging/'metrics.csv'),
            sources=sources,processed=processed,cells=cells,formants=args.formants,profiles=list(PROFILES),
            block=args.block,versions=dict(numpy=np.__version__,scipy=scipy.__version__,soundfile=sf.__version__),
            listening_status='not_listened',mos_transfer=False,automatic_promotion=False,
            interpretation='Causal adaptation/ablations, not full published FPV. Derived Elastique is TSM + '
            'offline Fourier resampling, not native pitch output. Target and stress grids are separate. '
            'Categories from catalog; review categories use the pre-existing filename map. '
            'Per-channel broad-envelope/onset diagnostics are not perceptual ratings. Raw peaks are not true peaks.')
        (staging/'summary.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n',encoding='utf-8')
        staging.rename(output)
    return result


def main() -> None:
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('pv-cli','multires-cli','ref-dir','test-dir','catalog','output'):
        parser.add_argument('--'+name,type=Path,required=True)
    parser.add_argument('--source-commit',required=True)
    parser.add_argument('--formants',nargs='+',choices=FORMANTS,default=list(FORMANTS))
    parser.add_argument('--block',type=int,default=256)
    parser.add_argument('--workers',type=int,default=3)
    r=run(parser.parse_args())
    print(json.dumps({k:r[k] for k in ('conditions','dsp_renders','derived_renders','exact_duration_renders')},indent=2))

if __name__=='__main__': main()
