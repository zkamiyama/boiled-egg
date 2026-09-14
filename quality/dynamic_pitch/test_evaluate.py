import math
import unittest
import numpy as np
from evaluate import frequency
class ToneEstimatorTest(unittest.TestCase):
 def test_phase_and_gain_do_not_change_frequency(self):
  for rate in (48000,96000):
   for hz in (27.5,55.,220.,12400.):
    t=np.arange(round(.34*rate))/rate
    for phase,gain in ((.2,.1),(1.1,.3)):
     value=frequency(gain*np.sin(2*np.pi*hz*t+phase),rate,hz)
     self.assertLess(abs(1200*math.log2(value/hz)),.08)
 def test_detuned_tone_is_detected(self):
  rate=48000;t=np.arange(round(.34*rate))/rate;target=220.;actual=target*2**(20/1200)
  got=frequency(.2*np.sin(2*np.pi*actual*t),rate,target)
  self.assertAlmostEqual(1200*math.log2(got/target),20.,places=3)
 def test_silence_nonfinite_and_short_are_invalid(self):
  for x in (np.zeros(400),np.full(400,np.nan),np.ones(12)):
   with self.assertRaises(ValueError):frequency(x,48000,220.)
if __name__=='__main__':unittest.main()
