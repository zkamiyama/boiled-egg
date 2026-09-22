import copy,itertools,unittest
import run_bench as b
class BenchmarkTests(unittest.TestCase):
 def fixture(self):
  rows=[]
  for i,j,v in itertools.product(range(56),range(3),('original','before','after')):
   t=.8 if v=='after' else 1.
   m=dict(io='streaming' if i<32 else 'realtime',native_per_input_block=t,wall_seconds=t,thread_seconds=t,fixture_create_seconds=1.,over_80_percent=0)
   rows.append(dict(case=i,repeat=j,version=v,status='complete',metrics=m,pcm_sha256='a'*64))
  return rows
 def test_known_ratios(self):
  r=b.assess(self.fixture());self.assertTrue(r['primary_pass']);self.assertEqual(r['all']['native_per_input_block']['median'],.8)
 def test_incomplete_or_duplicate(self):
  rows=self.fixture()
  for bad in ([],rows[:-1],rows+[rows[0]]):
   with self.assertRaises(ValueError):b.assess(bad)
 def test_slow_candidate_cannot_pass(self):
  rows=self.fixture()
  for r in rows:
   if r['version']=='after':r['metrics']['native_per_input_block']=1.5
  result=b.assess(rows);self.assertTrue(result['same_output_pass']);self.assertFalse(result['cost_gate_pass']);self.assertFalse(result['primary_pass'])
 def test_changed_pcm_or_failed_primary(self):
  for change in ('pcm','status'):
   rows=self.fixture();r=next(x for x in rows if x['version']=='after')
   if change=='pcm':r['pcm_sha256']='b'*64
   else:r['status']='failed'
   self.assertFalse(b.assess(rows)['primary_pass'])
 def test_all_failed_preserves_denominator(self):
  rows=self.fixture()
  for r in rows:r['status']='failed'
  result=b.assess(rows);self.assertEqual(result['trials'],504);self.assertFalse(result['primary_pass']);self.assertIsNone(result['all']['wall_seconds'])
 def test_nonfinite_and_missing_fields(self):
  for val in (float('nan'),float('inf'),-1,0,None):
   rows=self.fixture();rows[2]['metrics']['native_per_input_block']=val
   with self.assertRaises(ValueError):b.assess(rows)
if __name__=='__main__':unittest.main()
