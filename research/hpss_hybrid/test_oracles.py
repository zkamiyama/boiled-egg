import unittest
import numpy as np
import metrics as m

class OracleTests(unittest.TestCase):
    def test_oracle_and_shorter_are_not_always_better(self):
        x=m.fixture('attack',48000)[0];r=m.temporal_errors(x,x,48000)
        self.assertEqual(r['width_absolute_error_ms'],0);self.assertEqual(r['centroid_absolute_error_ms'],0)
        y=np.zeros_like(x)
        for start in m.STARTS:y[round((start+.001)*48000)]=1
        self.assertGreater(m.temporal_errors(y,x,48000)['width_absolute_error_ms'],.5)
    def test_delay_detected_without_alignment(self):
        x=m.fixture('attack',48000)[0];y=np.roll(x,480)
        r=m.temporal_errors(y,x,48000);self.assertAlmostEqual(r['centroid_absolute_error_ms'],10,places=8)
        self.assertAlmostEqual(r['outside_gate_energy_fraction'],1,places=12)
    def test_metrics_do_not_modify_input(self):
        x=np.random.default_rng(13).normal(0,.1,(20000,2));before=x.copy()
        d=m.local_spectral(x,x*.7,48000,1);self.assertLess(max(d.values()),1e-12)
        m.natural_metrics(x,x*.7,48000,1);np.testing.assert_array_equal(before,x)
    def test_seeded_banks_and_low_tone(self):
        for seed in tuple(range(2609160,2609168)):
            x,f=m.fixture('newbank',48000,2,seed);y,_=m.fixture('newbank',48000,2,seed)
            np.testing.assert_array_equal(x,y);self.assertLess(max(f),24000-4);self.assertGreater(min(np.diff(f)),8)
        x,f=m.fixture('low55',48000);d=m.synthetic_metrics('low55',x[:,None],x,f,48000,1)
        self.assertLess(abs(d['pitch_error_cents']),.1)

if __name__=='__main__':unittest.main()
