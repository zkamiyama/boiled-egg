from pathlib import Path
import tempfile,unittest
from unittest.mock import patch
import audit,ring_scope as s

class RingScopeTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
  self.before=Path(self.tmp.name)/'before';self.after=Path(self.tmp.name)/'after'
  self.changes={};self.additions={}
  for name in (*s.CHANGES,'src/untouched.cpp','include/public.h','adapters/a','eval/e','research/r'):
   for root in (self.before,self.after):
    p=root/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text('original '+name)
  for name in s.CHANGES:
   (self.after/name).write_text('candidate '+name)
   self.changes[name]=(audit.sha(self.before/name),audit.sha(self.after/name))
  for name in s.ADDITIONS:
   p=self.after/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text('new helper')
   self.additions[name]=audit.sha(p)
  self.stack=[patch.object(s,'CHANGES',self.changes),patch.object(s,'ADDITIONS',self.additions)]
  for p in self.stack:p.start();self.addCleanup(p.stop)
 def test_only_exact_runtime_changes(self):
  self.assertEqual(len(s.check_runtime(self.before,self.after)),5)
  for name in (*self.changes,*self.additions,'src/untouched.cpp','include/public.h'):
   p=self.after/name;old=p.read_bytes();p.write_bytes(old+b'changed')
   with self.subTest(path=name),self.assertRaises(ValueError):s.check_runtime(self.before,self.after)
   p.write_bytes(old)
 def test_missing_added_and_extra_files_fail(self):
  helper=self.after/next(iter(self.additions));old=helper.read_bytes();helper.unlink()
  with self.assertRaises(ValueError):s.check_runtime(self.before,self.after)
  helper.write_bytes(old);extra=self.after/'src/extra.cpp';extra.write_text('unreviewed')
  with self.assertRaises(ValueError):s.check_runtime(self.before,self.after)
 def test_reference_is_not_a_waiver(self):
  name=next(iter(self.changes));(self.before/name).write_text('unexpected')
  with self.assertRaisesRegex(ValueError,'unknown ring reference'):s.check_runtime(self.before,self.after)
 def test_predecessor_called_and_protected_trees_checked(self):
  parent=dict(donor_runtime_sha256={'original':'hash'})
  with patch.object(s.formant_scope,'source_contract',return_value=parent) as previous:
   answer=s.source_contract(1,2,self.after,3,4,5,self.before,6)
   previous.assert_called_once_with(1,2,self.before,3,4,5,6)
   self.assertEqual(answer['source_profile'],'exact-pv-ring-address-v1')
   (self.after/'eval/e').write_text('changed')
   with self.assertRaisesRegex(ValueError,'protected ring eval'):s.source_contract(1,2,self.after,3,4,5,self.before,6)
  with patch.object(s.formant_scope,'source_contract',side_effect=ValueError('predecessor failed')):
   with self.assertRaisesRegex(ValueError,'predecessor'):s.source_contract(1,2,self.after,3,4,5,self.before,6)

if __name__=='__main__':unittest.main()
