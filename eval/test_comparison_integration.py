"""Actual FFmpeg + product CLI integration. No missing-engine skips.

Usage: BOILED_EGG_CLI=/path/boiled_egg_cli python eval/test_comparison_integration.py
The calibration report retains its own strict pitch gate. This test audits
correct handling of both reference successes and rejections, not their sound.
"""
import argparse
import csv
import json
import os
from pathlib import Path
import tempfile
import unittest

import calibrate_external as calibration
import comparison_contract as contract


class RealComparisonTests(unittest.TestCase):
    def test_real_operations_negative_controls_and_rejection_accounting(self):
        cli = Path(os.environ['BOILED_EGG_CLI']).resolve(strict=True)
        destination = os.environ.get('BOILED_EGG_COMPARISON_RESULTS')
        with tempfile.TemporaryDirectory(prefix='boiled-comparison-test-') as temporary:
            root = Path(destination) if destination else Path(temporary)/'calibration'
            report = calibration.run(argparse.Namespace(ffmpeg=os.environ.get('FFMPEG','ffmpeg'),
                cli=cli,spectral_cli=None,output=root,quick=True))
            with (root/'measurements.csv').open(newline='') as stream:
                rows=list(csv.DictReader(stream))
            self.assertEqual(len(rows),8)
            self.assertTrue(all(r['status']=='passed' for r in rows if r['engine']=='boiled_egg'))
            self.assertTrue(all(n['detected'] for n in report['negative_controls']))
            self.assertTrue(report['stable_engine_identities'])
            # All requested metadata must be right; any dominant-tone diagnostic
            # rejection stays visible and report.passed must stay false.
            self.assertEqual(report['passed'],all(r['status']=='passed' for r in rows))
            self.assertEqual(report['passed_cases'],sum(r['status']=='passed' for r in rows))
            for row in rows:
                receipt=contract.verify_case(root/row['case'])
                self.assertEqual(receipt['duration_error_frames'],0)
                self.assertEqual(receipt['output']['subtype'],'FLOAT')
                if row['status'] != 'passed':
                    self.assertEqual(row['status'],'pitch_failed')
                    self.assertGreater(abs(float(row['cents_error'])),5.)
                    self.assertFalse(report['passed'])
            if destination:
                contract.json_write(root/'integration-test.json',dict(passed=True,
                    scope='operation/format and truthful calibration accounting; not a passing reference pitch gate',
                    calibration_passed=report['passed']))


if __name__=='__main__':unittest.main()
