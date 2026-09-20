import copy
import os
from pathlib import Path
import tempfile
import unittest
import numpy as np
from scipy import signal
import anchor_ownership as a
import comparison_contract as c
import wsola_offline as w

class Calibration(unittest.TestCase):
    def test_fixed_grid(self):
        self.assertEqual(len(a.FAMILIES)*len(a.RATES)*len(a.SHIFTS)*len(a.ARMS)*3,1080)
        for name in a.FAMILIES:
            for rate in a.RATES:
                x,meta=a.fixture(name,rate)
                self.assertEqual(len(x),rate);self.assertTrue(np.isfinite(x).all())
        with self.assertRaises(ValueError):a.assess([])
    def test_markers_not_true_metadata(self):
        x,m=a.fixture('mixed61',48000);z,n=a.fixture('missed61',48000)
        np.testing.assert_array_equal(x,z);self.assertEqual(m['centers'],n['centers']);self.assertNotEqual(m['supplied_marks'],n['supplied_marks'])
        _,o=a.fixture('offset61',48000);self.assertEqual(o['supplied_marks'][0]-m['supplied_marks'][0],96)
    def test_frequency_and_sideband_calibration(self):
        for rate in a.RATES:
            t=np.arange(rate)/rate
            for f in (20.5,30.5,48.5,194.):
                good=.2*np.sin(2*np.pi*f*t);m=a.pure(good,rate,f,.2)
                self.assertLess(abs(m['cents']),.1);self.assertTrue(a.tone_pass(m))
                bad=.2*np.sin(2*np.pi*f*2**(50/1200)*t)
                self.assertFalse(a.tone_pass(a.pure(bad,rate,f,.2)))
                mixed=good+.1*np.sin(2*np.pi*(f+300)*t)
                self.assertGreater(a.pure(mixed,rate,f,.2)['unexplained_energy'],.1)
    def test_event_shift_missing_and_energy(self):
        x,m=a.fixture('bursts_sparse',48000);sos=signal.butter(4,1000,btype='highpass',fs=48000,output='sos');x=signal.sosfiltfilt(sos,x)
        good=a.event_windows(x,x,48000,m['centers']);self.assertTrue(all(e['pass'] for e in good))
        bad=np.concatenate((np.zeros(480),x[:-480]));result=a.event_windows(bad,x,48000,m['centers'])
        for g,b in zip(good,result):self.assertAlmostEqual(b['position_ms']-g['position_ms'],10,places=4);self.assertFalse(b['pass'])
        missing=a.event_windows(np.zeros_like(x),x,48000,m['centers']);self.assertTrue(all(not e['pass'] for e in missing))
        quiet=a.event_windows(x*.1,x,48000,m['centers']);self.assertTrue(all(not e['pass'] for e in quiet))
    def test_deterministic_wav_and_pcm(self):
        x,_=a.fixture('tone61',48000)
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'x.wav';p.write_bytes(a.wav_bytes(x,48000));got,rate=w.read_input(p)
            np.testing.assert_array_equal(got,x);self.assertEqual(rate,48000)
            self.assertEqual(a.wav_bytes(x,48000),a.wav_bytes(x,48000))
            changed=x.copy();changed[100]+=.01;self.assertNotEqual(a.pcm_hash(x),a.pcm_hash(changed))
    def test_complete_failed_grid_is_blocked_not_missing_summary(self):
        import itertools
        rows=[dict(zip(('family','rate','shift','arm','repeat'),key),status='failed',errors=['injected'])
              for key in itertools.product(a.FAMILIES,a.RATES,a.SHIFTS,a.ARMS,range(a.REPEATS))]
        result=a.assess(rows)
        self.assertFalse(result['integrity_pass']);self.assertIsNone(result['profiles']);self.assertIsNone(result['quality_selection'])
        for row in rows:row['status']='rejected_uncovered'
        self.assertFalse(a.assess(rows)['integrity_pass'])
    def test_quality_not_execution(self):
        m=dict(cents=0,amplitude_error_db=0,unexplained_energy=0);self.assertTrue(a.tone_pass(m))
        for k,v in [('cents',50),('amplitude_error_db',3),('unexplained_energy',.1)]:
            wrong=m.copy();wrong[k]=v;self.assertFalse(a.tone_pass(wrong))

class NativeControls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.path=Path(os.environ['BE_ANCHOR_LIBRARY']).resolve(strict=True);cls.native=a.Native(cls.path,c.fingerprint(cls.path))
    def test_identity_and_empty_mark_equivalence(self):
        x,_=a.fixture('tone61',48000)
        for mode in ('free','snap','owned'):
            y,info=self.native.render(x,48000,0,mode,[]);np.testing.assert_array_equal(x,y);self.assertTrue(info['unity_bypass'])
        y,_=self.native.render(x,48000,12,'free',[])
        for mode in ('snap','owned'):np.testing.assert_array_equal(y,self.native.render(x,48000,12,mode,[])[0])
    def test_marker_trace_and_repeat(self):
        x,m=a.fixture('mixed61',48000);marks=m['supplied_marks']
        y,info=self.native.render(x,48000,12,'owned',marks)
        z,again=self.native.render(x,48000,12,'owned',marks)
        np.testing.assert_array_equal(y,z);self.assertEqual(info['trace'],again['trace'])
        for g in info['trace']:
            if g['anchor_index']>=0:
                mark=marks[g['anchor_index']];self.assertEqual(g['source_center']-g['output_center'],mark-2*mark)
    def test_dense_ownership_rejection_is_not_silence_success(self):
        x,m=a.fixture('dense83',48000)
        with self.assertRaisesRegex(a.KernelError,'4'):
            self.native.render(x,48000,12,'owned',m['supplied_marks'])
    def test_bad_marks_hash_and_domain(self):
        x,_=a.fixture('tone61',48000)
        with self.assertRaises(ValueError):a.Native(self.path,'0'*64)
        for marks in ([0],[999999],[12000,12000],[12000,11000],[12000,12001],[1.5],[2**80]):
            with self.assertRaises(ValueError):self.native.render(x,48000,12,'owned',marks)
        with self.assertRaises(ValueError):self.native.render(x,48000,12,'free',[12000])
        with self.assertRaises(ValueError):self.native.render(np.zeros_like(x),48000,12,'owned',[])
        with self.assertRaises(ValueError):self.native.render(x,48000,float('nan'),'owned',[])
        with self.assertRaises(ValueError):self.native.render(np.stack([x,x]),48000,12,'owned',[])

if __name__=='__main__':unittest.main()
