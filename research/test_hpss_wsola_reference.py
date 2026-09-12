from __future__ import annotations
import sys
import unittest
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parent))
from hpss_wsola_reference import audio_array, output_frames, separate, overlap_add, wsola

class HybridReferenceTest(unittest.TestCase):
    def setUp(self):
        self.x = np.random.default_rng(421).normal(0, .1, (8192, 2))

    def test_hpss_reconstruction(self):
        h, p = separate(self.x)
        np.testing.assert_allclose(h+p, self.x, atol=1e-15, rtol=0)

    def test_hpss_antiphase(self):
        x = np.c_[self.x[:, 0], -self.x[:, 0]]
        h, p = separate(x)
        self.assertGreater(float(np.std(h)), .001)
        np.testing.assert_allclose(h[:, 0], -h[:, 1], atol=1e-14)
        np.testing.assert_allclose(p[:, 0], -p[:, 1], atol=1e-14)

    def test_hpss_stereo_linkage(self):
        x = np.c_[self.x[:, 0], .37*self.x[:, 0]]
        h, p = separate(x)
        np.testing.assert_allclose(h[:, 1], .37*h[:, 0], atol=1e-14)
        np.testing.assert_allclose(p[:, 1], .37*p[:, 0], atol=1e-14)

    def test_short_and_silent_hpss(self):
        for n in (1, 13, 255, 2048):
            h,p = separate(np.zeros((n, 2)))
            self.assertEqual(h.shape, (n, 2));self.assertFalse(np.any(h+p))

    def test_ola_identity(self):
        np.testing.assert_allclose(overlap_add(self.x, 1), self.x, atol=1e-14)

    def test_wsola_identity(self):
        np.testing.assert_allclose(wsola(self.x, 1), self.x, atol=1e-14)

    def test_duration_and_peak_bound(self):
        for ratio in (.25, .5, .8, 1, 1.25, 2, 4):
            for algorithm in (overlap_add, wsola):
                y=algorithm(self.x,ratio)
                self.assertEqual(y.shape, (output_frames(len(self.x),ratio),2))
                self.assertTrue(np.isfinite(y).all())
                self.assertLessEqual(np.max(np.abs(y)), np.max(np.abs(self.x))+1e-12)

    def test_wsola_antiphase_linkage(self):
        x=np.c_[self.x[:,0], -self.x[:,0]]
        y=wsola(x, 1.5)
        np.testing.assert_allclose(y[:,0], -y[:,1], atol=1e-14)

    def test_short_silence(self):
        for n in (1, 13, 255):
            for ratio in (.25, 1, 4):
                for algorithm in (overlap_add,wsola):
                    y=algorithm(np.zeros((n, 1)),ratio)
                    self.assertEqual(len(y),output_frames(n,ratio))
                    self.assertFalse(np.any(y))

    def test_deterministic(self):
        np.testing.assert_array_equal(wsola(self.x,1.5),wsola(self.x,1.5))

    def test_invalid_audio(self):
        for x in ([],[np.nan],[np.inf],np.zeros((5,0)),np.zeros((1,2,3))):
            with self.assertRaises(ValueError): audio_array(x)

    def test_invalid_parameters(self):
        for ratio in (0, -.5, float('nan'),float('inf'),4.01):
            with self.assertRaises(ValueError): overlap_add(self.x,ratio)
        for kw in (dict(fft_size=31),dict(hop=2048),dict(kernel=4)):
            with self.assertRaises(ValueError): separate(self.x,**kw)
        for kw in (dict(hop=300),dict(frame=31),dict(tolerance=-1)):
            with self.assertRaises(ValueError): overlap_add(self.x,1.5,**kw)

if __name__=='__main__':unittest.main()
