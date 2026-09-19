"""Measurement calibration and real offline CLI refusals; no MOS."""
import itertools
import json
import os
from pathlib import Path
import subprocess
import tempfile
import struct
import unittest
import numpy as np
import soundfile as sf
import offline_pv_benchmark as b

class MeasurementTests(unittest.TestCase):
    def test_tone_and_wrong_pitch(self):
        for rate in b.RATES:
            for f in (30.5,61.,122.):
                t=np.arange(round(.45*rate))/rate
                x=.2*np.sin(2*np.pi*f*t)
                self.assertLess(abs(b.tone_error(x,rate,f)),.05)
                self.assertGreater(abs(b.tone_error(x,rate,f*2**(50/1200))),49.9)
    def test_amplitude_and_extra_tone(self):
        t=np.arange(24000)/48000
        x=.2*np.sin(2*np.pi*223*t)+.1*np.cos(2*np.pi*446*t)
        amps,res=b.components(x,48000,[223.,446.]);np.testing.assert_allclose(amps,[.2,.1],atol=1e-12);self.assertLess(res,1e-25)
        _,bad=b.components(x+.1*np.sin(2*np.pi*1000*t),48000,[223.,446.]);self.assertGreater(bad,.15)
    def test_event_position_and_width(self):
        for rate in b.RATES:
            x,m=b.fixture('bursts',rate);good=b.events(x,rate,m['centers'])
            self.assertLess(max(abs(r['position_error_ms']) for r in good),.001)
            shifted=np.roll(x,round(rate*.01));bad=b.events(shifted,rate,m['centers'])
            self.assertTrue(all(abs(r['position_error_ms']-10)<.001 for r in bad))
            self.assertTrue(all(3<r['width_ms']<4 for r in good))
    def test_zero_and_nonfinite_rejected(self):
        for x in (np.zeros(1000),np.full(1000,np.nan),np.full(1000,np.inf),np.array([])):
            with self.assertRaises(ValueError):b.valid_vector(x)
    def test_fixture_and_analytic_measurement(self):
        for rate,family in itertools.product(b.RATES,b.FAMILIES):
            x,m=b.fixture(family,rate);self.assertEqual(len(x),round(.75*rate));r=b.measure(x,m,0)
            self.assertGreater(r['rms'],1e-8)
            if 'amplitudes' in r:np.testing.assert_allclose(r['amplitudes'],m['amplitudes'],atol=1e-7)
    def test_incomplete_duplicate_grid(self):
        plan={'sources':[{'metadata':{'family':'low','rate':48000}}],'shifts':[0],'engines':['offline_0'],'repeats':1,'expected_runs':1}
        row=dict(family='low',rate=48000,shift=0,engine='offline_0',repeat=0)
        b.validate_grid([row],plan)
        for rows in ([],[row,row],[{**row,'rate':96000}]):
            with self.assertRaises(ValueError):b.validate_grid(rows,plan)

class CLITests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
        self.exe=Path(os.environ['BOILED_EGG_OFFLINE_CLI']).resolve(strict=True) # missing is an error, never skip
        self.x,m=b.fixture('low',48000);self.input=self.root/'in.wav';sf.write(self.input,self.x,48000,subtype='FLOAT')
    def call(self,name,extras=(),audio=None,rate=48000):
        source=self.input
        if audio is not None:
            source=self.root/(name+'.wav');sf.write(source,audio,rate,subtype='FLOAT')
        output=self.root/name
        cmd=[str(self.exe),str(source),str(output),*extras]
        p=subprocess.run(cmd,capture_output=True,text=True,timeout=30)
        return p,output
    def opts(self):return ['--execution','offline','--allow-experimental','--iterations','0']
    def test_valid_identity_and_no_overwrite(self):
        p,out=self.call('good',self.opts());self.assertEqual(p.returncode,0,p.stderr)
        y,rate=sf.read(out/'output.wav');np.testing.assert_allclose(y,self.x,atol=1e-5)
        before=(out/'report.json').read_bytes();p,_=self.call('good',self.opts());self.assertNotEqual(p.returncode,0)
        self.assertEqual((out/'report.json').read_bytes(),before)
    def test_negative_options_and_audio_receipts(self):
        cases=[('no_opt_in',[],None,48000),('freeze',self.opts()+['--time','0'],None,48000),
          ('bad_formant',self.opts()+['--formant','harmonic'],None,48000),('bad_pitch',self.opts()+['--pitch-semitones','13'],None,48000),
          ('duplicate',self.opts()+['--iterations','8'],None,48000),('unknown',self.opts()+['--auto'],None,48000),
          ('zero',self.opts(),np.zeros(1000),48000),('nan',self.opts(),np.full(1000,np.nan),48000),
          ('stereo',self.opts(),np.c_[self.x,self.x],48000),('rate',self.opts(),self.x,44100)]
        for name,opts,audio,rate in cases:
            with self.subTest(name=name):
                p,out=self.call(name,opts,audio,rate);self.assertEqual(p.returncode,2,p.stderr)
                report=json.loads((out/'report.json').read_text());self.assertEqual(report['status'],'blocked')
                self.assertFalse((out/'output.wav').exists())

    def test_malformed_wav_layout_before_allocation(self):
        original=self.input.read_bytes()
        def wav(chunks):return b'RIFF'+struct.pack('<I',4+len(chunks))+b'WAVE'+chunks
        fmt=b'fmt '+struct.pack('<IHHIIHH',16,3,1,48000,192000,4,32)
        data=b'data'+struct.pack('<I',128)+struct.pack('<f',.2)*32
        cases={'truncated':original[:-64],
            'riff_length':original[:4]+struct.pack('<I',4)+original[8:],
            'huge_chunk':wav(fmt+b'data'+struct.pack('<I',0xfffffff0)+b'abcd'),
            'partial_sample':wav(fmt+b'data'+struct.pack('<I',3)+b'abc'+b'\x00'),
            'duplicate_data':wav(fmt+data+data),
            'duplicate_fmt':wav(fmt+fmt+data),
            'missing_fmt':wav(data)}
        for name,raw in cases.items():
            with self.subTest(name=name):
                self.input.write_bytes(raw);process,out=self.call(name,self.opts())
                self.assertEqual(process.returncode,2,process.stderr)
                self.assertEqual(json.loads((out/'report.json').read_text())['status'],'blocked')
                self.assertFalse((out/'output.wav').exists())

if __name__=='__main__':unittest.main()
