#!/usr/bin/env python3
"""Frozen OMOQSE-CNN compatibility replay, never independent MOS qualification.

External author source/weights are hash-pinned, not redistributed. This profile
changes entropy-driven crop selection and fixes modern feature defaults. It is
not bit-exact historical reproduction. See OMOQSE_REPLAY_PROTOCOL_2026-09-20.md.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import io
import json
import platform
from pathlib import Path
import sys
import time

import numpy as np
import soundfile as sf

import fixed_predictor as audit
import comparison_contract as contract
import tsm_dataset as dataset

SCHEMA = 'boiled-egg.omoqse-replay.v1'
PROFILE = 'omoqse-cnn-modern-reflect-seeded-v1'
WEIGHTS_SHA = '261336ab331254259010566ef7b9e8d03a0e65156a2381f6b6605d7d3faa659a'
AUTHOR_SHA = '154816c4752cba2e3e0cafd6f45fb0d7eb337d30ab5bb2258dbcfa4b47b876ad'
VERSIONS = {'python': '3.13.5', 'torch': '2.10.0+cpu', 'librosa': '0.11.0',
            'numpy': '2.3.5', 'scipy': '1.17.0', 'soundfile': '0.13.1'}
SEED, CROPS, FRAMES = 20260920, 16, 53
require = audit.require


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def json_write(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + '\n', encoding='utf-8')


def runtime() -> dict:
    import librosa
    import scipy
    import torch
    return dict(python=platform.python_version(), torch=torch.__version__,
                librosa=librosa.__version__, numpy=np.__version__,
                scipy=scipy.__version__, soundfile=sf.__version__)


def prepare_audio(audio: np.ndarray) -> tuple[np.ndarray, dict]:
    """Mono only. Preserve author's signed leading trim and no-op trailing trim."""
    x = np.asarray(audio, dtype=np.float32)
    require(x.ndim == 1 and len(x) >= 3, 'unsupported mono/empty audio')
    require(bool(np.isfinite(x).all()), 'nonfinite audio')
    rms = float(np.sqrt(np.mean(x.astype(np.float64) ** 2)))
    require(rms > 1e-8, 'silent/zero audio')
    peak = float(np.max(np.abs(x)))
    x = x / peak
    # Original loop advances while ANY of the next3 signed values is <0.0061.
    # It stops at n-3 if no three consecutive positives exist. End starts at n,
    # making the original trailing slice empty and its trailing loop a no-op.
    below = x < 0.0061
    candidates = np.flatnonzero(~below[:-2] & ~below[1:-1] & ~below[2:])
    start = int(candidates[0]) if len(candidates) else len(x) - 3
    return x[start:], dict(input_frames=len(x), leading_removed=start, trailing_removed=0,
                          original_peak=peak, original_rms=rms)


def features(audio: np.ndarray, rate: int) -> tuple[np.ndarray, dict]:
    import librosa
    require(type(rate) is int and rate == 44100, 'profile requires44100 Hz; no resampling')
    x, receipt = prepare_audio(audio)
    require(len(x) >= 4096, 'insufficient post-trim samples for fixed delta profile')
    mel = librosa.feature.melspectrogram(y=x, sr=rate, n_fft=2048, hop_length=512,
             win_length=2048, window='hann', center=True, pad_mode='reflect', power=2.0,
             n_mels=128, fmin=0.0, fmax=rate / 2, htk=False, norm='slaney')
    db = librosa.power_to_db(mel, ref=1.0, amin=1e-10, top_db=80.0)
    mfcc = librosa.feature.mfcc(S=db, n_mfcc=128, dct_type=2, norm='ortho', lifter=0)
    delta = librosa.feature.delta(mfcc, width=9, order=1, axis=-1, mode='interp')
    result = np.ascontiguousarray(np.stack((mfcc, delta)), dtype=np.float32)
    require(bool(np.isfinite(result).all()), 'nonfinite features')
    receipt.update(feature_shape=list(result.shape), feature_sha256=digest(result.tobytes()))
    return result, receipt


def crop_starts(length: int, input_sha: str) -> list[int]:
    require(type(length) is int and length > 0, 'empty features')
    audit.sha(input_sha)
    seed = int.from_bytes(hashlib.sha256(f'{SEED}:{input_sha}'.encode()).digest()[:4], 'big')
    rng = np.random.RandomState(seed)
    # Same exclusive bound as author's randint; last possible start is excluded.
    return rng.randint(0, length - FRAMES, CROPS).tolist() if length > FRAMES else [0] * CROPS


