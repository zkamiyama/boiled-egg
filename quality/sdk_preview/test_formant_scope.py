from pathlib import Path
import tempfile,unittest
from unittest.mock import patch
import audit,formant_scope as f
class ScopeTests(unittest.TestCase):
 def test_exact_changes_only(self):
  with tempfile.TemporaryDirectory() as d:
   b=Path(d)/'b';c=Path(d)/'c';changes={}
   for root in (b,c):
    for folder in ('src','include'):(root/folder).mkdir(parents=True)
   for name in f.CHANGES:
    (b/name).parent.mkdir(parents=True,exist_ok=True);(c/name).parent.mkdir(parents=True,exist_ok=True)
    (b/name).write_text('old');(c/name).write_text('new');changes[name]=(audit.sha(b/name),audit.sha(c/name))
   with patch.object(f,'CHANGES',changes):
    self.assertEqual(len(f.check_runtime(b,c)),3)
    (c/'src/extra.cpp').write_text('unexpected')
    with self.assertRaises(ValueError):f.check_runtime(b,c)
    (c/'src/extra.cpp').unlink();(c/'src/backend.cpp').write_text('different')
    with self.assertRaises(ValueError):f.check_runtime(b,c)
 def test_unknown_reference_rejected(self):
  with tempfile.TemporaryDirectory() as d:
   with self.assertRaises(ValueError):f.check_runtime(Path(d),Path(d))
if __name__=='__main__':unittest.main()
