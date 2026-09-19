"""Controls for a real, externally supplied CNN. Missing model assets fail, not skip."""
import copy
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

import numpy as np
import soundfile as sf

sys.path.insert(0, str(Path(__file__).resolve().parent))
import omoqse_replay as r


class ReplayTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.author = Path(os.environ['OMOQSE_AUTHOR_SOURCE'])
        cls.weights = Path(os.environ['OMOQSE_CNN_WEIGHTS'])
        cls.model = r.ReplayModel(cls.author, cls.weights)

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def fixture(self):
        import shutil
        for src, name in ((self.author, 'author.py'), (self.weights, 'weights.pth')):
            shutil.copyfile(src, self.root / name)
        x = (0.2 * np.sin(2 * np.pi * 223 * np.arange(44100) / 44100)).astype(np.float32)
        for name in ('ref.wav', 'out.wav'):
            sf.write(self.root / name, x, 44100, subtype='FLOAT')
        row = dict(item_id='fixture1', source_id='generated223', engine_id='analytic_not_engine',
                   reference_path='ref.wav', processed_path='out.wav', category='synthetic',
                   method='generated', ratio=1, mos=3, pitch_semitones=0, formant='off')
        for prefix, name in (('reference', 'ref.wav'), ('processed', 'out.wav')):
            row.update({prefix+'_sha256': r.contract.fingerprint(self.root/name), prefix+'_frames': 44100,
                        prefix+'_samplerate': 44100, prefix+'_channels': 1})
        r.dataset.write_csv(self.root / 'manifest.csv', [row])
        def spec(name):
            return {'path': name, 'sha256': r.contract.fingerprint(self.root / name)}
        plan = dict(schema=r.SCHEMA, profile=r.PROFILE, purpose='replication_only',
             kind='synthetic_calibration', runtime=r.VERSIONS, source_sha256=r.source_hashes(),
             seed=r.SEED, crops=r.CROPS, expected_rows=1,
             scope=dict(task='tsm', formant='off', pitch_semitones=0, channels=1,
                        sample_rates=[44100], ratio_range=[0.5, 4.5]),
             manifest=spec('manifest.csv'), artifacts=dict(weights=spec('weights.pth'),
                                                         author_source=spec('author.py')))
        return plan

    def run_plan(self, plan, name='result'):
        p = self.root / 'plan.json'
        r.json_write(p, plan)
        return r.run(p, r.contract.fingerprint(p), self.root / name)

    def test_real_checkpoint_and_author_forward(self):
        import torch
        f = np.random.RandomState(4).normal(size=(2, 128, 53)).astype(np.float32)
        values = self.model.predict(f, [0]*16)
        with torch.inference_mode():
            direct = float(self.model.net(torch.from_numpy(f[None]), 0).item()) * 4 + 1
        self.assertEqual(values, [direct] * 16)
        self.assertTrue(1 <= direct <= 5)
        self.assertGreater(self.model.parameter_count, 100000)

    def test_runtime_lock(self):
        self.assertEqual(r.runtime(), r.VERSIONS)

    def test_prepare_matches_literal_author_loops(self):
        def original(x):
            x = np.divide(x, np.max(np.abs(x)))
            start = 0
            while np.sum(x[start:start+3] < 0.0061) and start+3 < x.shape[0]:
                start += 1
            end = x.shape[0]
            while np.sum(x[end:end+3] < 0.0061) and end+3 > 0:
                end -= 1
            return x[start:end]
        fixtures = [np.array([-1., -.5, -.1]), np.ones(4096), -np.ones(4096),
                    np.r_[np.zeros(23), [-.4, -.3, .2, .3, .4], np.zeros(50)],
                    np.random.RandomState(8).normal(size=10000)]
        for x in fixtures:
            x = x.astype(np.float32)
            actual, info = r.prepare_audio(x)
            np.testing.assert_array_equal(actual, original(x))
            self.assertEqual(info['trailing_removed'], 0)

    def test_feature_explicit_profile_equivalence(self):
        import librosa
        x = np.sin(2*np.pi*223*np.arange(10000)/44100).astype(np.float32)
        f, info = r.features(x, 44100)
        y, _ = r.prepare_audio(x)
        mfcc = librosa.feature.mfcc(y=y, sr=44100, n_mfcc=128, pad_mode='reflect')
        delta = librosa.feature.delta(mfcc, width=9, order=1)
        np.testing.assert_array_equal(f, np.stack((mfcc, delta)))
        self.assertEqual(info['feature_shape'], list(f.shape))

    def test_crop_boundaries_and_padding(self):
        sha = 'f'*64
        for length in (1, 52, 53, 54, 200):
            starts = r.crop_starts(length, sha)
            self.assertEqual(starts, r.crop_starts(length, sha))
            self.assertEqual(len(starts), 16)
            if length <= 54:
                self.assertEqual(starts, [0]*16)
            else:
                self.assertLess(max(starts), length-53)
            feature = np.ones((2, 128, length), dtype=np.float32)
            crop = r.crop_tensor(feature, starts[0])
            self.assertEqual(crop.shape, (1, 2, 128, 53))
            if length < 53:
                self.assertTrue((crop[..., :53-length] == 0).all())
                self.assertTrue((crop[..., 53-length:] == 1).all())

    def test_invalid_audio_and_scope(self):
        for x in (np.zeros(44100), np.array([]), np.ones((44100, 2)),
                  np.r_[np.nan, np.ones(5000)], -np.ones(5000)):
            with self.subTest(shape=x.shape), self.assertRaises(ValueError):
                r.features(x, 44100)
        with self.assertRaises(ValueError):
            r.features(np.ones(10000), 48000)

    def test_no_global_rng_pollution(self):
        np.random.seed(77)
        before = np.random.get_state()
        r.crop_starts(100, 'a'*64)
        after = np.random.get_state()
        np.testing.assert_array_equal(before[1], after[1])
        self.assertEqual(before[2:], after[2:])

    def test_changed_model_or_source_refused(self):
        for role in ('weights', 'author'):
            p = self.root / 'bad'
            p.write_bytes(b'not a checkpoint or trusted source')
            with self.assertRaises(ValueError):
                r.ReplayModel(p if role == 'author' else self.author,
                              p if role == 'weights' else self.weights)

    def test_complete_replay_and_exact_repeat(self):
        plan = self.fixture()
        first, second = self.run_plan(plan, 'one'), self.run_plan(plan, 'two')
        self.assertEqual(first['status'], 'complete_replay_not_independent', first['errors'])
        self.assertEqual(first['rows'], second['rows'])
        self.assertFalse(first['independence']['passed'])
        self.assertFalse(first['independent_validation'])
        self.assertIsNone(first['quality_selection'])
        self.assertIsNone(first['scores'])
        self.assertTrue(first['model_inference_performed'])
        self.assertEqual(first['replication_diagnostics']['overall']['n'], 1)

    def test_bad_plans_fail_with_receipts(self):
        plan = self.fixture()
        cases = [dict(purpose='independent'), dict(expected_rows=0), dict(seed=1),
                 dict(crops=1), dict(kind='unknown'), dict(profile='unknown'),
                 dict(artifacts=[]), dict(runtime={}), dict(source_sha256={}),
                 dict(kind='tsmdb_test_replay')]
        for i, patch in enumerate(cases):
            report = self.run_plan(plan | patch, f'bad{i}')
            self.assertEqual(report['status'], 'blocked')
            self.assertIsNone(report['replication_diagnostics'])
            self.assertTrue((self.root/f'bad{i}'/'report.json').exists())
        p = self.root / 'plan.json'
        report = r.run(p, '0'*64, self.root/'badsha')
        self.assertEqual(report['status'], 'blocked')

    def test_bad_manifest_and_audio_refused(self):
        plan = self.fixture()
        original = r.dataset.read_manifest(self.root/'manifest.csv')
        cases = [original*2, [original[0] | {'mos':'NaN'}],
                 [original[0] | {'pitch_semitones':'1'}],
                 [original[0] | {'formant':'harmonic'}],
                 [original[0] | {'ratio':'0'}],
                 [original[0] | {'processed_path':'../missing.wav'}]]
        for i, rows in enumerate(cases):
            r.dataset.write_csv(self.root/'manifest.csv', rows)
            plan['manifest']['sha256'] = r.contract.fingerprint(self.root/'manifest.csv')
            report = self.run_plan(plan, f'manifest{i}')
            self.assertEqual(report['status'], 'blocked')
        r.dataset.write_csv(self.root/'manifest.csv', original)
        plan['manifest']['sha256'] = r.contract.fingerprint(self.root/'manifest.csv')
        sf.write(self.root/'out.wav', np.zeros(44100), 44100, subtype='FLOAT')
        self.assertEqual(self.run_plan(plan, 'changed')['status'], 'blocked')

    def test_partial_inference_keeps_failures_without_scores(self):
        plan = self.fixture()
        with mock.patch.object(r.ReplayModel, 'predict', side_effect=RuntimeError('injected failure')):
            report = self.run_plan(plan)
        self.assertEqual(report['status'], 'blocked')
        self.assertIsNone(report['replication_diagnostics'])
        self.assertEqual(report['rows'][0]['status'], 'failed')
        self.assertIn('injected failure', report['rows'][0]['error'])

    def test_mutation_during_inference_blocks_scores(self):
        plan = self.fixture()
        original = r.ReplayModel.predict
        def mutate(model, feature, starts):
            value = original(model, feature, starts)
            (self.root/'ref.wav').write_bytes(b'changed')
            return value
        with mock.patch.object(r.ReplayModel, 'predict', new=mutate):
            report = self.run_plan(plan)
        self.assertEqual(report['status'], 'blocked')
        self.assertIsNone(report['replication_diagnostics'])

    def test_invalid_model_return_keeps_failure_receipt(self):
        plan = self.fixture()
        for i, values in enumerate(([float('nan')]*16, [3.0]*15, [float('inf')]*16)):
            with mock.patch.object(r.ReplayModel, 'predict', return_value=values):
                report = self.run_plan(plan, f'invalid_return{i}')
            self.assertEqual(report['status'], 'blocked')
            self.assertIsNone(report['replication_diagnostics'])
            self.assertEqual(report['rows'][0]['status'], 'failed')
            self.assertTrue((self.root/f'invalid_return{i}'/'report.json').exists())

    def test_never_overwrite_existing_output(self):
        plan = self.fixture()
        out = self.root/'existing'
        out.mkdir()
        (out/'keep.txt').write_text('keep')
        with self.assertRaises(FileExistsError):
            self.run_plan(plan, 'existing')
        self.assertEqual((out/'keep.txt').read_text(), 'keep')


if __name__ == '__main__':
    unittest.main()
