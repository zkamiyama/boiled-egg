"""Correctness checks, not fitted quality thresholds or native comparison."""
import os
import unittest
import numpy as np
import detection as d
import recombine as r

HEAP=os.environ['BOILED_EGG_PHASE_HEAP_LIBRARY']
EVENTS=os.environ['BOILED_EGG_LINKED_EVENTS_LIBRARY']

def bursts(rate,spacing=.027,level=1.):
    x=np.zeros((rate,2))
    for ch in (0,1):
        for t in (.2,.4,.6,.8):
            n=round(.002*rate);s=round((t+ch*spacing)*rate)-n//2
            local=(np.arange(n)-n//2)/rate
            x[s:s+n,ch]+=(level if ch else 1)*np.sin(np.pi*np.arange(n)/n)**2*np.cos(2*np.pi*7000*local)
    return x

class LinkedTests(unittest.TestCase):
    def test_fusion_matches_exhaustive_and_permutation(self):
        rng=np.random.default_rng(260916);f=d.Fusion(EVENTS,200)
        try:
            for n in (0,1,2,50,200):
                t=rng.integers(0,100,n).astype(float);s=rng.integers(0,5,n).astype(float)
                for gap in (0,.5,1.,3.):
                    a=f.process(t,s,gap);np.testing.assert_array_equal(a,d.fusion_reference(t,s,gap))
                    perm=rng.permutation(n);np.testing.assert_array_equal(a,f.process(t[perm],s[perm],gap))
            with self.assertRaises(ValueError):f.process([0,np.nan],[1,1],1)
        finally:f.close()
    def test_27ms_stereo_and_quieter_channel(self):
        x=bursts(48000,level=.1)
        old,_=d.detect(x,48000,'legacy40',EVENTS);new,_=d.detect(x,48000,'linked6',EVENTS)
        self.assertEqual(len(old),4);self.assertEqual(len(new),8)
        swapped,_=d.detect(x[:,::-1],48000,'linked6',EVENTS);np.testing.assert_array_equal(new,swapped)
        dual=np.repeat(x[:,0,None],2,axis=1);events,_=d.detect(dual,48000,'linked6',EVENTS);self.assertEqual(len(events),4)
    def test_detector_silence_scale_polarity_and_readonly(self):
        x=bursts(48000);x.setflags(write=False)
        expected,_=d.detect(x,48000,'linked6',EVENTS)
        for y in (x*.2,-x):np.testing.assert_array_equal(expected,d.detect(y,48000,'linked6',EVENTS)[0])
        self.assertEqual(len(d.detect(np.zeros((100,2)),48000,'linked6',EVENTS)[0]),0)
        with self.assertRaises(ValueError):d.detect([np.nan],48000,'linked6',EVENTS)
    def test_full_phase_replays_unchanged_heap(self):
        x=np.random.default_rng(5).normal(0,.1,(4099,2))
        for ratio in (.5,1.,1.5,2.):
            field=r.PhaseField(x,48000,ratio,HEAP)
            y,_=r.base.render(x,48000,time=ratio,mode='heap',kernel_path=HEAP)
            np.testing.assert_array_equal(field.apply(),y)
    def test_linearity_with_complementary_components(self):
        rng=np.random.default_rng(6);x=rng.normal(0,.1,(8001,2));q=rng.normal(0,.03,x.shape)
        for ratio in (.5,1.5,2.):
            f=r.PhaseField(x,48000,ratio,HEAP)
            np.testing.assert_allclose(f.apply(x-q)+f.apply(q),f.apply(),atol=2e-15,rtol=0)
    def test_empty_short_unity_and_linked_phase(self):
        for n in (0,1,31,2099):
            v=np.random.default_rng(n).normal(0,.1,n);x=np.c_[v,-.5*v]
            out,_=r.render_set(x,48000,1.,HEAP,EVENTS)
            for y in out.values():
                self.assertEqual(x.shape,y.shape);np.testing.assert_allclose(y,x,atol=1e-12,rtol=0)
        x=bursts(48000);x[:,1]=-.5*x[:,0]
        out,_=r.render_set(x,48000,1.5,HEAP,EVENTS)
        for y in out.values():np.testing.assert_allclose(y[:,1],-.5*y[:,0],atol=2e-12,rtol=0)
    def test_shared_control_and_gate_bounds(self):
        x=bursts(48000);out,stats=r.render_set(x,48000,2.,HEAP,EVENTS)
        self.assertLess(stats['shared_long']['recombine_error'],2e-14)
        np.testing.assert_allclose(out['heap'],out['shared_long'],atol=2e-14)
        g=r.local_gate(1000,.5,np.array([100.,107.,800.]),48000)
        self.assertTrue(np.all((g>=0)&(g<=1)))
    def test_duration_finite_and_deterministic(self):
        x=np.random.default_rng(99).normal(0,.1,(12001,2))
        a,_=r.render_set(x,96000,.5,HEAP,EVENTS);b,_=r.render_set(x,96000,.5,HEAP,EVENTS)
        for mode in r.MODES:
            self.assertEqual(a[mode].shape,(6001,2));np.testing.assert_array_equal(a[mode],b[mode])
if __name__=='__main__':unittest.main()
