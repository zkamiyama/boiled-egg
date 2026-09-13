"""Calibration and pairing tests. Synthetic scores are test fixtures only."""
import copy,sys,unittest
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parent))
import compare_zplane_outputs as c

class ComparisonTests(unittest.TestCase):
    def setUp(self):
        self.rate=16000;t=np.arange(32000)/self.rate
        self.x=(.2*np.sin(2*np.pi*220*t)+.1*np.sin(2*np.pi*440*t))[:,None]
    def test_identity(self):
        r=c.tsm_metrics(self.x,self.x,self.rate)
        for k in ('envelope_rmse_db','rms_shape_db','spectral_distance_db','spectral_convergence'):self.assertLess(abs(r[k]),1e-10)
        self.assertAlmostEqual(r['onset_corr'],1);self.assertAlmostEqual(r['chroma_corr'],1)
    def test_gain_invariance(self):
        r=c.tsm_metrics(self.x,2*self.x,self.rate)
        for k in ('rms_shape_db','spectral_distance_db','spectral_convergence'):self.assertLess(abs(r[k]),1e-9)
    def test_wrong_pitch_detected(self):
        t=np.arange(32000)/self.rate;y=(.2*np.sin(2*np.pi*330*t)+.1*np.sin(2*np.pi*660*t))[:,None]
        r=c.tsm_metrics(self.x,y,self.rate)
        self.assertGreater(r['spectral_distance_db'],5);self.assertLess(r['chroma_corr'],.5)
    def test_input_immutable(self):
        before=self.x.copy();c.tsm_metrics(self.x,self.x,self.rate);np.testing.assert_array_equal(self.x,before)
    def test_nonfinite_and_explicit_mono_contract(self):
        for a in (self.x*np.nan,np.c_[self.x,-self.x]):
            with self.assertRaises(ValueError):c.stretch_features(a,self.rate)
    def test_silence_rejected(self):
        with self.assertRaises(ValueError):c.tsm_metrics(np.zeros_like(self.x),self.x,self.rate)
    def rows(self):
        r=[]
        for source in ('a','b'):
            for index in range(3):
                for profile,value in [('provided_elastique',2.),('transient',1.)]:
                    r.append(dict(operation='time_stretch',scope='target',source=source,condition=source+str(index),profile=profile,**{k:value for k in c.DIRECTIONS}))
        return r
    def test_pairing_directions_and_clusters(self):
        results=c.summarize(self.rows(),['transient'])
        for r in results:
            self.assertEqual(r['sources'],2);self.assertEqual(r['n'],6);self.assertEqual(r['delta'],-1.)
            self.assertEqual(r['wins'],6 if c.DIRECTIONS[r['metric']]<0 else 0)
            self.assertEqual(r['ci95'],[-1.,-1.])
    def test_duplicate_and_missing_pairs_rejected(self):
        r=self.rows()
        with self.assertRaises(ValueError):c.summarize(r+r[:1],['transient'])
        with self.assertRaises(KeyError):c.summarize(r[:-1],['transient'])
    def test_bootstrap_reproducible(self):
        r=self.rows();r[-1]['onset_corr']=.8
        self.assertEqual(c.summarize(r,['transient']),c.summarize(r,['transient']))
    def test_scope_never_pooled(self):
        r=self.rows()
        for row in r:
            if row['source']=='b':row['scope']='stress'
        summary=c.summarize(r,['transient'])
        self.assertEqual({v['scope'] for v in summary},{'target','stress'})
        self.assertTrue(all(v['n']==3 and v['sources']==1 for v in summary))
if __name__=='__main__':unittest.main()
