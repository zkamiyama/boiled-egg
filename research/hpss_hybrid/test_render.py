import os,unittest
import numpy as np
from scipy import signal
import render as r

class HybridTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.hps=os.environ['BOILED_EGG_HPSS_LIBRARY'];cls.heap=os.environ['BOILED_EGG_PHASE_HEAP_LIBRARY'];cls.k=r.Kernels(cls.hps)
    def test_mask_formula_symmetry_scale_and_errors(self):
        a=np.array([0.,1.,.3,100]);b=np.array([0.,2.,.8,5]);m=self.k.mask(a,b)
        self.assertEqual(m[0],.5);np.testing.assert_allclose(m[1:],a[1:]**2/(a[1:]**2+b[1:]**2),atol=1e-16)
        np.testing.assert_allclose(m+self.k.mask(b,a),1,atol=1e-16)
        for scale in (1e-250,1e250):np.testing.assert_allclose(self.k.mask(a*scale,b*scale),m,atol=2e-16)
        for bad in (np.full(4,-1),np.full(4,np.inf),np.full(4,np.nan)):
            with self.assertRaises(ValueError):self.k.mask(a,bad)
        with self.assertRaises(ValueError):self.k.mask(a,b[:2])
    def test_separator_identity_short_odd_and_purity(self):
        for length in (0,1,31,2049,6503):
            x=np.random.default_rng(length).normal(0,.1,(length,2));before=x.copy();h,p,s=r.separate(x,48000,self.k)
            np.testing.assert_array_equal(before,x);np.testing.assert_allclose(h+p,x,atol=6e-17,rtol=0)
    def test_separator_channel_permutation_and_antiphase(self):
        x=np.random.default_rng(445).normal(0,.1,(7011,2));h,p,_=r.separate(x,96000,self.k)
        hh,pp,_=r.separate(x[:,::-1],96000,self.k)
        np.testing.assert_allclose(hh,h[:,::-1],atol=1e-16);np.testing.assert_allclose(pp,p[:,::-1],atol=1e-16)
        hh,pp,_=r.separate(np.c_[x[:,0],-.5*x[:,0]],48000,self.k)
        np.testing.assert_allclose(hh[:,1],-.5*hh[:,0],atol=1e-16);np.testing.assert_allclose(pp[:,1],-.5*pp[:,0],atol=1e-16)
    def test_ola_against_independent_numpy_scatter(self):
        x=np.random.default_rng(713).normal(0,.1,(101,2));window=signal.windows.hann(32,sym=False)
        s=np.array([0,7,42,100,111]);t=np.array([0,12,72,170,189]);y,w=self.k.ola(x,s,t,window,201)
        ref=np.zeros_like(y);den=np.zeros_like(w)
        for a,b in zip(s,t):
            for k in range(32):
                i,j=a-16+k,b-16+k
                if 0<=j<len(ref):
                    den[j]+=window[k]
                    if 0<=i<len(x):ref[j]+=window[k]*x[i]
        np.testing.assert_array_equal(y,ref);np.testing.assert_array_equal(w,den)
    def test_full_hybrid_unity_without_output_bypass(self):
        for length in (1,31,1025,4097):
            x=np.random.default_rng(length).normal(0,.1,(length,2))
            for mode in r.MODES:
                y,s=r.render(x,48000,mode=mode,phase_kernel=self.heap,hps_kernel=self.hps)
                np.testing.assert_allclose(y,x,atol=5e-16,rtol=0)
    def test_empty_silence_duration_and_modes(self):
        for n in (0,1,31,4097):
            for time,pitch in ((.5,.5),(.5,2),(2,.5),(2,2)):
                for mode in ('hps_heap_ola','hps_locked_pv'):
                    y,s=r.render(np.zeros((n,2)),48000,time,pitch,mode,self.heap,self.hps)
                    self.assertEqual(y.shape,(int(np.floor(n*time+.5)),2));self.assertFalse(np.any(y))
    def test_baselines_exactly_inherited(self):
        x=np.random.default_rng(990).normal(0,.1,(6001,2))
        for mode in ('locked','heap'):
            y,_=r.render(x,48000,.5,1.,mode,self.heap,self.hps);z,_=r.phase.render(x,48000,.5,1.,mode,self.heap)
            np.testing.assert_array_equal(y,z)
    def test_components_cached_and_deterministic(self):
        x=np.random.default_rng(115).normal(0,.1,(6001,2));h,p,stats=r.separate(x,48000,self.k);before=h.copy()
        a,_=r.render(x,48000,1.,.75,'hps_heap_ola',self.heap,self.hps,(h,p,stats))
        b,_=r.render(x,48000,1.,.75,'hps_heap_ola',self.heap,self.hps)
        np.testing.assert_array_equal(a,b);np.testing.assert_array_equal(h,before)
    def test_hybrid_antiphase(self):
        x=np.random.default_rng(66).normal(0,.1,8001)
        for mode in r.MODES[2:]:
            y,_=r.render(np.c_[x,-.5*x],48000,1.5,.8,mode,self.heap,self.hps)
            np.testing.assert_allclose(y[:,1],-.5*y[:,0],atol=4e-15,rtol=0)
    def test_invalid_inputs(self):
        for x in (np.full((10,2),np.nan),np.zeros((10,0)),np.zeros((10,9))):
            with self.assertRaises(ValueError):r.render(x,48000,phase_kernel=self.heap,hps_kernel=self.hps)
        for kwargs in (dict(rate=32000),dict(time=0),dict(pitch=3),dict(mode='auto')):
            options=dict(rate=48000,phase_kernel=self.heap,hps_kernel=self.hps);options.update(kwargs)
            with self.assertRaises(ValueError):r.render(np.zeros(31),**options)
if __name__=='__main__':unittest.main()
