"""Raw three-way review reports never borrow four-way baseline labels."""
import sys
from pathlib import Path
import numpy as np
import soundfile as sf
sys.path.insert(0,str(Path(__file__).resolve().parent))
from test_reference_profiles import Fixture
from eval_multires_corpus import fingerprint
from report_reference_profile_peaks import audit


class ReferencePeakTests(Fixture):
    def test_raw_amplitudes_and_pairing(self):
        rows,summary=audit(self.evaluation,self.refs)
        self.assertEqual(summary['conditions'],6);self.assertEqual(summary['rows'],18)
        self.assertEqual(summary['external_baseline'],'none')
        multi=next(r for r in rows if r['profile']=='multires')
        self.assertAlmostEqual(multi['peak_ratio_vs_transient'],1.2/1.1,places=6)
        self.assertAlmostEqual(multi['peak_ratio_vs_reference'],1.2,places=6)
        self.assertEqual(multi['artifact_assessment'],'not_listened')
        self.assertNotAlmostEqual(multi['peak'],.3) # CSV placeholder was not reused.

    def test_flags_do_not_assert_artifact(self):
        rows,summary=audit(self.evaluation,self.refs,peak_threshold=.01,ratio_threshold=1.01)
        self.assertEqual(summary['flagged_rows'],18)
        self.assertTrue(all(r['artifact_assessment']=='not_listened' for r in rows))

    def test_tampered_source_rejected(self):
        sf.write(self.source,self.x*.5,48000,subtype='FLOAT')
        with self.assertRaisesRegex(ValueError,'fingerprint'):audit(self.evaluation,self.refs)

    def test_silent_baseline_is_not_floored(self):
        for row in self.rows:
            if row['profile']=='transient':
                path=self.evaluation/row['render_path'];sf.write(path,np.zeros_like(self.x),48000,subtype='FLOAT')
                row['render_sha256']=fingerprint(path)
        self.save_grid()
        rows,_=audit(self.evaluation,self.refs)
        multi=next(r for r in rows if r['profile']=='multires')
        self.assertIsNone(multi['peak_ratio_vs_transient'])
        self.assertIsNone(multi['rms_delta_vs_transient_db'])
        self.assertIn('nonzero_vs_silent_transient',multi['review_flags'])

    def test_invalid_thresholds(self):
        for value in (0,-1,float('nan'),float('inf')):
            with self.assertRaises(ValueError):audit(self.evaluation,self.refs,value,1.1)