def crop_tensor(feature: np.ndarray, start: int) -> np.ndarray:
    require(feature.ndim == 3 and feature.shape[:2] == (2, 128), 'wrong feature shape')
    length = feature.shape[2]
    require(type(start) is int and length > 0 and start >= 0, 'invalid crop')
    require(start <= max(0, length - FRAMES), 'crop outside feature bounds')
    if length < FRAMES:
        result = np.pad(feature, ((0, 0), (0, 0), (FRAMES - length, 0)))
    else:
        result = feature[:, :, start:start + FRAMES]
    return np.ascontiguousarray(result[None], dtype=np.float32)


class ReplayModel:
    """Execute only the pinned external Net definition, with its exact checkpoint."""
    def __init__(self, author_source: Path, weights: Path):
        import torch
        import torch.nn as nn
        import torch.nn.functional as F
        source = author_source.read_bytes()
        payload = weights.read_bytes()
        require(digest(source) == AUTHOR_SHA, 'unrecognized/changed author source')
        require(digest(payload) == WEIGHTS_SHA, 'unrecognized/changed weights')
        require(torch.__version__ == VERSIONS['torch'], 'unlocked Torch runtime')
        torch.set_num_threads(1)
        torch.use_deterministic_algorithms(True)
        tree = ast.parse(source.decode('utf-8'))
        nodes = [node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == 'Net']
        require(len(nodes) == 1, 'missing/duplicate author Net')
        module = ast.fix_missing_locations(ast.Module(body=nodes, type_ignores=[]))
        namespace = dict(torch=torch, nn=nn, F=F, device=torch.device('cpu'), dropout_per=0.0)
        exec(compile(module, str(author_source), 'exec'), namespace)
        self.net = namespace['Net']().cpu()
        state = torch.load(io.BytesIO(payload), map_location='cpu', weights_only=True)
        require(isinstance(state, dict) and bool(state), 'invalid state dictionary')
        require(all(isinstance(v, torch.Tensor) and bool(torch.isfinite(v).all()) for v in state.values()),
                'invalid/nonfinite checkpoint tensor')
        self.net.load_state_dict(state, strict=True)
        self.net.eval()
        self.tensor_count = len(state)
        self.parameter_count = sum(v.numel() for v in self.net.parameters())

    def predict(self, feature: np.ndarray, starts: list[int]) -> list[float]:
        import torch
        require(len(starts) == CROPS, 'incomplete crop grid')
        result = []
        with torch.inference_mode():
            for start in starts:
                value = self.net(torch.from_numpy(crop_tensor(feature, start)), 0)
                require(tuple(value.shape) == (1, 1) and bool(torch.isfinite(value).all()),
                        'invalid inference result')
                result.append(float(value.item()) * 4.0 + 1.0)
        return result


def source_hashes() -> dict:
    return {Path(p).name: contract.fingerprint(Path(p)) for p in
            (__file__, audit.__file__, contract.__file__, dataset.__file__)}


