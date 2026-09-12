"""Standalone calibration of metrics; no renderer or dataset dependency."""
import sys
import unittest
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parent))
import audio_quality_metrics as m


class MetricCalibrationTest(unittest.TestCase):
    rate=48000

    def test_identity_temporal_zero_and_gain_invariance(self):
        x=np.zeros(48000);x[12000:14400]=1
        for gain in (.1,1.,2.):
            r=m.temporal(x,x*gain,self.rate)
            self.assertLess(r['energy_transport_ms'],1e-10)
            self.assertLess(r['rms_shape_error_db'],1e-10)
            self.assertAlmostEqual(r['rms_gain_db'],20*np.log10(gain),places=8)

    def test_transport_detects_exact_10ms_shift(self):
        x=np.zeros(48000);x[12000:12480]=1
        r=m.temporal(x,np.roll(x,480),self.rate)
        self.assertAlmostEqual(r['energy_transport_ms'],10.,places=8)
        self.assertGreater(r['rms_shape_error_db'],50)

    def test_antiphase_not_cancelled(self):
        x=np.zeros(48000);x[12000:12480]=1;y=np.roll(x,480)
        self.assertEqual(m.temporal(x,y,self.rate),m.temporal(np.c_[x,-x],np.c_[y,-y],self.rate))

    def test_final_partial_bin_not_dropped(self):
        x=np.zeros(48001);x[-1]=1
        r=m.temporal(x,x,self.rate)
        self.assertEqual(r['energy_transport_ms'],0)
        self.assertEqual(r['active_bins'],1)

    def test_silence_nonfinite_and_bad_shapes_rejected(self):
        for x in (np.zeros(48000),np.full(48000,np.nan),np.array([]),np.ones((2,3,4))):
            with self.assertRaises(ValueError):m.temporal(x,x,self.rate)
        with self.assertRaises(ValueError):m.temporal(np.ones(48000),np.ones(47999),self.rate)
        with self.assertRaises(ValueError):m.temporal(np.ones(48000),np.ones(48000),0)

    def test_partial_identity_phase_and_level_invariance(self):
        t=np.arange(96000)/self.rate
        f=np.array([1000.,2300.])
        x=np.sin(2*np.pi*1000*t)+.5*np.sin(2*np.pi*2300*t)
        y=2*(np.cos(2*np.pi*1000*t)+.5*np.cos(2*np.pi*2300*t))
        r=m.partials(x,y,self.rate,f)
        self.assertLess(r['partial_envelope_error_db'],1e-6)
        self.assertLess(r['off_partial_energy_db'],-35)

    def test_wrong_pitch_and_missing_partial_detected(self):
        t=np.arange(96000)/self.rate
        x=np.sin(2*np.pi*1000*t)+.5*np.sin(2*np.pi*2300*t)
        detuned=np.sin(2*np.pi*1020*t)+.5*np.sin(2*np.pi*2320*t)
        r=m.partials(detuned,x,self.rate,np.array([1000.,2300.]))
        self.assertGreater(r['off_partial_energy_db'],-1)
        missing=m.partials(np.sin(2*np.pi*1000*t),x,self.rate,np.array([1000.,2300.]))
        self.assertGreater(missing['partial_envelope_error_db'],20)

    def test_stereo_signed_phase_and_channel_balance(self):
        x=np.random.default_rng(20260913).standard_normal(96000)*.1
        r=m.stereo(np.c_[x,-.5*x],self.rate,(2200,6200))
        self.assertAlmostEqual(r['lr_correlation'],-1,places=10)
        self.assertAlmostEqual(r['coherence'],1,places=10)
        self.assertAlmostEqual(r['ild_db'],20*np.log10(.5),places=10)

if __name__=='__main__':unittest.main()
