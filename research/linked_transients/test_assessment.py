import unittest
import numpy as np
import assess as a

class AssessmentTests(unittest.TestCase):
    def test_one_to_one_detection_does_not_count_duplicates(self):
        truth=[(.1,0,.002),(.12,1,.002)]
        s=a.detection_score(np.array([100.,100.,120.]),truth,1000)
        self.assertEqual((s['tp'],s['fp'],s['fn']),(2,1,0))
        s=a.detection_score(np.array([110.]),truth,1000)
        self.assertEqual((s['tp'],s['fp'],s['fn']),(0,1,2))
    def test_exact_oracle_and_gain_calibration(self):
        x,events=a.events_signal(48000)
        s=a.event_score(x,x,48000,events)
        for k in ('width_error_ms','centroid_error_ms','energy_error_db','outside_support_fraction'):self.assertLess(s[k],1e-12)
        g=a.event_score(x*.5,x,48000,events)
        self.assertAlmostEqual(g['energy_error_db'],20*np.log10(2),places=10)
        self.assertLess(g['centroid_error_ms'],1e-10)
    def test_delay_is_not_fitted_away(self):
        x,events=a.events_signal(48000);y=np.pad(x,((48,0),(0,0)))[:len(x)]
        s=a.event_score(y,x,48000,events)
        self.assertAlmostEqual(s['centroid_error_ms'],1.,places=7)
    def test_frozen_new_signals_and_output_shapes(self):
        self.assertEqual(len(a.SEEDS),8);self.assertEqual(len(set(a.SEEDS)),8)
        for rate in (48000,96000):
            for ratio in (.5,1.5,2.):
                x,meta=a.fixture('mixture',rate,ratio,a.SEEDS[0]);y,_=a.fixture('mixture',rate,ratio,a.SEEDS[0])
                np.testing.assert_array_equal(x,y);self.assertEqual(len(x),int(np.floor(1.85*rate*ratio+.5)))
                self.assertEqual(len(meta['events']),8)
if __name__=='__main__':unittest.main()
