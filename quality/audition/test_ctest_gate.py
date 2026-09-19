"""Negative controls for a misleading green CTest invocation with no tests."""
import copy
from pathlib import Path
import subprocess
import tempfile
import unittest
import run_ctest as gate


class CTestGateTests(unittest.TestCase):
    def test_zero_missing_duplicate_disabled_and_unbuilt_are_rejected(self):
        good = {'tests': [{'name': 'one', 'command': ['/bin/true'], 'properties': []},
                          {'name': 'two', 'command': ['/bin/true'], 'properties': []}]}
        self.assertEqual(gate.validate_inventory(good, 2), ['one', 'two'])
        disabled = copy.deepcopy(good)
        disabled['tests'][0]['properties'] = [{'name': 'DISABLED', 'value': True}]
        unbuilt = copy.deepcopy(good); del unbuilt['tests'][0]['command']
        for bad in ({}, {'tests': []}, {'tests': good['tests'][:1]},
                    {'tests': good['tests'][:1]*2}, disabled, unbuilt):
            with self.assertRaises(ValueError): gate.validate_inventory(bad, 2)

    def test_real_empty_ctest_directory_fails_before_running(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(ValueError): gate.run(Path(directory), 1)

    def test_real_runtime_skip_is_not_a_success(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root/'CTestTestfile.cmake').write_text(
                'add_test(skip "/bin/sh" "-c" "exit 7")\n'
                'set_tests_properties(skip PROPERTIES SKIP_RETURN_CODE 7)\n')
            with self.assertRaisesRegex(ValueError, 'skipped'):
                gate.run(root, 1)

    def test_real_failing_test_cannot_become_a_pass(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root/'CTestTestfile.cmake').write_text('add_test(bad "/bin/false")\n')
            with self.assertRaises(subprocess.CalledProcessError): gate.run(root, 1)
            (root/'CTestTestfile.cmake').write_text('add_test(good "/bin/true")\n')
            gate.run(root, 1)


if __name__ == '__main__': unittest.main()
