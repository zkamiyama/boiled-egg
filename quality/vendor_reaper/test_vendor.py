import copy,itertools,json,tempfile,unittest
from pathlib import Path
import numpy as np
import soundfile as sf
import contract as h
import study as s

class Calibration(unittest.TestCase):
 def test_fixed_grid(self):
  self.assertEqual(len(s.FAMILIES)*len(s.RATES)*len(s.SHIFTS)*len(s.ENGINES)*3,720)
  for family,rate in itertools.product(s.FAMILIES,s.RATES):
   x,m=s.fixture(family,rate);self.assertEqual(len(x),rate*2);self.assertTrue(np.isfinite(x).all());self.assertGreater(np.mean(x*x),1e-8)
 def test_unrestricted_pitch_and_energy(self):
  x,meta=s.fixture('low61',48000);good=s.measure(x,meta,0)['tone'];self.assertTrue(good['passed'])
  wrong=s.measure(x,meta,12)['tone'];self.assertLess(wrong['cents'],-1190);self.assertFalse(wrong['passed'])
  for bad in (x*0,x[:-1],x*np.nan):
   with self.assertRaises(ValueError):s.measure(bad,meta,0)
 def test_analytic_envelope_oracle(self):
  for family in ('vowel120','vowel220'):
   x,meta=s.fixture(family,48000);metric=s.measure(x,meta,0)['formant']
   self.assertLess(metric['preserved_target_rmse_db'],1e-4);self.assertLess(metric['off_target_rmse_db'],1e-4)
   t=np.arange(96000)/48000;k=np.arange(1,31);pitch=2.;amps=.03*s.envelope(k*meta['f0']*pitch)/k**.7
   y=sum(a*np.sin(2*np.pi*n*meta['f0']*pitch*t+.29*n) for n,a in zip(k,amps))
   result=s.measure(y,meta,12)['formant'];self.assertLess(result['preserved_target_rmse_db'],1e-8)
   self.assertGreater(result['off_target_rmse_db'],2)
 def test_event_position_and_missing(self):
  rate=48000;x=np.zeros(rate*2);x[24000]=1
  a=s.event_metric(x,rate,[.5])[0];self.assertAlmostEqual(a['position_ms'],0)
  b=s.event_metric(np.roll(x,480),rate,[.5])[0];self.assertAlmostEqual(b['position_ms'],10)
  self.assertTrue(s.event_metric(x*0,rate,[.5])[0]['missing'])
 def test_explicit_mode_and_no_overwrite(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'input.wav';sf.write(p,np.ones(100)*.1,48000,subtype='FLOAT');out=Path(d)/'output.wav'
   with self.assertRaises(ValueError):h.job('x',p,out,48000,100,0,'auto')
   with self.assertRaises(ValueError):h.job('x',p,out,48000,100,99,'elastique_soloist')
   out.write_text('sentinel')
   with self.assertRaises(ValueError):h.job('x',p,out,48000,100,0,'elastique_soloist')
   self.assertEqual(out.read_text(),'sentinel')
 def test_lua_serialization(self):
  self.assertEqual(h.lua('a"b\\c'),'"a\\"b\\\\c"')
  for x in ('line\nbreak',float('nan'),None):
   with self.assertRaises(ValueError):h.lua(x)
 def grid(self,status='failed'):
  return [dict(zip(('family','rate','shift','engine','repeat'),k),status=status,error='injected') for k in itertools.product(s.FAMILIES,s.RATES,s.SHIFTS,s.ENGINES,range(3))]
 def test_complete_grid_failure_is_not_success(self):
  r=s.assess(self.grid());self.assertFalse(r['integrity_pass']);self.assertEqual(r['completed'],0);self.assertIsNone(r['profiles'])
 def test_incomplete_duplicate_grid(self):
  g=self.grid()
  for bad in ([],g[:-1],g+[g[0]]):
   with self.assertRaises(ValueError):s.assess(bad)
 def test_fabricated_receipts_fail_closed(self):
  g=self.grid('complete');self.assertFalse(s.assess(g)['integrity_pass'])
  for row in g:row.update(pcm_sha256='0'*64,metrics={'peak':1.,'rms':.1})
  self.assertFalse(s.assess(g)['integrity_pass'])
  for row in g:row['metrics']['rms']=0
  self.assertFalse(s.assess(g)['integrity_pass'])
 def test_wrong_host_identity_fails_before_audio(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'receipt.json';p.write_text(json.dumps({'status':'complete','id':'x','plan_sha256':'other'}))
   with self.assertRaises(ValueError):h.verify({'receipt':str(p),'id':'x'},'correct')
 def test_failed_host_with_existing_output_is_not_success(self):
  good={'returncode':0,'batch':{'attempts':270,'completed':270}}
  h.require_process(good,270)
  for bad in ({'returncode':1,'batch':good['batch']}, {'returncode':0},
              {'returncode':0,'batch':{'attempts':270,'completed':269}},
              {'returncode':False,'batch':good['batch']},
              {'returncode':0,'batch':{'attempts':270.,'completed':270}}):
   with self.subTest(receipt=bad),self.assertRaises(ValueError):h.require_process(bad,270)
 def test_pcm16_output_rejected(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'x.wav';sf.write(p,np.ones(100)*.1,48000,subtype='PCM_16');info=h.c.inspect_audio(p)
   self.assertIn('output is not float32 WAV',h.c.output_checks(info,info,h.c.Request()))

if __name__=='__main__':unittest.main()
