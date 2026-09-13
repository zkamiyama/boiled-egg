"""Calibrations for the offline selective-window experiment, not hearing scores."""
import sys
import unittest
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parent))
import adaptive_nsgt as n
from eval_audio_quality import fixture

class AdaptiveTest(unittest.TestCase):
    rate=48000
    def test_identity_waveform(self):
        x=np.random.default_rng(331).normal(0,.1,(9600,2))
        for cfg in (n.Config(),n.Config(adapt=False),n.Config(formant='harmonic')):
            y,meta=n.render(x,self.rate,cfg=cfg)
            self.assertEqual(y.shape,x.shape)
            self.assertLess(np.max(np.abs(y-x)),1e-10)
            self.assertEqual(meta['detected_events'],0)
    def test_deterministic(self):
        x,_=fixture('attack',self.rate,1.)
        a,ma=n.render(x,self.rate,pitch_ratio=2)
        b,mb=n.render(x,self.rate,pitch_ratio=2)
        np.testing.assert_array_equal(a,b);self.assertEqual(ma,mb)
        self.assertGreater(ma['detected_events'],0)
        self.assertGreater(ma['adapted_frames'],0)
    def test_linked_antiphase_no_silent_leak(self):
        x,_=fixture('harmonics',self.rate,1.)
        a=np.c_[x[:,0],-.5*x[:,0],np.zeros(len(x))]
        for p in (.5,2.):
            y,_=n.render(a,self.rate,pitch_ratio=p)
            self.assertLess(np.max(np.abs(y[:,1]+.5*y[:,0])),1e-10)
            np.testing.assert_array_equal(y[:,2],0)
    def test_silence_and_empty(self):
        for length in (0,9600):
            x=np.zeros((length,2));y,meta=n.render(x,self.rate,pitch_ratio=2)
            np.testing.assert_array_equal(x,y)
            self.assertEqual(meta['detected_events'],0)
    def test_duration_and_coverage(self):
        x=np.random.default_rng(42).normal(0,.03,(10003,1))
        for t in (.5,.75,1.,1.5,2.):
            for p in (.5,1.,2.):
                y,meta=n.render(x,self.rate,t,p)
                self.assertEqual(y.shape,(int(np.floor(len(x)*t+.5)),1))
                self.assertGreater(meta['min_weight'],1e-8)
                self.assertTrue(np.isfinite(y).all())
    def test_one_sample_lengths(self):
        for length in (1,2,3,31):
            x=np.ones((length,1))*.1
            for t in (.5,1.,2.):
                for p in (.5,1.,2.):
                    y,_=n.render(x,self.rate,t,p)
                    self.assertEqual(len(y),int(np.floor(length*t+.5)))
                    self.assertTrue(np.isfinite(y).all())
    def test_fixed_control_disables_detector(self):
        x,_=fixture('attack',self.rate,1.)
        _,meta=n.render(x,self.rate,pitch_ratio=2,cfg=n.Config(adapt=False))
        self.assertEqual(meta['detected_events'],0)
        self.assertEqual(meta['min_window'],meta['max_window'])
    def test_input_not_mutated(self):
        x=np.random.default_rng(82).normal(0,.1,(12000,1));old=x.copy()
        n.render(x,self.rate,1.5,1.2,n.Config(formant='harmonic'))
        np.testing.assert_array_equal(x,old)
    def test_unsupported_configs(self):
        x=np.ones((4800,1))
        for kwargs in (dict(rate=123),dict(time_ratio=float('nan')),dict(pitch_ratio=0),
                       dict(cfg=n.Config(long_window=1000)),dict(cfg=n.Config(hop=0)),
                       dict(cfg=n.Config(formant_ratio=1.5)),dict(cfg=n.Config(formant='unknown'))):
            args=dict(rate=self.rate);args.update(kwargs)
            with self.assertRaises(ValueError):n.render(x,**args)
        with self.assertRaises(ValueError):n.render(np.full((4800,1),np.nan),self.rate)
    def test_common_fft_window_support(self):
        for length in (64,512,2048):
            w=n.window(length,4096)
            self.assertEqual(len(w),4096)
            self.assertEqual(np.argmax(w),2048)
            self.assertAlmostEqual(w.sum(),length/2.)
            np.testing.assert_array_equal(w[:(4096-length)//2],0)
    def test_mixed_derivative_impulse_vs_tone(self):
        x=np.zeros((48000,1));x[24000]=1
        _,_,centers,score=n.percussion(x,self.rate,4096,2048,256,n.Config())
        self.assertGreater(score[(centers>23500)&(centers<24500)].max(),.9)
        tone=np.sin(2*np.pi*937.5*np.arange(48000)/48000)[:,None]
        _,_,centers,score=n.percussion(tone,self.rate,4096,2048,256,n.Config())
        self.assertLess(score[(centers>2048)&(centers<45952)].max(),.05)
    def test_formant_pitch_cancellation(self):
        x,_=fixture('vowel_a',self.rate,1.)
        for p in (.5,2.):
            a,_=n.render(x,self.rate,pitch_ratio=p,cfg=n.Config(formant='off'))
            b,_=n.render(x,self.rate,pitch_ratio=p,cfg=n.Config(formant='harmonic',formant_ratio=p))
            np.testing.assert_array_equal(a,b)

if __name__=='__main__':unittest.main()
