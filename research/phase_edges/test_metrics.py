import unittest
import numpy as np
import study as s

class StudyTests(unittest.TestCase):
    def test_local_identity_gain_and_input_purity(self):
        x=np.random.default_rng(7).normal(0,.1,(20000,2));copy=x.copy()
        for gain in (.1,1,2):
            metrics=s.local_spectral(x,gain*x,48000,1)
            self.assertLess(max(metrics.values()),1e-12)
        np.testing.assert_array_equal(x,copy)
    def test_local_descriptor_detects_misplaced_event(self):
        x=np.zeros((30000,1));x[9000:10000,0]=np.random.default_rng(8).normal(0,.1,1000)
        y=np.roll(x,4800,axis=0)
        self.assertGreater(s.local_spectral(x,y,48000,1)['local_spectral_512_db'],30)
    def test_grid_missing_duplicate_rejected(self):
        r=dict(source='a',rate=48000,ratio=1.5,seed=0,mode='heap');keys=[('a',48000,1.5,0,'heap')]
        s.validate([r],keys)
        for rows in ([],[r,r]):
            with self.assertRaises(ValueError):s.validate(rows,keys)
    def test_seeded_fixtures_fixed_and_band_safe(self):
        for seed in s.SEEDS:
            a,f=s.fixture('newbank',48000,2,seed);b,_=s.fixture('newbank',48000,2,seed)
            np.testing.assert_array_equal(a,b);self.assertLess(max(f),24000-4);self.assertGreater(min(np.diff(f)),8)

if __name__=='__main__':unittest.main()
