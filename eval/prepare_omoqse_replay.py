#!/usr/bin/env python3
"""Freeze the received TSMDB test subset for a non-independent CNN replay."""
import argparse
import csv
from pathlib import Path
import shutil

import omoqse_replay as replay

INPUTS = {'test': 'fe7aa424d7bbf9c6145633c083083401641cabe3fb775839764b7282c759528d',
          'ref': 'd7930be5a56fb8aa5ef919f123f624d698be71c4b5810f6e2eb07008637a35f9',
          'scores': '423db29274b79a78a51a842b864a8cf3084b269d21d332edf8b1445de2eefaf6'}


def prepare(ref: Path, test: Path, scores: Path, weights: Path, author: Path, output: Path) -> dict:
    specs = {'ref': ref, 'test': test, 'scores': scores, 'weights': weights, 'author': author}
    hashes = INPUTS | {'weights': replay.WEIGHTS_SHA, 'author': replay.AUTHOR_SHA}
    for key, path in specs.items():
        replay.require(replay.contract.fingerprint(path) == hashes[key], f'unrecognized {key}')
    output.mkdir(parents=True, exist_ok=False)
    imported = replay.dataset.import_dataset(ref, test, scores, output)
    with scores.open(newline='', encoding='utf-8') as stream:
        labels = list(csv.DictReader(stream))
    rows = replay.dataset.read_manifest(imported.manifest_csv)
    for row in rows:
        exact = [r for r in labels if r['test_name'] == row['processed_name']]
        replay.require(len(exact) == 1, 'ambiguous score row')
        label = exact[0]
        replay.require(label['ref_name'] == row['reference_name'] and
                       abs(float(label['MeanOS']) - float(row['mos'])) < 1e-10, 'score/ref mismatch')
        row.update(source_id=label['ref_name'], engine_id=label['method'], category='unannotated',
                   pitch_semitones='0', formant='off', dataset_TSM=label['TSM'],
                   MeanOS_RAW=label['MeanOS_RAW'])
        for prefix in ('reference', 'processed'):
            row[prefix + '_sha256'] = replay.contract.fingerprint(output / row[prefix + '_path'])
    replay.dataset.write_csv(output / 'replay_manifest.csv', rows)
    assets = output / 'assets'
    assets.mkdir()
    shutil.copyfile(weights, assets / 'OMOQSE_CNN.pth')
    shutil.copyfile(author, assets / 'Eval_OMOQ_CNN.py')
    def spec(name):
        return {'path': name, 'sha256': replay.contract.fingerprint(output / name)}
    plan = dict(schema=replay.SCHEMA, profile=replay.PROFILE, purpose='replication_only',
                kind='tsmdb_test_replay', runtime=replay.VERSIONS, source_sha256=replay.source_hashes(),
                seed=replay.SEED, crops=replay.CROPS, expected_rows=240,
                protocol_commits=['72a2942362dd5ea332ec597c4ecdeea4dcedc7c7',
                                  '9a298cf4d5ce32a0c281b135363a9099c324e748'],
                scope=dict(task='tsm', formant='off', pitch_semitones=0, channels=1,
                           sample_rates=[44100], ratio_range=[0.5, 4.5]),
                manifest=spec('replay_manifest.csv'),
                artifacts=dict(weights=spec('assets/OMOQSE_CNN.pth'),
                               author_source=spec('assets/Eval_OMOQ_CNN.py')),
                original_inputs_sha256=hashes, preparation_script_sha256=replay.contract.fingerprint(Path(__file__)))
    replay.json_write(output / 'plan.json', plan)
    (output / 'PLAN_SHA256.txt').write_text(replay.contract.fingerprint(output / 'plan.json') + '\n')
    return plan


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('ref', 'test', 'scores', 'weights', 'author', 'output'):
        p.add_argument('--' + name, type=Path, required=True)
    prepare(**vars(p.parse_args()))
