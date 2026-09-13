"""Validate temporal-only no-preservation controls without invented MOS."""
import csv,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parent))
import check_pitch_formant_control as p
class PitchControlTests(unittest.TestCase):
    def rows(self):
        return [dict(source=source,condition=source+str(i),profile=profile,
                     onset_corr=.8 if profile=='derived_elastique' else .9,
                     rms_shape_db=2. if profile=='derived_elastique' else 1.)
                for source in ('a','b','c') for i in (0,1)
                for profile in ('derived_elastique',*p.c.e.PROFILES)]
    def test_paired_means_and_directions(self):
        for r in p.summarize(self.rows()):
            self.assertEqual(r['n'],6);self.assertEqual(r['sources'],3);self.assertEqual(r['wins'],6)
            self.assertAlmostEqual(r['delta'],.1 if r['metric']=='onset_corr' else -1.)
    def test_missing_and_duplicate_cells_fail(self):
        rows=self.rows()
        with self.assertRaises(ValueError):p.summarize(rows+rows[:1])
        with self.assertRaises(KeyError):p.summarize(rows[:-1])
        with self.assertRaises(ValueError):p.summarize([])
    def test_render_command_really_disables_formant_preservation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);t=np.arange(32000)/16000
            source=root/'source.wav';test=root/'test.wav'
            x=(.2*np.sin(2*np.pi*220*t)).astype('float32')
            for path in (source,test):p.c.sf.write(path,x,16000,subtype='FLOAT')
            cell=dict(reference_name=source.name,processed_name=test.name,reference_sha256=p.c.fingerprint(source),
                processed_sha256=p.c.fingerprint(test),control_ratio=1.,stem='source',condition_id='C001')
            def render(command,**kwargs):
                self.assertEqual(command[command.index('--formant')+1],'off')
                self.assertEqual(command[command.index('--time')+1],'1')
                p.c.sf.write(command[2],x,16000,subtype='FLOAT')
                return p.subprocess.CompletedProcess(command,0,'','')
            with patch.object(p.subprocess,'run',side_effect=render) as proc:
                rows=p.measure((cell,root,root,root))
            self.assertEqual(proc.call_count,5);self.assertEqual(len(rows),6)
            self.assertTrue(all(r['formant']=='off' for r in rows))
            self.assertTrue(all('envelope_rmse_db' not in r for r in rows))
if __name__=='__main__':unittest.main()
