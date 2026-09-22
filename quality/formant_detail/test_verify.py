import itertools,unittest
import numpy as np
import verify as v
class Controls(unittest.TestCase):
 def test_fixtures(self):
  for f,r in itertools.product(v.FAMILIES,v.RATES):
   x=v.fixture(f,r); self.assertEqual(len(x),2*r);self.assertTrue(np.isfinite(x).all());self.assertGreater(np.sum(x*x),0)
   np.testing.assert_array_equal(v.fixture(f,r,2)[:,1],-.5*x)
 def test_no_silent_score(self):
  with self.assertRaises(ValueError):v.measure(np.zeros(96000),'check83',48000,12)
 def test_identity_target_and_faults(self):
  x=v.fixture('check83',48000);m=v.measure(x,'check83',48000,0);self.assertLess(m['rmse_db'],1e-4);self.assertLess(m['unexplained_energy'],1e-6)
  wrong=v.measure(.1*x,'check83',48000,0);self.assertGreater(wrong['rmse_db'],19.9)
 def test_incomplete_duplicate_grids(self):
  for fn in (v.assess_quality,v.assess_cost):
   with self.assertRaises(ValueError):fn([])
 def test_full_failed_grid_is_not_pass(self):
  rows=[dict(zip(('family','rate','channels','block','shift','io','detail','repeat'),key),status='failed') for key in itertools.product(v.FAMILIES,v.RATES,(1,),(64,),v.SHIFTS,(1,),(0,1),range(3))]
  self.assertFalse(v.assess_quality(rows)['passed'])
 def test_fabricated_complete_is_not_evidence(self):
  rows=[dict(zip(('family','rate','channels','block','shift','io','detail','repeat'),key),status='complete') for key in itertools.product(v.FAMILIES,v.RATES,(1,),(64,),v.SHIFTS,(1,),(0,1),range(3))]
  self.assertFalse(v.assess_quality(rows)['passed'])
 def test_unknown_input_rejected(self):
  with self.assertRaises(ValueError):v.fixture('unknown',48000)
if __name__=='__main__':unittest.main()
