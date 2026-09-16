import unittest
import numpy as np
import metrics as m

class Metrics(unittest.TestCase):
    def setUp(self):
        self.rng=np.random.default_rng(260916)
        self.a=self.rng.normal(size=(40,20,2))+1j*self.rng.normal(size=(40,20,2))
    def test_common_phase_is_not_spatial_damage(self):
        rotor=np.exp(1j*self.rng.uniform(-np.pi,np.pi,(40,20,1)))
        self.assertLess(m.projector_distance(self.a,self.a*rotor)['spatial_error'],1e-14)
    def test_relative_phase_and_mono_collapse_are_detected(self):
        b=self.a.copy();b[...,1]*=-1
        self.assertGreater(m.projector_distance(self.a,b)['spatial_error'],.1)
        b=np.repeat(self.a.mean(axis=-1,keepdims=True),2,axis=-1)
        self.assertGreater(m.projector_distance(self.a,b)['spatial_error'],.1)
    def test_severity_ordering(self):
        scores=[]
        for phase in [0.,.001,.01,.1,.5]:
            b=self.a.copy();b[...,1]*=np.exp(1j*phase)
            scores.append(m.projector_distance(self.a,b)['spatial_error'])
        self.assertTrue(all(a<b for a,b in zip(scores,scores[1:])))
    def test_zero_nonfinite_shape_fail(self):
        for b in [np.zeros_like(self.a),self.a[:1],self.a*np.nan]:
            with self.assertRaises(ValueError):m.projector_distance(self.a,b)
        with self.assertRaises(ValueError):m.relation(np.zeros((128,2)),[1,0])
    def test_known_gain_polarity_error(self):
        a=self.rng.normal(size=10000);x=np.c_[a,-.375*a];x.setflags(write=False)
        self.assertEqual(m.relation(x,[1,-.375])['relative_error'],0.)
        self.assertAlmostEqual(m.relation(x,[1,.375])['relative_error'],.75)
    def test_spectral_relation_and_injected_delay(self):
        a=self.rng.normal(size=12000);x=np.c_[a,-.375*a]
        self.assertLess(m.stereo_spectrum(x,48000,-.375)['spatial_error'],1e-14)
        b=x.copy();b[1:,1]=b[:-1,1];b[0,1]=0
        self.assertGreater(m.stereo_spectrum(b,48000,-.375)['spatial_error'],.1)
    def test_envelope_gain_and_timing_not_fitted(self):
        a=np.zeros((4800,1));a[2400:2448]=.1
        self.assertEqual(m.envelope_rmse(a,a,48000),0.)
        self.assertAlmostEqual(m.envelope_rmse(a,a*.5,48000),20*np.log10(2))
        b=np.roll(a,480,axis=0);self.assertGreater(m.envelope_rmse(a,b,48000),50)
    def test_projection_input_purity(self):
        a=self.a.copy();a.setflags(write=False);before=a.copy()
        m.projector_distance(a,a);np.testing.assert_array_equal(a,before)
if __name__=='__main__':unittest.main()
