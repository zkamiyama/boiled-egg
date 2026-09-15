"""Actual evaluation-only R2/R3 C-API checks. Requires an explicit local library."""
import os
from pathlib import Path
import unittest
import numpy as np
from comparison_contract import Request
from calibrate_external import pitch_cents
from reference_rubberband import Reference

class ReferenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.reference=Reference(Path(os.environ['BOILED_EGG_RB_LIBRARY']))

    def test_invalid_audio_and_configuration_rejected(self):
        ref=self.reference
        for x in (np.empty((0,1)),np.zeros((100,3)),np.full((100,1),np.nan)):
            with self.assertRaises(ValueError):ref.render(x,48000,Request())
        for kwargs in ({'engine':1},{'formant':'harmonic'},{'block':0}):
            with self.assertRaises(ValueError):ref.render(np.zeros((100,1)),48000,Request(),**kwargs)

    def test_both_requested_engines_and_float_duration(self):
        x=np.zeros((48000,1),dtype=np.float32)
        for engine in (2,3):
            y,meta=self.reference.render(x,48000,Request(.8),engine=engine)
            self.assertEqual(meta['engine'],engine)
            self.assertEqual(len(y),38400)
            self.assertEqual(y.dtype,np.float32)
            self.assertFalse(np.any(y))

    def test_r3_calibrated_operations_and_input_purity(self):
        t=np.arange(96000)/48000;x=(.125*np.sin(2*np.pi*440*t))[:,None];before=x.copy()
        x.setflags(write=False)
        for duration,shift in ((.8,0),(1.25,0),(1,-7),(1,7)):
            request=Request.from_semitones(duration,shift)
            y,meta=self.reference.render(x,48000,request,engine=3)
            self.assertEqual(len(y),request.target_frames(len(x)))
            self.assertLess(abs(pitch_cents(y[:,0],48000,440*request.pitch_ratio)),5.)
            np.testing.assert_array_equal(x,before)

    def test_formant_flag_is_independent_of_engine_selection(self):
        t=np.arange(48000)/48000;x=(.1*np.sin(2*np.pi*220*t))[:,None]
        for formant in ('off','preserved'):
            y,meta=self.reference.render(x,48000,Request(1,1.5),engine=3,formant=formant)
            self.assertEqual(meta['engine'],3)
            self.assertEqual(bool(int(meta['options_hex'],16)&0x01000000),formant=='preserved')
            self.assertEqual(y.shape,x.shape)
            self.assertTrue(np.isfinite(y).all())
        # Flag routing is not a spectral-envelope quality assertion.

if __name__=='__main__':unittest.main()
