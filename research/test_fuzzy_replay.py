"""Byte-exact optimization replay tests; fixtures are not listening evidence."""
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock
import numpy as np
import soundfile as sf
sys.path.insert(0, str(Path(__file__).resolve().parent))
import check_fuzzy_replay as replay


class ReplayTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.ref = self.root/'source.wav'
        self.original = self.root/'original.wav'
        sf.write(self.ref, np.zeros(4800), 48000, subtype='FLOAT')
        sf.write(self.original, np.linspace(-.1,.1,4800), 48000, subtype='FLOAT')
        self.row = dict(reference_name=self.ref.name, reference_sha256=replay.e.fingerprint(self.ref),
                       render_path=self.original.name, render_sha256=replay.e.fingerprint(self.original),
                       condition_id='C0001', profile='fuzzy', formant='harmonic', control_ratio=2.0)
        self.job = (self.row, self.root, self.root, self.ref, 32)

    def mock_render(self, command, **kwargs):
        Path(command[2]).write_bytes(self.original.read_bytes())
        return subprocess.CompletedProcess(command, 0, '', '')

    def test_identical_wav_is_compared_at_requested_block(self):
        with mock.patch.object(replay.subprocess, 'run', side_effect=self.mock_render) as process:
            result = replay.check_render(self.job)
        self.assertTrue(result['identical'])
        command = process.call_args.args[0]
        self.assertEqual(command[command.index('--block')+1], '32')
        self.assertEqual(command[command.index('--mode')+1], 'fuzzy')

    def test_different_wav_is_a_failed_comparison(self):
        def changed(command, **kwargs):
            Path(command[2]).write_bytes(self.ref.read_bytes())
            return subprocess.CompletedProcess(command, 0, '', '')
        with mock.patch.object(replay.subprocess, 'run', side_effect=changed):
            result = replay.check_render(self.job)
        self.assertFalse(result['identical'])
        self.assertNotEqual(result['original_sha256'], result['replay_sha256'])

    def test_tampering_fails_before_render(self):
        for key in ('render_sha256','reference_sha256'):
            original = self.row[key]; self.row[key] = '0'*64
            with mock.patch.object(replay.subprocess, 'run') as process:
                with self.assertRaisesRegex(ValueError, 'fingerprint'):
                    replay.check_render(self.job)
                process.assert_not_called()
            self.row[key] = original

    def test_renderer_error_is_not_a_comparison(self):
        failure = subprocess.CompletedProcess([], 1, '', 'fixture error')
        with mock.patch.object(replay.subprocess, 'run', return_value=failure):
            with self.assertRaisesRegex(RuntimeError, 'fixture error'):
                replay.check_render(self.job)

    def test_invalid_commit_or_workers_refused(self):
        for commit, workers in [('short',1),('a'*40,0)]:
            with self.assertRaises(ValueError):
                replay.run(self.root,self.root,self.ref,commit,workers)

if __name__ == '__main__':
    unittest.main()
