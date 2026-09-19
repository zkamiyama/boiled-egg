import tempfile
import unittest
from pathlib import Path
import audit_scope as audit

class ScopeTests(unittest.TestCase):
    def test_dsp_headers_adapters_and_build_changes_cannot_pass(self):
        with tempfile.TemporaryDirectory() as tmp:
            a,b=Path(tmp)/'ref',Path(tmp)/'new'
            for root in (a,b):
                for name in audit.PROTECTED:
                    p=root/name
                    if name.endswith('.txt'):p.write_text('root build')
                    else:p.mkdir(parents=True);(p/'source').write_text(name)
            self.assertTrue(audit.audit(a,b)['unchanged'])
            for prefix in audit.PROTECTED:
                path=b/prefix if prefix.endswith('.txt') else b/prefix/'source'
                original=path.read_bytes();path.write_text('mutated')
                with self.assertRaises(ValueError):audit.audit(a,b)
                path.write_bytes(original)
            (b/'src/extra').write_text('new runtime')
            with self.assertRaises(ValueError):audit.audit(a,b)
            (b/'src/extra').unlink();(b/'include/source').unlink()
            with self.assertRaises(ValueError):audit.audit(a,b)
    def test_missing_reference_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):audit.audit(tmp,tmp)

if __name__=='__main__':unittest.main()
