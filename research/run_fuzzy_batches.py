#!/usr/bin/env python3
"""Resumable, locked execution of the fingerprinted fuzzy corpus grid (Linux).

A .incomplete directory is NOT a result. Completed cells are revalidated before
reuse; all render hashes are verified before atomic final publication. Missing or
corrupt cells are regenerated only under the explicit --resume authorization.
"""
from __future__ import annotations
import argparse,concurrent.futures as cf,csv,fcntl,json,os,shutil,sys,time
from pathlib import Path
import eval_fuzzy_corpus as e


def atomic_json(path: Path, value) -> None:
    temporary=path.with_suffix(path.suffix+'.pending')
    with temporary.open('w',encoding='utf-8') as f:
        # Flush/rename is atomic publication, not a power-loss durability promise.
        # Recovery revalidates every checkpoint and WAV hash.
        json.dump(value,f,indent=2,allow_nan=False);f.write('\n');f.flush()
    temporary.replace(path)


def checked_cell(staging: Path, rows: list[dict], cell: dict, formants: list[str]) -> None:
    e.validate(rows,[cell],formants)
    for row in rows:
        expected=f'renders/{cell["condition_id"]}/'+(e.BASELINE+'.wav' if row['profile']==e.BASELINE else row['profile']+'_'+row['formant']+'.wav')
        if row['render_path']!=expected or e.fingerprint(e.inside(staging,expected))!=row['render_sha256']:
            raise ValueError('checkpoint render path/hash mismatch')


def run(a: argparse.Namespace) -> dict:
    if not e.re.fullmatch('[0-9a-f]{40}',a.source_commit) or a.workers<1 or not 1<=a.block<=16384 or a.batch_limit<0:
        raise ValueError('invalid commit/workers/block/batch limit')
    if not a.formants or len(set(a.formants))!=len(a.formants) or set(a.formants)-set(e.FORMANTS):
        raise ValueError('invalid formants')
    output=a.output.resolve();stage=output.with_name(output.name+'.incomplete')
    if output.exists():raise ValueError('final output already exists')
    existed=stage.exists()
    if existed and not a.resume:raise ValueError('incomplete output exists; explicit --resume required')
    if stage.is_symlink():raise ValueError('staging directory may not be a symlink')
    stage.mkdir(parents=True,exist_ok=existed)
    with (stage/'LOCK').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        refs,tests,pv,multi=[p.resolve(strict=True) for p in (a.ref_dir,a.test_dir,a.pv_cli,a.multires_cli)]
        sources,processed,cells=e.plan(refs,tests,a.catalog)
        identity=dict(schema=e.SCHEMA,source_commit=a.source_commit,sources=sources,processed=processed,cells=cells,
            formants=a.formants,profiles=list(e.PROFILES),block=a.block,
            executables={'pv':e.fingerprint(pv),'multires':e.fingerprint(multi)},catalog_sha256=e.fingerprint(a.catalog),
            implementation_sha256={p.name:e.fingerprint(p) for p in (Path(e.__file__),Path(__file__))})
        manifest=stage/'INCOMPLETE.json'
        if existed:
            if not manifest.exists() or json.loads(manifest.read_text())!=identity:
                raise ValueError('resume identity differs: inputs/code/commit/config must match')
        else:atomic_json(manifest,identity)
        checkpoints=stage/'checkpoints';checkpoints.mkdir(exist_ok=True)
        ready={};pending=[];recovered=[]
        for cell in cells:
            checkpoint=checkpoints/(cell['condition_id']+'.json')
            if checkpoint.exists():
                try:
                    rows=json.loads(checkpoint.read_text());checked_cell(stage,rows,cell,a.formants)
                    ready[cell['condition_id']]=rows;continue
                except (ValueError,OSError,KeyError,TypeError) as error:
                    recovered.append(dict(condition_id=cell['condition_id'],error=str(error)))
                    checkpoint.unlink()
            folder=stage/'renders'/cell['condition_id']
            if folder.is_symlink():raise ValueError('render directory may not be a symlink')
            if folder.exists():shutil.rmtree(folder)
            pending.append(cell)
        selected=pending[:a.batch_limit] if a.batch_limit else pending
        jobs=[(c,refs,tests,pv,multi,stage,a.formants,a.block) for c in selected]
        try:
            with cf.ProcessPoolExecutor(max_workers=a.workers) as pool:
                for cell,rows in zip(selected,pool.map(e.job,jobs)):
                    checked_cell(stage,rows,cell,a.formants)
                    atomic_json(checkpoints/(cell['condition_id']+'.json'),rows)
                    ready[cell['condition_id']]=rows
                    print(f'verified cells {len(ready)}/{len(cells)}',flush=True)
        except Exception as error:
            with (stage/'attempts.jsonl').open('a') as f:f.write(json.dumps(dict(time=time.time(),error=str(error),recovered=recovered))+'\n')
            raise
        with (stage/'attempts.jsonl').open('a') as f:f.write(json.dumps(dict(time=time.time(),completed=len(ready),recovered=recovered))+'\n')
        if len(ready)!=len(cells):return dict(complete=False,verified_conditions=len(ready),expected_conditions=len(cells))
        rows=[r for c in cells for r in ready[c['condition_id']]]
        for c in cells:checked_cell(stage,ready[c['condition_id']],c,a.formants)
        expected={r['render_path'] for r in rows}
        actual={p.relative_to(stage).as_posix() for p in (stage/'renders').rglob('*') if p.is_file()}
        if expected!=actual:raise ValueError('unexpected or missing final render files')
        if identity['executables']!={'pv':e.fingerprint(pv),'multires':e.fingerprint(multi)} or identity['catalog_sha256']!=e.fingerprint(a.catalog):
            raise ValueError('binary/catalog changed during batch')
        if any(e.fingerprint(e.inside(refs,s['reference_name']))!=s['reference_sha256'] for s in sources) or any(
                e.fingerprint(e.inside(tests,p['name']))!=p['sha256'] for p in processed):raise ValueError('input changed during batch')
        with (stage/'metrics.csv').open('w',newline='',encoding='utf-8') as f:
            w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
        result=dict(**identity,**e.summarize(rows,cells,a.formants),complete=True,
            metrics_sha256=e.fingerprint(stage/'metrics.csv'),listening_status='not_listened',mos_transfer=False,
            automatic_promotion=False,versions=dict(numpy=e.np.__version__,scipy=e.scipy.__version__,soundfile=e.sf.__version__),
            interpretation='Causal adaptation, not full FPV. Derived Elastique = supplied TSM + Fourier resampling, '
            'not native pitch output. Exact/derived and target/stress remain separate. No perceptual score. '
            'Catalog categories preserved; review categories are the existing filename map. Raw sample peaks, not true peaks.')
        atomic_json(stage/'summary.json',result)
        manifest.rename(stage/'INPUT_MANIFEST.json')
        stage.rename(output)
        return result


def main() -> None:
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('pv-cli','multires-cli','ref-dir','test-dir','catalog','output'):p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--source-commit',required=True);p.add_argument('--formants',nargs='+',choices=e.FORMANTS,default=list(e.FORMANTS))
    p.add_argument('--block',type=int,default=256);p.add_argument('--workers',type=int,default=3)
    p.add_argument('--resume',action='store_true');p.add_argument('--batch-limit',type=int,default=0)
    r=run(p.parse_args());print(json.dumps({k:v for k,v in r.items() if k in ('complete','verified_conditions','expected_conditions','dsp_renders','derived_renders')},indent=2))
    raise SystemExit(0 if r['complete'] else 3)

if __name__=='__main__':main()
