"""Negative controls for the previously declared per-cell stopping rules."""
import copy
import unittest
from offline_pv_assess import paired_failures, finite, assess

class StopTests(unittest.TestCase):
    def cell(self):
        return dict(family='bursts',rendered=True,repeat_pcm_equal=True,
                    metrics=dict(rms=.1,peak=.2,events=[dict(position_error_ms=2.,width_ms=10.) for _ in range(2)]))
    def test_paired_pass_and_position_absolute(self):
        a=self.cell();b=copy.deepcopy(a);self.assertEqual(paired_failures(a,b),[])
        a['metrics']['events'][0]['position_error_ms']=-4.
        self.assertEqual(paired_failures(a,b),['event0 absolute position error worsened >1ms'])
    def test_width_and_no_average_cancellation(self):
        a=self.cell();b=copy.deepcopy(a)
        a['metrics']['events'][0]['width_ms']=12.01;a['metrics']['events'][1]['width_ms']=1.
        self.assertEqual(paired_failures(a,b),['event0 energy width worsened >20%'])
    def test_pitch_zero_and_incomplete(self):
        a=self.cell();b=copy.deepcopy(a);a['family']='low';a['metrics']['pitch_error_cents']=-5.1
        self.assertEqual(paired_failures(a,b),['pitch exceeds 5 cents'])
        a['metrics']['pitch_error_cents']=0;a['metrics']['rms']=0
        self.assertEqual(paired_failures(a,b),['silent output'])
        a['rendered']=False;self.assertTrue(paired_failures(a,b))
    def test_nonfinite_missing_grid(self):
        for x in (float('nan'),float('inf'),None,True):
            with self.assertRaises(ValueError):finite(x)
        with self.assertRaises(ValueError):assess(dict(schema='boiled-egg.offline-pv-screen.v1',rows=[],cells=[]))

if __name__=='__main__':unittest.main()
