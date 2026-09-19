"""Independent failure injection for publication and UI/worker shutdown."""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import tempfile
import threading
import time
from pathlib import Path
from unittest.mock import patch
import unittest
import numpy as np
import soundfile as sf
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import QApplication
from app import MainWindow
from worker import PlayerWorker
import sdk_compare

QT = QApplication.instance() or QApplication([])

def tone(path):
    t = np.arange(12000) / 48000
    sf.write(path, .1*np.cos(2*np.pi*223*t), 48000, subtype='FLOAT')

class MergeSafetyTests(unittest.TestCase):
    def test_failed_receipt_removes_only_this_attempts_audio(self):
        with tempfile.TemporaryDirectory() as tmp:
            source, out = Path(tmp)/'source.wav', Path(tmp)/'out.wav'
            tone(source)
            real_open = Path.open
            def fail_receipt(p, *args, **kwargs):
                if p == out.with_suffix('.wav.json'):
                    raise OSError('injected receipt failure')
                return real_open(p, *args, **kwargs)
            with patch.object(Path, 'open', fail_receipt):
                with self.assertRaises(OSError):
                    sdk_compare.render(source, out, 0, 1, 0)
            self.assertFalse(out.exists(), 'A failed operation must not publish unreceipted audio')
            self.assertTrue(source.is_file())

    def test_source_mutation_during_decode_is_not_misattributed(self):
        with tempfile.TemporaryDirectory() as tmp:
            source, out = Path(tmp)/'source.wav', Path(tmp)/'out.wav'
            tone(source)
            real_read = sf.read
            def mutating_read(p, *args, **kwargs):
                value = real_read(p, *args, **kwargs)
                if Path(p) == source:
                    sf.write(source, np.zeros(12000), 48000, subtype='FLOAT')
                return value
            with patch.object(sf, 'read', mutating_read):
                with self.assertRaisesRegex(ValueError, 'changed'):
                    sdk_compare.render(source, out, 0, 1, 0)
            self.assertFalse(out.exists())

    def test_already_cancelled_render_never_starts_process(self):
        with tempfile.TemporaryDirectory() as tmp:
            source, out = Path(tmp)/'source.wav', Path(tmp)/'out.wav'; tone(source)
            cancel = threading.Event(); cancel.set()
            with patch.object(sdk_compare.subprocess, 'Popen', side_effect=AssertionError('process started')):
                with self.assertRaises(InterruptedError):
                    sdk_compare.render(source, out, 0, 1, 0, cancel=cancel)
            self.assertFalse(out.exists())

    def test_worker_quit_does_not_execute_queued_followup(self):
        worker = PlayerWorker(); first = threading.Event(); release = threading.Event(); calls=[]
        def apply(kind, value):
            calls.append(kind)
            if kind == 'first': first.set(); release.wait(3)
        worker._apply = apply
        worker.command('first'); worker.command('must_not_run'); worker.start()
        self.assertTrue(first.wait(3)); worker.stop_worker(); release.set(); worker.join(3)
        self.assertFalse(worker.is_alive()); self.assertEqual(calls, ['first'])

    def test_close_is_nonblocking_and_tempdir_lives_until_job_finishes(self):
        window = MainWindow(); release = threading.Event(); started = threading.Event()
        def job(): started.set(); release.wait(3)
        window.job = window.pool.submit(job); self.assertTrue(started.wait(3))
        root = Path(window.temporary.name)
        # Safety release from a non-Qt timer: the old blocking path cannot deadlock this test.
        safety = threading.Timer(1., release.set); safety.start()
        try:
            event=QCloseEvent(); start=time.monotonic(); window.closeEvent(event)
            elapsed=time.monotonic()-start
            self.assertLess(elapsed, .3, 'close must not wait on file/DSP work on Qt thread')
            self.assertFalse(event.isAccepted()); self.assertTrue(root.is_dir())
            release.set()
            deadline=time.monotonic()+3
            while root.exists() and time.monotonic()<deadline:
                QT.processEvents(); time.sleep(.005)
            self.assertFalse(root.exists())
        finally:
            release.set(); safety.cancel(); safety.join(); window.worker.join(3)
            window.close(); QT.processEvents()

if __name__ == '__main__': unittest.main()
