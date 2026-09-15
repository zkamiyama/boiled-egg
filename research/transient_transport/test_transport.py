import os
import unittest
import numpy as np
import transport as t
import fixtures as f
import metrics as m
from native import Mapper

class TransportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.kernel=os.environ['BOILED_EGG_PHASE_HEAP_LIBRARY']
        cls.mapper=Mapper(os.environ['BOILED_EGG_TRANSIENT_MAP_LIBRARY'])

    def test_complement_and_read_only(self):
        for n in (0,1,31,301,16001):
            x=np.random.default_rng(n).normal(0,.1,(n,2));x.flags.writeable=False
            h,p,stats=t.separate(x,48000)
            np.testing.assert_allclose(h+p,x,atol=1e-15,rtol=0)
            self.assertEqual(h.shape,x.shape)

    def test_map_knots_unit_slope_and_monotonicity(self):
        for r in (.5,1,1.5,2):
            for anchors in ([],[1,100,199],[50,51,52,120]):
                a,b=t.anchor_knots(200,r,anchors,48000)
                self.assertTrue(np.all(np.diff(a)>0));self.assertTrue(np.all(np.diff(b)>0))
                np.testing.assert_allclose(self.mapper(r*np.asarray(anchors),a,b),anchors,atol=1e-10)
                for i in range(len(anchors)):
                    self.assertAlmostEqual((b[3*i+3]-b[3*i+1])/(a[3*i+3]-a[3*i+1]),1.,places=10)
                self.assertEqual(a[-1],r*200);self.assertEqual(b[-1],200)

    def test_cpp_random_oracle(self):
        rng=np.random.default_rng(260915)
        for n in (2,3,17,99):
            for _ in range(20):
                a=np.cumsum(rng.uniform(.01,100,n));b=np.cumsum(rng.uniform(.01,100,n))
                q=rng.uniform(-100,a[-1]+100,257)
                np.testing.assert_array_equal(self.mapper(q,a,b),t.map_positions(q,a,b))

    def test_invalid_maps(self):
        for a,b,q in (([0,0],[0,1],[0]),([0,1],[1,0],[0]),([0,1],[0,1],[np.nan]),([0,np.inf],[0,1],[0])):
            with self.assertRaises(ValueError):self.mapper(q,a,b)
        for anchors in ([0],[200],[50,49],[np.nan]):
            with self.assertRaises(ValueError):t.anchor_knots(200,1.5,anchors,48000)

    def test_identity_all_modes_and_short_input(self):
        for n in (0,1,31,301,8001):
            x=np.random.default_rng(n+7).normal(0,.1,(n,2))
            for mode in t.MODES:
                y,_=t.render(x,48000,1.,mode,self.kernel,self.mapper)
                np.testing.assert_allclose(y,x,atol=2e-14,rtol=0)

    def test_duration_silence_and_finite(self):
        for r in (.5,1.5,2):
            for n in (1,31,401):
                for mode in t.MODES:
                    y,_=t.render(np.zeros((n,2)),48000,r,mode,self.kernel,self.mapper)
                    self.assertEqual(y.shape,(int(np.floor(n*r+.5)),2));self.assertFalse(np.any(y))

    def test_linked_antiphase(self):
        x=np.random.default_rng(18).normal(0,.1,9001)
        for mode in t.MODES:
            y,_=t.render(np.c_[x,-.5*x],48000,1.5,mode,self.kernel,self.mapper)
            np.testing.assert_allclose(y[:,1],-.5*y[:,0],atol=2e-13,rtol=0)

    def test_permutation_and_input_purity(self):
        x=np.random.default_rng(11).normal(0,.1,(7000,2));x[:,1]*=.4;before=x.copy();x.flags.writeable=False
        for mode in ('split_heap_ola','split_heap_anchor'):
            y,_=t.render(x,48000,.5,mode,self.kernel,self.mapper)
            z,_=t.render(x[:,::-1],48000,.5,mode,self.kernel,self.mapper)
            np.testing.assert_allclose(z[:,::-1],y,atol=2e-12,rtol=0)
        np.testing.assert_array_equal(x,before)

    def test_stable_repeated_output(self):
        x,_=f.make('mixed',48000)
        a,sa=t.render(x,48000,1.5,'split_heap_anchor',self.kernel,self.mapper)
        b,sb=t.render(x,48000,1.5,'split_heap_anchor',self.kernel,self.mapper)
        np.testing.assert_array_equal(a,b);self.assertEqual(sa,sb)

    def test_anchor_detection(self):
        x=np.zeros((48000,2));x[12000,0]=1;x[36000,1]=.9
        a=t.detect_anchors(x,48000)
        self.assertEqual(len(a),2);np.testing.assert_allclose(a,[12000,36000],atol=48)
        self.assertEqual(len(t.detect_anchors(np.zeros_like(x),48000)),0)

    def test_oracle_metric_identity_gain_and_delay(self):
        y,meta=f.make('attack2',48000,1.5)
        same=m.events(y,y,48000,**meta)
        self.assertEqual(same['width_error_ms'],0);self.assertEqual(same['centroid_error_ms'],0)
        louder=m.events(2*y,y,48000,**meta)
        self.assertAlmostEqual(louder['event_energy_abs_db'],20*np.log10(2),places=10)
        delayed=np.roll(y,96,axis=0);r=m.events(delayed,y,48000,**meta)
        self.assertAlmostEqual(r['centroid_error_ms'],2.,places=8)
        self.assertGreater(r['outside_support_fraction'],.95)

    def test_oracle_gate_not_scaled(self):
        for name in ('attack2','attack20','noise_bursts'):
            x,meta=f.make(name,48000);y,other=f.make(name,48000,2.)
            self.assertEqual(meta['duration'],other['duration'])
            self.assertAlmostEqual(np.sum(x*x),np.sum(y*y),places=12)

    def test_lowtone_oracle(self):
        y,_=f.make('low55',48000,1.5)
        self.assertLess(m.tone_frequency(y,48000,55.)['cents_error'],.01)

    def test_overlap_covariance_oracle(self):
        w=np.hanning(17)[:-1]**2
        synth=np.arange(0,40,4)
        for centers in (synth.copy(),2*synth,synth//2,synth+np.array([0,0,0,2,2,2,4,4,4,4])):
            den=t.overlap_weights(synth,centers,w,64,True)
            expected=np.zeros(64)
            for sample in range(64):
                groups={}
                for s,c in zip(synth,centers):
                    if s<=sample<s+len(w):
                        source=int(c+sample-s)
                        groups[source]=groups.get(source,0.)+w[sample-s]
                expected[sample]=np.sqrt(sum(v*v for v in groups.values()))
            np.testing.assert_allclose(den,expected,rtol=1e-15,atol=1e-15)

    def test_unit_power_noise_not_gain_fit(self):
        x=np.random.default_rng(717).normal(0,.1,(48000,1))
        for ratio in (.5,1.5,2):
            y,_=t.ola(x,48000,ratio,unit_power=True)
            gain=10*np.log10(np.mean(y[2000:-2000]**2)/.01)
            self.assertLess(abs(gain),.25)

    def test_invalid_audio_controls(self):
        for x in (np.full(100,np.nan),np.zeros((10,0)),np.zeros((10,9))):
            with self.assertRaises(ValueError):t.render(x,48000,kernel=self.kernel)
        for r in (0,3,np.nan):
            with self.assertRaises(ValueError):t.render(np.ones(10),48000,r,kernel=self.kernel)
        with self.assertRaises(ValueError):t.render(np.ones(10),12345,kernel=self.kernel)

if __name__=='__main__':unittest.main()
