"""Metric calibration with analytically controlled distortions, not listening votes."""
import argparse
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parent))
import audio_quality_metrics as m
import eval_audio_quality as e


class MetricsTest(unittest.TestCase):
    rate=48000

    def test_analysis_does_not_mutate_readonly_input(self):
        x,_=e.fixture('noise0',self.rate,1.)
        original=x.copy();x.flags.writeable=False
        m.temporal(x,x,self.rate);m.noise(x,self.rate,(2200,6200))
        np.testing.assert_array_equal(x,original)

    def test_attack_identity_width_and_no_leak(self):
        x,meta=e.fixture('attack',self.rate,1.)
        r=e.diagnose(x,x,meta,self.rate)
        self.assertEqual(r['width_excess_ms'],0)
        self.assertEqual(r['pre_energy_pct'],0)
        self.assertEqual(r['post_energy_pct'],0)
        self.assertLess(r['attack_width_ms'],2)

    def test_attack_blur_and_position_are_separate(self):
        x,meta=e.fixture('attack',self.rate,1.)
        delayed=np.roll(x,480,axis=0)
        a=m.attacks(x,self.rate,meta['starts'],meta['duration'])
        b=m.attacks(delayed,self.rate,meta['starts'],meta['duration'])
        self.assertAlmostEqual(b['centroid_bias_ms']-a['centroid_bias_ms'],10,places=7)
        self.assertAlmostEqual(b['attack_width_ms'],a['attack_width_ms'],places=7)
        self.assertAlmostEqual(b['centered_pre_energy_pct'],a['centered_pre_energy_pct'],places=7)
        smear=sum(np.roll(x,48*k,axis=0) for k in range(-8,9))
        c=m.attacks(smear,self.rate,meta['starts'],meta['duration'])
        self.assertGreater(c['attack_width_ms'],a['attack_width_ms']+8)
        self.assertGreater(c['centered_pre_energy_pct'],10)

    def test_known_pre_echo_is_detected(self):
        x,meta=e.fixture('attack',self.rate,1.)
        r=m.attacks(x+.5*np.roll(x,-480,axis=0),self.rate,meta['starts'],meta['duration'])
        self.assertAlmostEqual(r['pre_energy_pct'],20,places=5)

    def test_invalid_attack_window_and_missing_event(self):
        x=np.ones(48000)
        with self.assertRaises(ValueError):m.attacks(x,self.rate,[0],.002)
        with self.assertRaises(ValueError):m.attacks(x,self.rate,[],.002)
        with self.assertRaises(ValueError):m.attacks(x*0,self.rate,[.3],.002)

    def test_overlapping_partial_masks_refused(self):
        x,_=e.fixture('harmonics',self.rate,1.)
        for frequencies in (np.array([110,112]),np.array([0]),np.array([24000]),np.array([np.nan])):
            with self.assertRaises(ValueError):m.partials(x,x,self.rate,frequencies)

    def test_noise_gaussian_control_and_frozen_repeat(self):
        x,_=e.fixture('noise0',self.rate,1.)
        r=m.noise(x,self.rate,(2200,6200))
        self.assertGreater(r['noise_flatness'],.9)
        self.assertLess(r['noise_lag_peak'],.06)
        frozen=np.tile(x[:480],(200,1))
        bad=m.noise(frozen,self.rate,(2200,6200))
        self.assertGreater(bad['noise_lag_peak'],.95)
        self.assertLess(bad['noise_flatness'],r['noise_flatness']*.5)

    def test_noise_am_pumping_detected(self):
        x,_=e.fixture('noise0',self.rate,1.)
        am=(1+.8*np.sin(2*np.pi*8*np.arange(len(x))/self.rate))[:,None]
        a=m.noise(x,self.rate,(2200,6200))
        b=m.noise(x*am,self.rate,(2200,6200))
        self.assertGreater(b['noise_rms_cv'],a['noise_rms_cv']+.3)

    def test_noise_mono_duplicates_not_different(self):
        x,_=e.fixture('noise1',self.rate,1.)
        a=m.noise(x,self.rate,(2200,6200));b=m.noise(np.c_[x,-x],self.rate,(2200,6200))
        for key in a:self.assertAlmostEqual(a[key],b[key],places=10)

    def test_stereo_known_correlation_and_collapse(self):
        x,_=e.fixture('stereo70',self.rate,1.)
        r=m.stereo(x,self.rate,(2200,6200))
        self.assertAlmostEqual(r['lr_correlation'],.7,delta=.025)
        self.assertAlmostEqual(r['coherence'],.49,delta=.04)
        self.assertAlmostEqual(r['ild_db'],0,delta=.15)
        collapsed=m.stereo(np.c_[x[:,0],x[:,0]],self.rate,(2200,6200))
        self.assertAlmostEqual(collapsed['coherence'],1,places=10)
        self.assertGreater(collapsed['lr_correlation']-r['lr_correlation'],.25)

    def test_stereo_invalid_channel_and_silent_channel(self):
        with self.assertRaises(ValueError):m.stereo(np.ones((48000,1)),self.rate,(2200,6200))
        with self.assertRaises(ValueError):m.stereo(np.c_[np.ones(48000),np.zeros(48000)],self.rate,(2200,6200))

    def test_oracles_deterministic_finite(self):
        for name in e.FIXTURES:
            with self.subTest(name=name):
                x,meta=e.fixture(name,self.rate,.5);y,_=e.fixture(name,self.rate,.5)
                np.testing.assert_array_equal(x,y)
                self.assertEqual(len(x),96000)
                self.assertTrue(np.isfinite(x).all())
                json.dumps(e.diagnose(x,x,meta,self.rate),allow_nan=False)

    def test_source_cluster_bootstrap_not_pitch_as_listener(self):
        rows=[]
        for source,difference in [('one',1.),('two',3.)]:
            for pitch in range(6):
                for profile in ['transient','fuzzy']:
                    value=1+(difference if profile=='fuzzy' else 0)
                    rows.append(dict(family='exact',stem=source,condition_id=str(pitch),profile=profile,
                                     rms_shape_error_db=value,energy_transport_ms=value))
        report=e.cluster_differences(rows)
        self.assertEqual(report[0]['sources'],2)
        self.assertEqual(report[0]['conditions'],12)
        self.assertEqual(report[0]['delta_vs_transient'],2)
        self.assertEqual(report[0]['ci95'],[1.,3.])
        with self.assertRaises(ValueError):e.cluster_differences(rows+rows[:1])

    @unittest.skipUnless(os.environ.get('BOILED_EGG_PV_CLI') and os.environ.get('BOILED_EGG_MULTIRES_CLI'),
                         'real CLI integration requires two explicit executable paths')
    def test_real_cli_complete_small_matrix(self):
        with tempfile.TemporaryDirectory() as td:
            args=argparse.Namespace(source_commit='a'*40,workers=2,block=32,rates=[48000],shifts=[0,7],
                fixtures=['attack','noise0','stereo70'],profiles=list(e.e.PROFILES),
                pv_cli=Path(os.environ['BOILED_EGG_PV_CLI']),multires_cli=Path(os.environ['BOILED_EGG_MULTIRES_CLI']),
                ref_dir=None,test_dir=None,catalog=None,output=Path(td)/'result')
            r=e.run(args)
            self.assertEqual(r['synthetic_renders'],30)
            self.assertEqual(r['corpus_renders'],0)
            self.assertFalse(r['automatic_promotion'])
            self.assertEqual(e.e.fingerprint(args.output/'synthetic.csv'),r['files']['synthetic.csv'])
            with self.assertRaises(ValueError):e.run(args)
            args.output=Path(td)/'bad';args.shifts=[7,7]
            with self.assertRaises(ValueError):e.run(args)
            self.assertFalse(args.output.exists())

if __name__=='__main__':unittest.main()
