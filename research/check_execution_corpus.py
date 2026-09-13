#!/usr/bin/env python3
"""Replay exact held-out pitches through scalar baseline and scheduled SIMD.

Complete grid, exact duration and complete-WAV identity are checked. The CSV
also measures unchanged objective diagnostics; no audio or MOS is redistributed.
"""
from __future__ import annotations
import argparse
import concurrent.futures as cf
import csv
import json
import subprocess
import tempfile
from pathlib import Path
import numpy as np
import eval_fuzzy_corpus as e


def job(args):
    record, refs, old, new = args
    src=e.inside(refs,record['reference_name'])
    if e.fingerprint(src)!=record['reference_sha256']:raise ValueError('source changed')
    source,rate=e.checked_audio(src);rows=[]
    with tempfile.TemporaryDirectory(prefix='execution-replay-') as tmp:
        oldwav,newwav=Path(tmp)/'old.wav',Path(tmp)/'new.wav'
        for shift in e.PITCHES:
            ratio=float(np.float32(2**(shift/12)))
            for mode in e.FORMANTS:
                for profile in e.PROFILES:
                    for build,path,block,flags in ((old,oldwav,256,[]),(new,newwav,32,['--execution','scheduled','--simd','on'])):
                        cmd=e.command(build/'boiled_egg_pv_rt_cli',build/'boiled_egg_multires_rt_cli',src,path,profile,mode,ratio,block)
                        cmd+=['--timing','centered','--rate-policy','scaled',*flags]
                        proc=subprocess.run(cmd,capture_output=True,text=True,timeout=120)
                        if proc.returncode:raise RuntimeError(f'{profile}/{mode}/{shift}: {proc.stderr}')
                    a,sra=e.checked_audio(oldwav);b,srb=e.checked_audio(newwav)
                    if sra!=rate or srb!=rate or a.shape!=source.shape or b.shape!=source.shape:raise ValueError('metadata mismatch')
                    ah,bh=e.fingerprint(oldwav),e.fingerprint(newwav)
                    rows.append(dict(source=record['reference_name'],reference_sha256=record['reference_sha256'],shift=shift,profile=profile,formant=mode,
                        rate=rate,frames=len(source),channels=source.shape[1],baseline_sha256=ah,candidate_sha256=bh,
                        byte_identical=ah==bh,max_sample_difference=float(np.max(np.abs(a-b))),**e.measure(source,b,rate)))
    if e.fingerprint(src)!=record['reference_sha256']:raise ValueError('source changed during rendering')
    return rows


def run(args):
    if args.workers<1:raise ValueError('positive workers required')
    sources=e.preflight(args.ref_dir,args.catalog)
    old,new=args.baseline.resolve(strict=True),args.candidate.resolve(strict=True)
    binaries={f'{label}/{name}':e.fingerprint(build/name) for label,build in [('baseline',old),('candidate',new)]
              for name in ('boiled_egg_pv_rt_cli','boiled_egg_multires_rt_cli')}
    catalog_hash=e.fingerprint(args.catalog);output=args.output.resolve()
    if output.exists():raise ValueError('output must not exist')
    output.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.execution-corpus-',dir=output.parent) as tmp:
        staging=Path(tmp)/'report';staging.mkdir();rows=[]
        with cf.ProcessPoolExecutor(max_workers=args.workers) as pool:
            for i,result in enumerate(pool.map(job,[(s,args.ref_dir,old,new) for s in sources]),1):
                rows+=result;print(f'source {i}/{len(sources)}; pairs {len(rows)}',flush=True)
        expected={(s['reference_name'],st,f,p) for s in sources for st in e.PITCHES for f in e.FORMANTS for p in e.PROFILES}
        actual={(r['source'],r['shift'],r['formant'],r['profile']) for r in rows}
        if len(actual)!=len(rows) or actual!=expected:raise ValueError('incomplete grid')
        for key,digest in binaries.items():
            label,name=key.split('/');build=old if label=='baseline' else new
            if e.fingerprint(build/name)!=digest:raise ValueError('binary changed')
        if e.fingerprint(args.catalog)!=catalog_hash:raise ValueError('catalog changed')
        with (staging/'comparisons.csv').open('w',newline='') as f:
            w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
        summary=dict(schema='boiled-egg.execution-corpus.v1',sources=sources,pairs=len(rows),rendered_wavs=2*len(rows),
            byte_identical=sum(r['byte_identical'] for r in rows),passed=all(r['byte_identical'] for r in rows),
            baseline_block=256,candidate_block=32,timing='centered',rate_policy='scaled',binary_sha256=binaries,
            catalog_sha256=catalog_hash,script_sha256=e.fingerprint(Path(__file__)),
            comparisons_sha256=e.fingerprint(staging/'comparisons.csv'),listening_status='not_listened',mos_transfer=False,
            meaning='Same-toolchain complete-file equivalence at exact target pitches, not a perceptual ranking or native Elastique comparison.')
        (staging/'summary.json').write_text(json.dumps(summary,indent=2,allow_nan=False)+'\n');staging.rename(output)
    return summary

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('ref-dir','catalog','baseline','candidate','output'):p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--workers',type=int,default=2)
    r=run(p.parse_args());print(f'{r["byte_identical"]}/{r["pairs"]} byte-identical');raise SystemExit(not r['passed'])
