import unittest
from pathlib import Path
import tempfile
from unittest.mock import patch
import numpy as np
import soundfile as sf
import study as s

class StudyTest(unittest.TestCase):
    def test_named_policy_grid_without_substitution(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'trusted-file';p.write_text('test double; never loaded')
            configs=s.configurations(p,p)
            self.assertEqual(len(configs),8)
            self.assertEqual({c['formant'] for c in configs if c['kind']=='spectral'}, {'off','harmonic','monophonic'})
            self.assertEqual({c['formant'] for c in configs if c['kind']=='rubberband_direct'}, {'off','preserved'})
        with self.assertRaises(ValueError):s.configurations(None,None)
    def test_duplicate_missing_and_nonfinite_grid(self):
        rows=[dict(rate=48000,f0=110.,contour='open',shift=3,engine=x,error=0.) for x in ('a','b')]
        keys={(48000,110.,'open',3,x) for x in ('a','b')}
        s.validate_grid(rows,keys)
        for bad in (rows[:1],rows+rows[:1],[rows[0],dict(rows[1],error=float('nan'))]):
            with self.assertRaises(ValueError):s.validate_grid(bad,keys)
    def test_failed_reference_retains_receipt(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);source=root/'source.wav';sf.write(source,np.zeros(96000),48000,subtype='FLOAT')
            cfg=dict(name='r3_preserved',kind='rubberband_direct',path='/test-double',formant='preserved',block=4096)
            with patch.object(s,'Reference',side_effect=RuntimeError('calibration fixture failure')):
                r=s.render(cfg,{},source,s.c.Request(),root/'case')
            self.assertEqual(r['status'],'failed');self.assertIn('calibration fixture failure',r['errors'][0])
            self.assertTrue((root/'case/receipt.json').is_file())
            self.assertFalse((root/'case/output.wav').exists())
if __name__=='__main__':unittest.main()
