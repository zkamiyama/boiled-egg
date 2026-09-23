import hashlib
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import fft_stage_scope as s

class FFTScopeTests(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup)
        self.old=Path(tmp.name)/'old';self.new=Path(tmp.name)/'new'
        self.file='src/experimental/pv/fft.cpp'
        for root in (self.old,self.new):
            for name in (self.file,'include/api.h','src/engine.cpp','adapters/a','eval/e','research/r'):
                p=root/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(b'old')
        (self.new/self.file).write_bytes(b'new')
        patcher=patch.dict(s.CHANGES,{self.file:(hashlib.sha256(b'old').hexdigest(),hashlib.sha256(b'new').hexdigest())},clear=True)
        patcher.start();self.addCleanup(patcher.stop)

    def test_exact_edit_only(self):
        self.assertEqual(s.check_runtime(self.old,self.new)[self.file],hashlib.sha256(b'new').hexdigest())
        (self.new/'include/api.h').write_bytes(b'other')
        with self.assertRaises(ValueError):s.check_runtime(self.old,self.new)

    def test_unknown_reference_rejected(self):
        (self.old/self.file).write_bytes(b'not the reference')
        with self.assertRaisesRegex(ValueError,'unknown FFT'):s.check_runtime(self.old,self.new)

    def test_missing_extra_or_modified_runtime_rejected(self):
        p=self.new/self.file
        p.unlink()
        with self.assertRaises(ValueError):s.check_runtime(self.old,self.new)
        p.write_bytes(b'new');extra=self.new/'src/extra.cpp';extra.write_bytes(b'extra')
        with self.assertRaises(ValueError):s.check_runtime(self.old,self.new)
        extra.unlink();p.write_bytes(b'another edit')
        with self.assertRaises(ValueError):s.check_runtime(self.old,self.new)

    def test_chain_and_protected_trees_retained(self):
        args=('main','donor',self.new,'package','duration','formant','ring',self.old,'host')
        with patch.object(s.ring_scope,'source_contract',return_value={'donor_runtime_sha256':{'source':'hash'}}) as parent:
            result=s.source_contract(*args)
            parent.assert_called_once_with('main','donor',self.old,'package','duration','formant','ring','host')
            self.assertEqual(result['source_profile'],'exact-pv-fft-first-stage-v1')
            for prefix in ('adapters','eval','research'):
                q=self.new/prefix/'extra';q.write_bytes(b'unapproved')
                with self.subTest(prefix=prefix),self.assertRaises(ValueError):s.source_contract(*args)
                q.unlink()

if __name__=='__main__':unittest.main()
