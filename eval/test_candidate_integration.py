"""Required real WSOLA+offline R3 evidence-to-listener integration, no mocks.

BOILED_EGG_CLI and BOILED_EGG_RB_LIBRARY must identify trusted local binaries.
Missing engines are errors, not silently skipped CI. Small fixed fixture only;
not the full calibration or product-quality decision.
"""
import json
import os
from pathlib import Path
import tempfile
import unittest
import numpy as np
import soundfile as sf
import candidate_evidence as e
import calibrated_listening as l

class CandidateIntegration(unittest.TestCase):
    def test_real_receipts_calibration_eligibility_and_pack(self):
        with tempfile.TemporaryDirectory() as tmp:
            requested=os.environ.get('BOILED_EGG_LISTENING_RESULTS')
            root=Path(requested) if requested else Path(tmp)
            if requested:root.mkdir(parents=True,exist_ok=False)
            panel=[e.Candidate('wsola','boiled_egg',os.environ['BOILED_EGG_CLI']),
                   e.Candidate('r3','rubberband_direct',os.environ['BOILED_EGG_RB_LIBRARY'],block=4096,generation=3)]
            calibration=e.calibrate(panel,root/'calibration',rates=(48000,),channels=(1,),operations=((.8,0),(1.25,0),(1.,-7),(1.,7)))
            self.assertTrue(calibration['passed']);self.assertEqual(calibration['rows'],8)
            t=np.arange(96000)/48000
            # A different signal from the calibration tone, all conditions retained.
            x=.08*np.sin(2*np.pi*220*t)+.04*np.sin(2*np.pi*660*t)
            source=root/'source.wav';sf.write(source,x,48000,subtype='FLOAT')
            report=l.run_panel(root/'calibration',[source],[(.8,0),(1.,7)],panel,root/'run')
            self.assertTrue(report['passed']);self.assertEqual(report['expected_cells'],4)
            pack=l.make_pack(root/'run',root/'calibration',root/'pack')
            self.assertEqual((pack['trials'],pack['choices'],pack['ratings_received']),(2,4,0))
            self.assertEqual(l.validate_answers(root/'pack',dict(pack_id=pack['pack_id'],ratings=[])),[])
            for path in (root/'pack/listener/audio').glob('*.wav'):
                y,rate=sf.read(path,always_2d=True);self.assertEqual(rate,48000)
                self.assertTrue(np.isfinite(y).all());self.assertLessEqual(np.abs(y).max(),.9500001)
            with self.assertRaisesRegex(ValueError,'untested'):
                l.run_panel(root/'calibration',[source],[(1.,3)],panel,root/'forbidden')
            self.assertFalse((root/'forbidden').exists())

if __name__=='__main__':unittest.main()
