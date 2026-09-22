from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import compare

class CompareTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.a=self.root/'a';self.b=self.root/'b'
        for d in (self.a,self.b):(d/'fixture').mkdir(parents=True)
        self.fields=['mode','rate','channels','quality','input','block','time','pitch','output','target','violations','allocations','error']
        self.row=['fixture','48000','1','0','1','32','1','1','1','1','0','0','']
        self.payload=b'\x00\x00\x80\x3e'
        self.save(self.a);self.save(self.b)
        self.context=patch.dict(compare.COUNTS,{'fixture':1},clear=True);self.context.start();self.addCleanup(self.context.stop)
    def save(self,d,row=None,raw=None):
        (d/'fixture.csv').write_text(','.join(self.fields)+'\n'+','.join(row or self.row)+'\n')
        (d/'fixture/1.f32').write_bytes(self.payload if raw is None else raw)
    def test_unchanged_complete(self):
        r=compare.compare(self.a,self.b);self.assertEqual(r['correct_length_unchanged_pcm'],1);self.assertFalse(r['failures'])
    def test_missing_grid(self):
        (self.b/'fixture.csv').write_text(','.join(self.fields)+'\n')
        with self.assertRaisesRegex(ValueError,'incomplete'):compare.compare(self.a,self.b)
    def test_duplicate_case(self):
        with patch.dict(compare.COUNTS,{'fixture':2},clear=True):
            for d in [self.a,self.b]:
                (d/'fixture.csv').write_text(','.join(self.fields)+'\n'+','.join(self.row)+'\n'+','.join(self.row)+'\n')
            with self.assertRaisesRegex(ValueError,'duplicate'):compare.compare(self.a,self.b)
    def test_changed_request(self):
        row=self.row.copy();row[6]='2';self.save(self.b,row)
        with self.assertRaisesRegex(ValueError,'changed case'):compare.compare(self.a,self.b)
    def test_wrong_pcm_and_length(self):
        self.save(self.b,raw=b'abcd');self.assertTrue(compare.compare(self.a,self.b)['failures'])
        self.save(self.b,raw=b'x')
        with self.assertRaisesRegex(ValueError,'PCM length'):compare.compare(self.a,self.b)
    def test_failed_candidate_is_not_success(self):
        for field,value in [('error','failed'),('violations','1'),('allocations','1'),('output','2')]:
            row=self.row.copy();row[self.fields.index(field)]=value;self.save(self.b,row)
            self.assertTrue(compare.compare(self.a,self.b)['failures'])
    def test_nonfinite_and_silent_pcm_rejected(self):
        for raw in [b'\x00\x00\x00\x00', b'\x00\x00\xc0\x7f']:
            self.save(self.b,raw=raw)
            with self.assertRaisesRegex(ValueError,'nonfinite or silent'):compare.compare(self.a,self.b)
    def test_original_overlong_and_stall_remain_explicit(self):
        row=self.row.copy();row[8]='2';self.save(self.a,row,raw=self.payload*2)
        self.assertEqual(compare.compare(self.a,self.b)['overlong_fixed'],1)
        row=self.row.copy();row[-1]='EOF progress';self.save(self.a,row)
        with self.assertRaisesRegex(ValueError,'failed baseline published'):compare.compare(self.a,self.b)
        (self.a/'fixture/1.f32').unlink();self.assertEqual(compare.compare(self.a,self.b)['stalls_fixed'],1)
if __name__=='__main__':unittest.main()
