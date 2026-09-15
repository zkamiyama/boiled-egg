import unittest
import numpy as np
import stereo_time as s

class StereoTimeTests(unittest.TestCase):
    def test_known_gain_polarity_and_silent_channel(self):
        x=s.fixture('proportional',48000);before=x.copy();x.setflags(write=False)
        self.assertLess(s.relation_error(x,-.375),1e-7)
        self.assertGreater(s.relation_error(x,.375),.7)
        z=s.fixture('silent_right',48000)
        self.assertEqual(s.relation_error(z,0.),0.)
        z[:,1]=.01*z[:,0]
        self.assertAlmostEqual(s.relation_error(z,0.),.01,places=8)
        np.testing.assert_array_equal(x,before)
    def test_zero_and_invalid_are_not_success(self):
        for x in (np.zeros((10,2)),np.full((10,2),np.nan),np.zeros((10,1))):
            with self.assertRaises(ValueError):s.relation_error(x,0.)
        with self.assertRaises(ValueError):s.permutation_error(np.zeros((3,2)),np.zeros((3,2)))
    def test_delay_is_recorded_not_fitted_away(self):
        x=s.fixture('bursts',48000);y=np.pad(x,((48,0),(0,0)))[:len(x)]
        a=s.placements(x,48000,1.);b=s.placements(y,48000,1.)
        for u,v in zip(a,b):
            self.assertLess(abs(u['signed_error_samples']),1e-5)
            self.assertAlmostEqual(v['signed_error_samples']-u['signed_error_samples'],48.,places=7)
    def test_scaled_positions_keep_signed_errors(self):
        rate=48000;ratio=1.1;x=s.fixture('bursts',rate);y=np.zeros((round(len(x)*ratio),2))
        for t,ch in s.EVENTS:
            start=round(t*rate);dest=round(t*rate*ratio)
            y[dest-96:dest+96,ch]=x[start-96:start+96,ch]
        for r in s.placements(y,rate,ratio):self.assertLess(abs(r['signed_error_samples']),1e-5)
    def test_exchange_covariance_and_shape_failure(self):
        x=s.fixture('bursts',48000);y=s.fixture('bursts_swapped',48000)
        self.assertEqual(s.permutation_error(x,y),0.)
        self.assertGreater(s.permutation_error(x,x),1.)
        with self.assertRaises(ValueError):s.permutation_error(x,y[:-1])
    def test_missing_event_and_input_purity(self):
        x=s.fixture('bursts',48000);before=x.copy();x.setflags(write=False)
        s.placements(x,48000,1.)
        np.testing.assert_array_equal(x,before)
        y=x.copy();y[:,1]=0
        with self.assertRaisesRegex(ValueError,'event'):s.placements(y,48000,1.)
    def test_complete_grid_rejects_lost_duplicate_nonfinite(self):
        rows=[dict(rate=48000,operation=0,fixture=f,engine='test',score=0.) for f in s.FIXTURES]
        keys={(48000,0,f,'test') for f in s.FIXTURES}
        s.validate_grid(rows,keys)
        for wrong in (rows[:-1],rows+rows[:1],[dict(rows[0],score=float('nan'))]+rows[1:]):
            with self.assertRaises(ValueError):s.validate_grid(wrong,keys)
    def test_fixed_protocol_and_deterministic_fixtures(self):
        self.assertEqual(len(s.OPERATIONS),5);self.assertEqual(s.THRESHOLD,1e-5)
        for rate in (48000,96000):
            for name in s.FIXTURES:
                x=s.fixture(name,rate)
                self.assertEqual(x.shape,(rate*2,2));self.assertEqual(x.dtype,np.float32)
                np.testing.assert_array_equal(x,s.fixture(name,rate))
if __name__=='__main__':unittest.main()
