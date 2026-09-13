import unittest
import numpy as np
from selective_nsgt_v2 import Config,render,wrap
class SelectiveTests(unittest.TestCase):
 def test_identity_even_odd_short(self):
  rng=np.random.default_rng(7)
  for n in (0,1,31,512,16001):
   x=rng.normal(0,.1,(n,2))
   for adaptive in (False,True):
    y,m=render(x,48000,cfg=Config(adaptive=adaptive,coherence=True))
    self.assertEqual(x.shape,y.shape);np.testing.assert_allclose(x,y,atol=2e-12,rtol=0)
 def test_exact_duration_and_silence(self):
  for t,p in ((.5,.5),(.5,2),(2,.5),(2,2)):
   y,m=render(np.zeros((4799,2)),48000,t,p)
   self.assertEqual(len(y),int(np.floor(4799*t+.5)));self.assertFalse(np.any(y))
 def test_linked_antiphase(self):
  x=np.random.default_rng(9).normal(0,.1,12000)
  y,m=render(np.c_[x,-.5*x],48000,1,1.5,Config(coherence=True))
  np.testing.assert_allclose(y[:,1],-.5*y[:,0],atol=2e-12)
 def test_invalid(self):
  for x in (np.full(10,np.nan),np.zeros((10,0)),np.zeros((10,9))):
   with self.assertRaises(ValueError):render(x,48000)
  with self.assertRaises(ValueError):render(np.ones(100),48000,3)
 def test_phase_difference_periodicity(self):
  rng=np.random.default_rng(13);d=rng.uniform(-np.pi,np.pi,100)
  np.testing.assert_allclose(wrap(d),wrap(d+4*np.pi),atol=5e-15)
 def test_reproducible(self):
  x=np.random.default_rng(17).normal(0,.1,8000)
  a,_=render(x,48000,1.3,1,Config(coherence=True));b,_=render(x,48000,1.3,1,Config(coherence=True))
  np.testing.assert_array_equal(a,b)
if __name__=='__main__':unittest.main()
