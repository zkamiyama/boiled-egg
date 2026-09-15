import os,unittest
import numpy as np
from scipy import signal
import render as r
import power_render as p
class PowerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.k=r.Kernels(os.environ['BOILED_EGG_HPSS_LIBRARY']);cls.pk=p.PowerKernel(os.environ['BOILED_EGG_HPSS_POWER_LIBRARY'])
    def test_dictionary_weights(self):
        source=np.array([0,4,8,12,16,20]);target=np.array([0,5,11,16,21,27]);w=signal.windows.hann(32,sym=False)
        actual=self.pk.weights(30,source,target,w,40);expected=[]
        for j in range(40):
            weights={}
            for s,t in zip(source,target):
                k=j-t+16;index=j+s-t
                if 0<=k<32 and 0<=index<30:weights[index]=weights.get(index,0)+w[k]
            expected.append(sum(v*v for v in weights.values()))
        np.testing.assert_allclose(actual,expected,rtol=0,atol=4e-15)
    def test_identity_without_unity_bypass(self):
        x=np.random.default_rng(891).normal(0,.1,(8193,2))
        for sparse in (False,True):
            out=p.short_render(x,48000,1,1,self.k,self.pk,sparse,True)
            np.testing.assert_allclose(out,x,rtol=0,atol=3e-16)
    def test_near_unity_no_arbitrary_normalizer_jump(self):
        x=np.random.default_rng(341).normal(0,.1,(8193,2))
        for ratio in (1-1e-9,1.,1+1e-9):
            out=p.short_render(x,48000,ratio,1,self.k,self.pk,False,True)
            np.testing.assert_allclose(out,x,atol=3e-16,rtol=0)
    def test_white_noise_power_model(self):
        x=np.random.default_rng(261).normal(0,.1,(96000,1))
        for time in (.5,1.5,2):
            a=p.short_render(x,48000,time,1,self.k,self.pk,False,False)
            b=p.short_render(x,48000,time,1,self.k,self.pk,False,True)
            gain=lambda y:10*np.log10(np.mean(y[2048:-2048]**2)/np.mean(x**2))
            self.assertLess(gain(a),-6)
            self.assertLess(abs(gain(b)),.2)
    def test_independent_addresses_not_mistaken_for_coherence(self):
        w=np.ones(4);s=np.array([0,1]);t=np.array([0,0]);out=self.pk.weights(8,s,t,w,4)
        self.assertEqual(out[0],2.) # two independent input samples, not squared sum4
        self.assertEqual(self.pk.weights(8,s,s,w,4)[0],4.) # identical source address
    def test_gain_correction_does_not_remove_periodic_correlation(self):
        # Negative model calibration, NOT a sonic-quality acceptance gate.
        x=np.random.default_rng(261).normal(0,.1,(96000,1))
        a=p.short_render(x,48000,2,1,self.k,self.pk,False,False)[2048:-2048,0]
        b=p.short_render(x,48000,2,1,self.k,self.pk,False,True)[2048:-2048,0]
        corr=lambda v:np.corrcoef(v[:-16],v[16:])[0,1]
        self.assertGreater(corr(a),.95)
        self.assertAlmostEqual(corr(a),corr(b),places=12)
        self.assertLess(abs(corr(x[2048:-2048,0])),.02)
    def test_nonmonotone_and_bad_window_rejected(self):
        with self.assertRaises(ValueError):self.pk.weights(8,[0,1,2],[0,2,2],np.ones(4),8)
        with self.assertRaises(ValueError):self.pk.weights(8,[0],[0],np.array([np.nan]),8)
if __name__=='__main__':unittest.main()