def run(plan_path: Path, plan_sha: str, output: Path) -> dict:
    """No overwrite, no label-driven inference, no aggregate on a partial grid."""
    output.mkdir(parents=True, exist_ok=False)
    report = dict(schema=SCHEMA, profile=PROFILE, status='blocked', errors=[], rows=[],
                  scores=None, replication_diagnostics=None, quality_selection=None,
                  independent_validation=False, model_inference_performed=False,
                  plan_sha256=plan_sha, source_sha256=source_hashes())
    seen: dict[str, str] = {}
    started = time.monotonic()
    try:
        require(contract.fingerprint(plan_path) == audit.sha(plan_sha), 'plan hash mismatch')
        seen[str(plan_path.resolve())] = plan_sha
        plan = audit.load_json(plan_path)
        root = plan_path.parent
        require(plan['schema'] == SCHEMA and plan['profile'] == PROFILE, 'unsupported plan/profile')
        require(plan['purpose'] == 'replication_only', 'independent qualification is not supported')
        require(plan['runtime'] == VERSIONS and runtime() == VERSIONS, 'unlocked runtime')
        require(plan['source_sha256'] == source_hashes(), 'adapter/dependency code changed')
        require(plan['seed'] == SEED and plan['crops'] == CROPS, 'unlocked sampling')
        scope = audit.validate_scope(plan)
        require(scope['sample_rates'] == [44100], 'unsupported sample rate')
        kind = plan['kind']
        require(kind in {'tsmdb_test_replay', 'synthetic_calibration'}, 'unknown replay kind')
        report['label_origin'] = 'existing_MeanOS' if kind == 'tsmdb_test_replay' else 'synthetic_fixture'
        artifacts = plan['artifacts']
        require(isinstance(artifacts, dict) and set(artifacts) == {'weights', 'author_source'}, 'invalid artifacts')
        paths = {k: audit.checked_file(root, spec, seen) for k, spec in artifacts.items()}
        require(artifacts['weights']['sha256'] == WEIGHTS_SHA and
                artifacts['author_source']['sha256'] == AUTHOR_SHA, 'wrong model identity')
        manifest = audit.checked_file(root, plan['manifest'], seen)
        rows = audit.table(manifest, audit.EVAL_FIELDS)
        audit.index(rows)
        require(type(plan['expected_rows']) is int and len(rows) == plan['expected_rows'], 'incomplete grid')
        if kind == 'tsmdb_test_replay':
            require(len(rows) == 240 and len({r['source_id'] for r in rows}) == 20 and
                    len({r['engine_id'] for r in rows}) == 3, 'incorrect TSMDB test grid')
        for row in rows:
            for field in audit.IDENTITY | {'category'}:
                audit.text(row[field], field)
            require(1 <= audit.number(row['mos'], 'label') <= 5, 'label outside1..5')
            audit.validate_audio(root, row, scope, seen)
        # This frozen checkpoint has selection exposure. Unknown full history
        # and alias review are never turned into independence by relabeling rows.
        development = [{k: r[k] for k in audit.IDENTITY} | {'stage': 'selection'} for r in rows]
        report['independence'] = audit.audit_inventory(rows, development, 'incomplete', False)
        report['independence']['interpretation'] = ('Known test-selection exposure for TSMDB; '
              'synthetic controls conservatively denied qualification. Full training/alias inventory not verified.')
        model = ReplayModel(paths['author_source'], paths['weights'])
        report['model'] = dict(tensors=model.tensor_count, parameters=model.parameter_count,
                              weights_sha256=WEIGHTS_SHA, author_sha256=AUTHOR_SHA)
        for row in rows:
            receipt = {'item_id': row['item_id'], 'status': 'failed'}
            try:
                path = audit.inside(root, row['processed_path'])
                raw = path.read_bytes()
                require(digest(raw) == row['processed_sha256'], 'input changed before inference')
                audio, rate = sf.read(io.BytesIO(raw), dtype='float32', always_2d=False)
                feat, prep = features(audio, rate)
                starts = crop_starts(feat.shape[-1], digest(raw))
                values = model.predict(feat, starts)
                require(isinstance(values, list) and len(values) == CROPS, 'incomplete model return')
                values = [audit.number(v, 'model prediction') for v in values]
                require(all(1 <= v <= 5 for v in values), 'model return outside sigmoid scale')
                report['model_inference_performed'] = True
                receipt.update(status='ok', source_id=row['source_id'], engine_id=row['engine_id'],
                      category=row['category'], label=audit.number(row['mos'], 'label'),
                      prediction=float(np.mean(values)), processed_sha256=digest(raw),
                      ratio=audit.number(row['ratio'], 'ratio'), preprocessing=prep,
                      crop_starts=starts, crop_predictions=values)
            except Exception as exc:
                receipt['error'] = f'{type(exc).__name__}: {exc}'
            report['rows'].append(receipt)
            # Incremental evidence survives a later interrupt; never a scored subset.
            json_write(output / 'progress.json', report)
        require(all(r['status'] == 'ok' for r in report['rows']), 'one or more inference rows failed')
        for name, expected in seen.items():
            require(contract.fingerprint(Path(name)) == expected, 'evidence changed during inference')
        require(source_hashes() == report['source_sha256'], 'code changed during inference')
        report['replication_diagnostics'] = audit.score(report['rows'])
        baseline = [r | {'prediction': 3.0} for r in report['rows']]
        report['constant3_diagnostics'] = audit.score(baseline)
        report['status'] = 'complete_replay_not_independent'
        predictions = [{'item_id': r['item_id'], 'prediction': r['prediction'], 'status': 'ok'}
                       for r in report['rows']]
        dataset.write_csv(output / 'predictions.csv', predictions)
    except Exception as exc:
        report['status'] = 'blocked'
        report['errors'].append(f'{type(exc).__name__}: {exc}')
        report['replication_diagnostics'] = None
        report.pop('constant3_diagnostics', None)
    report['elapsed_seconds'] = time.monotonic() - started
    report['files_sha256'] = seen
    json_write(output / 'report.json', report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan', type=Path, required=True)
    parser.add_argument('--plan-sha256', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    try:
        result = run(args.plan, args.plan_sha256, args.output)
    except FileExistsError:
        print('output already exists; no files overwritten', file=sys.stderr)
        return 2
    print(json.dumps({k: result[k] for k in ('status', 'errors', 'independent_validation')}, ensure_ascii=False))
    return 0 if result['status'] == 'complete_replay_not_independent' else 2


if __name__ == '__main__':
    raise SystemExit(main())
