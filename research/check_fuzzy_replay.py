#!/usr/bin/env python3
"""Re-render every fuzzy cell against a fingerprinted evaluation (no tolerance).

This validates a behavior-preserving optimization, not audio quality. Original
WAVs are immutable; replay WAVs are temporary. A mismatch is retained in the
report and produces a nonzero CLI status. The report never re-labels provenance.
"""
from __future__ import annotations
import argparse
import concurrent.futures as cf
import json
import re
import subprocess
import tempfile
from pathlib import Path
import eval_fuzzy_corpus as e
from make_fuzzy_listening import read_evaluation


def check_render(job: tuple) -> dict:
    row, evaluation, references, cli, block = job
    original = e.inside(evaluation, row['render_path'])
    source = e.inside(references, row['reference_name'])
    if e.fingerprint(original) != row['render_sha256'] or e.fingerprint(source) != row['reference_sha256']:
        raise ValueError('original/source fingerprint mismatch')
    with tempfile.TemporaryDirectory(prefix='fuzzy-replay-') as tmp:
        dest = Path(tmp)/'render.wav'
        run = subprocess.run(e.command(cli, cli, source, dest, row['profile'], row['formant'],
                                       row['control_ratio'], block), capture_output=True, text=True, timeout=120)
        if run.returncode:
            raise RuntimeError(f'replay renderer failed: {run.stderr}')
        digest = e.fingerprint(dest)
    return dict(condition_id=row['condition_id'], profile=row['profile'], formant=row['formant'],
                original_sha256=row['render_sha256'], replay_sha256=digest,
                identical=digest == row['render_sha256'])


def run(evaluation: Path, references: Path, cli: Path, commit: str, workers: int,
        block: int | None = None) -> dict:
    if not re.fullmatch('[0-9a-f]{40}', commit) or workers < 1:
        raise ValueError('full commit SHA and positive workers required')
    summary, rows = read_evaluation(evaluation)
    block = summary['block'] if block is None else block
    if not 1 <= block <= 16384:
        raise ValueError('invalid block size')
    cli = cli.resolve(strict=True)
    digest = e.fingerprint(cli)
    selected = [r for r in rows if r['profile'] in ('fuzzy', 'fuzzy-noise')]
    if not selected:
        raise ValueError('no fuzzy renders to replay')
    jobs = [(r, evaluation, references, cli, block) for r in selected]
    with cf.ProcessPoolExecutor(max_workers=workers) as pool:
        checked = []
        for i, row in enumerate(pool.map(check_render, jobs), 1):
            checked.append(row)
            if i % 100 == 0:
                print(f'replayed {i}/{len(selected)}', flush=True)
    if e.fingerprint(cli) != digest:
        raise ValueError('replay executable changed')
    return dict(schema='boiled-egg.fuzzy-replay.v1', evaluation_sha256=e.fingerprint(evaluation/'summary.json'),
                original_source_commit=summary['source_commit'], replay_source_commit=commit,
                replay_cli_sha256=digest, original_block=summary['block'], replay_block=block,
                renders=len(checked), byte_identical=sum(r['identical'] for r in checked),
                passed=all(r['identical'] for r in checked), rows=checked)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for key in ('evaluation', 'ref-dir', 'cli', 'output'):
        p.add_argument('--'+key, type=Path, required=True)
    p.add_argument('--source-commit', required=True)
    p.add_argument('--workers', type=int, default=2)
    p.add_argument('--block', type=int)
    a = p.parse_args()
    if a.output.exists():
        raise ValueError('output already exists')
    result = run(a.evaluation, a.ref_dir, a.cli, a.source_commit, a.workers, a.block)
    a.output.parent.mkdir(parents=True, exist_ok=True)
    with a.output.open('x', encoding='utf-8') as f:
        json.dump(result, f, indent=2, allow_nan=False); f.write('\n')
    print(f'{result["byte_identical"]}/{result["renders"]} byte-identical WAVs')
    raise SystemExit(not result['passed'])
