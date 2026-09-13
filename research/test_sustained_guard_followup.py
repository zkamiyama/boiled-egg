import sys,unittest,tempfile,subprocess
from pathlib import Path
from unittest.mock import patch
import numpy as np
import soundfile as sf
sys.path.insert(0,str(Path(__file__).resolve().parent))
import eval_sustained_guard_followup as e
class FollowupTest(unittest.TestCase):
 def test_seeded_bank_and_alias_free_partial_spacing(self):
  for rate in (48000,96000):
   for seed in range(4):
    x,m=e.oscillator_bank(seed,rate,.5);again,_=e.oscillator_bank(seed,rate,.5)
    np.testing.assert_array_equal(x,again);self.assertGreater(np.diff(m['frequencies']).min(),8)
    _,m=e.oscillator_bank(seed,rate,2);self.assertLess(m['frequencies'].max(),rate/2-4)
 def test_pair_order_and_duplicate_rejection(self):
  rows=[dict(cell=i,source=str(i//2),variant=v,error=i+(1 if v=='guard' else 0)) for i in range(4) for v in ('baseline','guard')]
  r=e.paired_summary(rows,('cell',),['error'],'source')['error']
  self.assertEqual(r['n'],4);self.assertEqual(r['delta'],1);self.assertEqual(r['ci95'],[1,1])
  with self.assertRaises(ValueError):e.paired_summary(rows+rows[:1],('cell',),['error'])
 def test_renderer_error_and_metadata_not_scored(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'wrong.wav';sf.write(p,np.zeros(128),44100,subtype='FLOAT')
   with patch.object(e.subprocess,'run',return_value=subprocess.CompletedProcess([],0,'','')):
    with self.assertRaisesRegex(ValueError,'metadata'):e.launch([],p,48000,128,1)
   with patch.object(e.subprocess,'run',return_value=subprocess.CompletedProcess([],1,'','fixture failure')):
    with self.assertRaisesRegex(RuntimeError,'fixture failure'):e.launch([],p,44100,128,1)
 def test_guard_has_control_for_every_declared_profile(self):
  profiles={p for p,v in e.VARIANTS if v=='baseline'}
  self.assertTrue(all(p in profiles for p,v in e.VARIANTS if v=='guard'))
if __name__=='__main__':unittest.main()
