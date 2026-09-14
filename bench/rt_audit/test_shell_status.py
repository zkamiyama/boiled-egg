"""Calibrate the shell contract used by log-producing CI steps (Linux)."""
import shutil
import subprocess
import unittest

class PipelineStatus(unittest.TestCase):
    def run_shell(self, explicit, code):
        shell=shutil.which('bash')
        self.assertIsNotNone(shell, 'Linux workflow calibration requires bash')
        args=[shell,'--noprofile','--norc','-e']
        if explicit:args+=['-o','pipefail']
        return subprocess.run(args+['-c',code],capture_output=True,text=True,timeout=5)
    def test_implicit_shell_can_hide_failure(self):
        result=self.run_shell(False,'(exit 7) | tee /dev/null; echo continued')
        self.assertEqual(result.returncode,0)
        self.assertEqual(result.stdout.strip(),'continued')
    def test_explicit_pipefail_preserves_failure(self):
        result=self.run_shell(True,'(exit 7) | tee /dev/null; echo continued')
        self.assertEqual(result.returncode,7)
        self.assertNotIn('continued',result.stdout)
    def test_successful_logs_still_succeed(self):
        result=self.run_shell(True,'printf "test passed\n" | tee /dev/null')
        self.assertEqual(result.returncode,0)
        self.assertEqual(result.stdout.strip(),'test passed')

if __name__=='__main__':unittest.main()
