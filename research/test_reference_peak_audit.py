"""Reference-grid raw peak audits; generated audio tests software only."""
import json
import sys
import unittest
from pathlib import Path

import numpy as np
import soundfile as sf

sys.path.insert(0, str(Path(__file__).resolve().parent))
import report_reference_peaks as peaks
import test_reference_profiles as fixture
from eval_multires_corpus import fingerprint


class ReferencePeakTest(fixture.Fixture):
    def setUp(self):
        super().setUp()
        self.refresh()

    def refresh(self):
        for row in self.rows:
            path = self.evaluation/row['render_path']
            audio, rate = sf.read(path, always_2d=True)
            stats = peaks.raw_stats(audio, rate)
            row.update(peak=stats['peak'], rms=stats['rms'], render_sha256=fingerprint(path))
        self.save_grid()

    def test_every_paired_profile_measured(self):
        rows, report = peaks.audit(self.evaluation, self.refs)
        self.assertEqual(report['measurements'], 18)
        self.assertEqual(report['conditions'], 6)
        self.assertEqual(report['review_rows'], 0)
        multires = next(r for r in rows if r['profile'] == 'multires')
        self.assertAlmostEqual(multires['peak_ratio_vs_transient'], 1.2/1.1, places=6)
        self.assertEqual(multires['artifact_assessment'], 'not_listened')

    def test_raw_peak_time_channel_and_no_audio_mutation(self):
        row = self.rows[2]
        path = self.evaluation/row['render_path']
        audio = self.x.copy(); audio[2000] = 2
        sf.write(path, audio, 48000, subtype='FLOAT')
        self.refresh()
        before = fingerprint(path)
        rows, report = peaks.audit(self.evaluation, self.refs)
        found = next(r for r in rows if r['profile'] == 'multires' and r['pitch_semitones'] == -12)
        self.assertEqual(found['peak'], 2)
        self.assertEqual(found['peak_channel'], 0)
        self.assertAlmostEqual(found['peak_time_seconds'], 2000/48000)
        self.assertIn('absolute_peak', found['review_reasons'])
        self.assertEqual(before, fingerprint(path))
        self.assertGreater(report['review_rows'], 0)

    def test_silence_has_null_ratios_and_db(self):
        sf.write(self.source, np.zeros_like(self.x), 48000, subtype='FLOAT')
        digest = fingerprint(self.source)
        self.sources[0]['reference_sha256'] = digest
        for row in self.rows:
            row['reference_sha256'] = digest
            sf.write(self.evaluation/row['render_path'], np.zeros_like(self.x), 48000, subtype='FLOAT')
        self.refresh()
        rows, report = peaks.audit(self.evaluation, self.refs)
        self.assertTrue(all(r['peak_ratio_vs_reference'] is None and r['rms_dbfs'] is None for r in rows))
        self.assertEqual(report['review_rows'], 0)
        json.dumps(report, allow_nan=False)

    def test_changed_audio_and_inconsistent_metrics_rejected(self):
        path = self.evaluation/self.rows[0]['render_path']
        original = path.read_bytes()
        sf.write(path, self.x*.5, 48000, subtype='FLOAT')
        with self.assertRaisesRegex(ValueError, 'fingerprint'):
            peaks.audit(self.evaluation, self.refs)
        path.write_bytes(original)
        self.rows[0]['peak'] = 9
        self.save_grid()
        with self.assertRaisesRegex(ValueError, 'CSV peak/RMS'):
            peaks.audit(self.evaluation, self.refs)

    def test_wrong_rate_rejected(self):
        path = self.evaluation/self.rows[0]['render_path']
        sf.write(path, self.x, 44100, subtype='FLOAT')
        self.refresh()
        with self.assertRaises(ValueError):
            peaks.audit(self.evaluation, self.refs)

    def test_bad_limits(self):
        for value in (0, -1, float('nan'), float('inf')):
            with self.assertRaises(ValueError):
                peaks.audit(self.evaluation, self.refs, ratio_limit=value)

    def test_atomic_report_and_overwrite_refusal(self):
        rows, report = peaks.audit(self.evaluation, self.refs)
        output = self.root/'audit'
        peaks.write_report(output, rows, report)
        self.assertTrue((output/'all_peaks.csv').is_file())
        self.assertEqual(len((output/'peak_outliers.csv').read_text().splitlines()), 1)
        with self.assertRaises(ValueError):
            peaks.write_report(output, rows, report)


if __name__ == '__main__':
    unittest.main()
