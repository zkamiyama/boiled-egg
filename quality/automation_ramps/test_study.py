import unittest
import numpy as np
from study import curve_values,event_plan,Ramp,Info
import ctypes
class StudyTests(unittest.TestCase):
    def test_layout(self):
        self.assertEqual(ctypes.sizeof(Ramp),32);self.assertEqual(ctypes.sizeof(Info),64)
    def test_post_tick_and_steps(self):
        np.testing.assert_array_equal(curve_values(6,[(1,2,2.,2,0),(4,2,.5,0,0)],2),[1,1.5,2,2,.5,.5])
    def test_interruption_and_duplicate(self):
        x=curve_values(5,[(0,2,2.,4,0),(2,2,.5,2,0)],2)
        np.testing.assert_array_equal(x,[1.25,1.5,1,.5,.5])
        np.testing.assert_array_equal(curve_values(3,[(0,2,2.,10,1),(0,2,.5,0,0)],2),[.5,.5,.5])
    def test_log_endpoint(self):
        x=curve_values(5,[(0,2,2.,4,1)],2)
        np.testing.assert_allclose(x,[2**.25,2**.5,2**.75,2,2],atol=1e-15)
    def test_time_clock_independent_of_pitch(self):
        ev=[(0,2,.5,500,1)]
        np.testing.assert_array_equal(curve_values(8,ev,1),np.ones(8))
    def test_bad_order(self):
        with self.assertRaises(ValueError):curve_values(5,[(3,2,1.,2,0),(2,2,1.,2,0)],2)
    def test_all_generated_groups_are_safe(self):
        for kind in ('pitch','time'):
            for shape in (0,1):
                events=event_plan(249600,48000,kind,shape,True)
                p=curve_values(249600,events,2);t=curve_values(249600,events,1)
                self.assertLessEqual(float(np.max(p*t)),2)
if __name__=='__main__':unittest.main()
