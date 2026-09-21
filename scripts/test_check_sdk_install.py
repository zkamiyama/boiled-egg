import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import check_sdk_install as gate


class InstallGateTests(unittest.TestCase):
    def test_cache_parser(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)
            (p/'CMakeCache.txt').write_text('// ignored\n# ignored\nBOILED_EGG_BUILD_SHARED:BOOL=OFF\nPATH:PATH=/tmp/path=with=equals\n')
            self.assertEqual(gate.cache_options(p), {'BOILED_EGG_BUILD_SHARED':'OFF','PATH':'/tmp/path=with=equals'})

    def test_four_declared_combinations(self):
        for linkage in ('shared','static'):
            for spectral in ('ON','OFF'):
                gate.require_build({'BOILED_EGG_BUILD_SHARED':'ON' if linkage=='shared' else 'OFF',
                                    'BOILED_EGG_ENABLE_EXPERIMENTAL_SPECTRAL':spectral},linkage,spectral)

    def test_missing_options(self):
        for options in ({},{'BOILED_EGG_BUILD_SHARED':'OFF'},
                        {'BOILED_EGG_BUILD_SHARED':'AUTO','BOILED_EGG_ENABLE_EXPERIMENTAL_SPECTRAL':'OFF'}):
            with self.assertRaises(ValueError):gate.require_build(options,'static','OFF')

    def test_mismatched_options(self):
        options={'BOILED_EGG_BUILD_SHARED':'ON','BOILED_EGG_ENABLE_EXPERIMENTAL_SPECTRAL':'OFF'}
        for linkage,spectral in (('static','OFF'),('shared','ON')):
            with self.assertRaises(ValueError):gate.require_build(options,linkage,spectral)

    def test_existing_output_not_overwritten(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);out=root/'existing';out.mkdir();sentinel=out/'report.json';sentinel.write_text('original')
            with self.assertRaises(FileExistsError):gate.run(root,out,'shared','OFF','Release')
            self.assertEqual(sentinel.read_text(),'original')

    def test_missing_cache_leaves_failed_receipt(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);out=root/'evidence'
            result=gate.run(root,out,'static','OFF','Release')
            self.assertEqual(result['status'],'failed')
            self.assertEqual(json.loads((out/'report.json').read_text())['status'],'failed')
            self.assertEqual(result['commands'],[])

    def test_configuration_mismatch_does_not_run_cmake(self):
        with tempfile.TemporaryDirectory() as d, patch.object(gate.platform,'platform',return_value='test-host'), patch.object(gate.subprocess,'run') as mock:
            root=Path(d)
            (root/'CMakeCache.txt').write_text('BOILED_EGG_BUILD_SHARED:BOOL=OFF\nBOILED_EGG_ENABLE_EXPERIMENTAL_SPECTRAL:BOOL=OFF\n')
            result=gate.run(root,root/'out','shared','OFF','Release')
            self.assertEqual(result['status'],'failed');mock.assert_not_called()

    def test_hashes_detect_changed_and_missing_files(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);a=root/'a';a.write_bytes(b'1');one=gate.hashes(root)
            a.write_bytes(b'2');self.assertNotEqual(one,gate.hashes(root))
            a.unlink();self.assertNotEqual(one,gate.hashes(root))


if __name__=='__main__':unittest.main()
