"""A named reference is exact evidence, not permission to change arbitrary trees."""
from pathlib import Path
import tempfile
import unittest
import audit


class PackageScopeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base, self.donor, self.current, self.reference, self.host = [
            Path(self.temp.name)/name for name in ('base','donor','current','reference','host')]
        self.header = 'include/boiled_egg/boiled_egg.h'
        self.old = '#if defined(_WIN32)\n  #if defined(BOILED_EGG_BUILDING_LIBRARY)\nEXPORT\n#endif\nint abi(void);\n'
        self.new = self.old.replace('  #if defined(BOILED_EGG_BUILDING_LIBRARY)',
            '  #if defined(BOILED_EGG_STATIC)\n    #define BOILEDEGG_API\n  #elif defined(BOILED_EGG_BUILDING_LIBRARY)')
        for root in (self.base,self.donor,self.current,self.reference,self.host):
            for name in ('adapters/plugin.cpp','eval/check.py','research/old.py',self.header,
                         'src/engine.cpp','src/engine.hpp','src/profile.cpp','src/backend.cpp'):
                path=root/name;path.parent.mkdir(parents=True,exist_ok=True)
                path.write_text(self.old if name==self.header else name+'\n')
        for root in (self.current,self.reference):
            (root/'eval/already_merged.py').write_text('accepted before this PR\n')
        (self.current/self.header).write_text(self.new)

    def check(self):
        return audit.packaging_source_contract(self.base,self.donor,self.current,self.reference,self.host)

    def test_named_scope_and_original_contract_remain_distinct(self):
        with self.assertRaisesRegex(ValueError,'protected eval'):
            audit.source_contract(self.base,self.donor,self.reference,self.host)
        result=self.check()
        self.assertEqual(result['source_profile'],'pinned-package-static-export-v1')
        self.assertEqual(set(result['allowed_runtime_change']),{self.header})
        self.assertNotEqual(result['allowed_runtime_change'][self.header]['before'],
                            result['allowed_runtime_change'][self.header]['after'])

    def test_unreviewed_trees_and_runtime_are_rejected(self):
        for name in ('adapters/plugin.cpp','eval/already_merged.py','research/old.py',
                     'src/backend.cpp','src/engine.cpp',self.header,'include/extra.h'):
            path=self.current/name;old=path.read_bytes() if path.exists() else None
            path.write_text('unexpected change\n')
            with self.subTest(path=name),self.assertRaises(ValueError):self.check()
            if old is None:path.unlink()
            else:path.write_bytes(old)

    def test_reference_is_not_a_runtime_waiver(self):
        path=self.reference/'src/backend.cpp';path.write_text('changed reference\n')
        (self.current/'src/backend.cpp').write_bytes(path.read_bytes())
        with self.assertRaisesRegex(ValueError,'reference differs from validated donor'):self.check()

    def test_exact_macro_and_reviewed_adapter_reference_required(self):
        (self.current/self.header).write_text(self.new.replace('int abi','long abi'))
        with self.assertRaises(ValueError):self.check()
        (self.current/self.header).write_text(self.new)
        (self.host/'adapters/plugin.cpp').write_text('different host\n')
        with self.assertRaisesRegex(ValueError,'reviewed host'):self.check()
        (self.host/'adapters/plugin.cpp').write_text('adapters/plugin.cpp\n')
        for root in (self.base,self.donor,self.reference):
            (root/self.header).write_text(self.old.replace('#if defined(_WIN32)', '#if 1'))
        with self.assertRaisesRegex(ValueError,'unknown reference export macro'):self.check()


if __name__ == '__main__':unittest.main()
