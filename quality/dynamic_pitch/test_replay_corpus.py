"""Schedule and strict equality controls; no user corpus required."""
import unittest
import numpy as np
import replay_corpus as r
class DynamicReplayTest(unittest.TestCase):
    def test_input_schedule_is_sorted_and_policy_independent(self):
        off=r.schedule(48001,48000,0);harmonic=r.schedule(48001,48000,1)
        self.assertEqual(off,[e for e in harmonic if e[1]==2]);self.assertEqual(len(off),7)
        self.assertEqual([e[0] for e in harmonic],sorted(e[0] for e in harmonic))
        self.assertTrue(all(0<=at<48001 for at,_,_ in harmonic))
        with self.assertRaises(ValueError):r.schedule(31,48000,1)
    def test_delay_and_changed_sample_are_not_aligned_away(self):
        a=np.zeros((2,100),np.float32);b=a.copy()
        self.assertEqual(len(r.compare(a,b,10,10)),64)
        with self.assertRaises(ValueError):r.compare(a,b,10,11)
        b[0,50]=np.nextafter(np.float32(0),np.float32(1))
        with self.assertRaises(ValueError):r.compare(a,b,10,10)
    def test_nonfinite_or_wrong_shape_rejected(self):
        a=np.ones((1,100),np.float32)
        with self.assertRaises(ValueError):r.compare(a,a[:,:99],10,10)
        a[0,30]=np.nan
        with self.assertRaises(ValueError):r.compare(a,a.copy(),10,10)
if __name__=='__main__':unittest.main()
