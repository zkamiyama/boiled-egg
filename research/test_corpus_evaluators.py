from __future__ import annotations
import hashlib
import math
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
import soundfile as sf
sys.path.insert(0, str(Path(__file__).resolve().parent))
import eval_multires_corpus as multi
import eval_hybrid_corpus as hybrid


def fixture(task='tsm', semitones=7.0, stem='fixture'):
    systems = (('elastique_tsm', 'general', 'transient', 'multires', 'wsola',
                'hpss_general', 'hpss_transient') if task == 'tsm' else
               ('derived_elastique', 'hpss_general', 'hpss_transient'))
    return [dict(task=task, stem=stem, category='solo', percent='150',
                 semitones=semitones, system=name, env=2 if i == 0 else 1.5,
                 onset=.5 if i == 0 else .6, peak=.9, duration_error_frames=0)
            for i, name in enumerate(systems)]


class CorpusEvaluatorsTest(unittest.TestCase):
    def test_fingerprint(self):
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/'file';path.write_bytes(b'abc')
            self.assertEqual(multi.fingerprint(path),hashlib.sha256(b'abc').hexdigest())

    def test_checked_audio(self):
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/'x.wav';sf.write(path,np.ones((300,2))*.1,44100,subtype='FLOAT')
            audio,rate=multi.checked_audio(path)
            self.assertEqual(audio.shape,(300,2));self.assertEqual(rate,44100)

    def test_nonfinite_and_empty_audio(self):
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/'x.wav'
            for x in (np.array([np.nan]),np.zeros((0,1))):
                sf.write(path,x,44100,subtype='FLOAT')
                with self.assertRaises(ValueError):multi.checked_audio(path)

    def test_empty_summaries(self):
        self.assertEqual(multi.summarize([]),{'conditions':0})
        self.assertEqual(hybrid.summarize([]),{})

    def test_direct_tsm_and_pitch_are_separate(self):
        result=hybrid.summarize(fixture()+fixture('pitch'))
        self.assertEqual(result['tsm_all']['multires']['conditions'],1)
        self.assertNotIn('multires',result['pitch_all'])
        self.assertAlmostEqual(result['tsm_all']['wsola']['env_delta'],-.5)
        self.assertAlmostEqual(result['pitch_all']['hpss_general']['onset_delta'],.1)

    def test_target_stress_separation(self):
        result=hybrid.summarize(fixture()+fixture(semitones=20,stem='stress'))
        self.assertEqual(result['tsm_target']['general']['conditions'],1)
        self.assertEqual(result['tsm_all']['general']['conditions'],2)

    def test_missing_pair_is_not_silently_dropped(self):
        with self.assertRaisesRegex(ValueError,'incomplete'):hybrid.summarize(fixture()[:-1])

    def test_duplicate_rejected(self):
        rows=fixture()
        with self.assertRaisesRegex(ValueError,'duplicate'):hybrid.summarize(rows+[rows[0]])

    def test_nonfinite_metadata_rejected(self):
        for field in ('env','onset','peak','semitones'):
            rows=fixture();rows[1][field]=math.nan
            with self.assertRaisesRegex(ValueError,'non-finite'):hybrid.summarize(rows)

    def test_inconsistent_pair_rejected(self):
        for field,value in (('category','voice'),('semitones',8.0)):
            rows=fixture();rows[1][field]=value
            with self.assertRaisesRegex(ValueError,'inconsistent'):hybrid.summarize(rows)

    def test_unknown_task_rejected(self):
        rows=fixture();rows[0]['task']='mos'
        with self.assertRaisesRegex(ValueError,'unexpected'):hybrid.summarize(rows)

    def test_rate_mismatch_preflight_writes_nothing(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);refs=root/'refs';tests=root/'tests';refs.mkdir();tests.mkdir()
            sf.write(refs/'fixture.wav',np.ones(500)*.1,44100)
            sf.write(tests/'fixture_Elastique_150_per.wav',np.ones(750)*.1,48000)
            output=root/'output'
            argv=['eval_hybrid_corpus.py','--pv-cli',sys.executable,'--multires-cli',sys.executable,
                  '--ref-dir',str(refs),'--test-dir',str(tests),'--output',str(output),
                  '--source-commit','synthetic-test']
            with patch.object(sys,'argv',argv),self.assertRaisesRegex(ValueError,'mismatch'):
                hybrid.main()
            self.assertFalse(output.exists())

if __name__=='__main__':unittest.main()
