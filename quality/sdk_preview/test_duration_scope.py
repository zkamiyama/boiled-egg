import hashlib
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import duration_scope as scope


class DurationScopeTests(unittest.TestCase):
    def test_real_candidate_identity(self):
        root=Path(__file__).resolve().parents[2]
        for name,(_,digest) in scope.CHANGES.items():
            self.assertEqual(hashlib.sha256((root/name).read_bytes()).hexdigest(),digest)

    def test_exact_changes_and_extra_files(self):
        with tempfile.TemporaryDirectory() as d:
            old,new=Path(d)/'old',Path(d)/'new'
            for root in (old,new):(root/'src').mkdir(parents=True)
            (old/'src/a').write_bytes(b'old');(new/'src/a').write_bytes(b'new')
            pair=(hashlib.sha256(b'old').hexdigest(),hashlib.sha256(b'new').hexdigest())
            with patch.dict(scope.CHANGES,{'src/a':pair},clear=True):
                self.assertEqual(scope.check_runtime(old,new),{'src/a':pair[1]})
                (new/'src/extra').write_text('unexpected')
                with self.assertRaises(ValueError):scope.check_runtime(old,new)
                (new/'src/extra').unlink();(new/'src/a').write_text('wrong')
                with self.assertRaises(ValueError):scope.check_runtime(old,new)

    def test_changed_reference_is_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaisesRegex(ValueError,'unknown duration reference'):
                scope.check_runtime(Path(d),Path(d))

    def test_parent_audit_is_not_bypassed(self):
        with patch.object(scope.audit,'packaging_source_contract',side_effect=ValueError('donor mismatch')) as parent:
            with self.assertRaisesRegex(ValueError,'donor mismatch'):
                scope.source_contract(*(Path('.') for _ in range(5)))
            parent.assert_called_once()


if __name__ == '__main__':unittest.main()
