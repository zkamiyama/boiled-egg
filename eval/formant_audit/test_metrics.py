import unittest
import numpy as np
import metrics as m

class MetricsTest(unittest.TestCase):
    def test_independent_ideal_and_gain(self):
        for rate in (48000,96000):
            for preserved in (False,True):
                pitch=2**(7/12);x=m.fixture(rate,110.,'open',pitch,preserved)
                before=x.copy();x.setflags(write=False)
                a=m.measure(x,rate,110.,'open',pitch,preserved)
                b=m.measure(x*.5,rate,110.,'open',pitch,preserved)
                self.assertLess(a['target_contour_rmse_db'],.003)
                self.assertLess(abs(a['mean_partial_gain_db']),.003)
                self.assertAlmostEqual(b['target_contour_rmse_db'],a['target_contour_rmse_db'],places=7)
                self.assertAlmostEqual(b['mean_partial_gain_db']-a['mean_partial_gain_db'],20*np.log10(.5),places=6)
                np.testing.assert_array_equal(x,before)
    def test_shifted_envelope_is_not_preserved_truth(self):
        x=m.fixture(48000,220.,'closed',2.,False)
        right=m.measure(x,48000,220.,'closed',2.,False)
        wrong=m.measure(x,48000,220.,'closed',2.,True)
        self.assertLess(right['target_contour_rmse_db'],.003)
        self.assertGreater(wrong['target_contour_rmse_db'],5.)
    def test_known_contour_error(self):
        x=np.array([10**(-3/20),10**(3/20)])
        error,gain=m.contour_error(x,np.ones(2))
        self.assertAlmostEqual(error,3.);self.assertAlmostEqual(gain,0.)
    def test_nonfinite_duration_and_overlap_rejected(self):
        for x in (np.zeros((2,1)),np.full((96000,1),np.nan),np.zeros((96000,2))):
            with self.assertRaises(ValueError):m.band_amplitudes(x,48000,np.array([110.,220.]))
        with self.assertRaises(ValueError):m.band_amplitudes(np.zeros((96000,1)),48000,np.array([110.,111.]))
    def test_identity_and_determinism(self):
        for contour in m.CONTOURS:
            a=m.fixture(48000,220.,contour)
            np.testing.assert_array_equal(a,m.fixture(48000,220.,contour,1.,True))
            np.testing.assert_array_equal(a,m.fixture(48000,220.,contour))
if __name__=='__main__':unittest.main()
