"""Drive the real GUI/worker batch and cancellation without a sound device."""
import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import json
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch
import numpy as np
import soundfile as sf
from PySide6.QtWidgets import QApplication
from app import MainWindow
from worker import PlayerWorker

QT=QApplication.instance() or QApplication([])

def until(predicate):
    deadline=time.monotonic()+8
    while not predicate() and time.monotonic()<deadline:
        QT.processEvents();time.sleep(.005)
    if not predicate():raise AssertionError('Native comparison did not complete')

def source(path):
    t=np.arange(24000)/48000;x=.1*np.cos(2*np.pi*223*t)
    sf.write(path,np.c_[x,-.375*x],48000,subtype='FLOAT')

class NativeBatchUITests(unittest.TestCase):
    def test_gui_compares_loaded_pcm_at_frozen_anchor_and_saves_choice(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'source.wav';source(p);window=MainWindow()
            try:
                window.load(p);until(lambda:window.source_path==p and window.native_ready)
                window.seek(.25);until(lambda:window.wave.position==.25)
                window.speed.setValue(0);window.pitch.setValue(12);window.export_seconds.setValue(.2)
                # The currently loaded source, not a changed pathname, is compared.
                p.unlink()
                window.render_all_native();self.assertTrue(window.native_busy)
                until(lambda:not window.native_busy and len(window.comparisons)==6)
                self.assertEqual(window.tabs.currentIndex(),1)
                self.assertTrue(window.native_batch_button.isEnabled())
                self.assertTrue(window.native_export_button.isEnabled())
                for index in range(6):
                    window.comparison_choice.setCurrentIndex(index)
                    output=window.reference_path
                    self.assertTrue(output.is_file())
                    receipt=json.loads(output.with_suffix('.wav.json').read_text())
                    self.assertEqual(receipt['source_position'],12000.)
                    self.assertEqual(receipt['final_source_position'],12000.)
                    self.assertEqual(receipt['pitch_semitones'],12.)
                    self.assertEqual(sf.info(output).frames,9600)
                target=Path(d)/'selected.wav'
                with patch('app.QFileDialog.getSaveFileName',return_value=(str(target),'Wave')):
                    window.save_comparison()
                self.assertTrue(target.is_file());self.assertTrue(target.with_suffix('.wav.json').is_file())
                self.assertFalse(window.playing)
            finally:window.close();QT.processEvents()

    def test_native_export_cancellation_preserves_existing_files(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'source.wav';source(p);worker=PlayerWorker()
            try:
                worker._load(p);worker.render_cancel.set();out=Path(d)/'cancelled.wav'
                with self.assertRaises(InterruptedError):worker._export(out,.2)
                self.assertFalse(out.exists())
                worker.render_cancel.clear();worker._export(out,.2)
                self.assertEqual(sf.info(out).frames,9600)
                before=out.read_bytes()
                with self.assertRaises(ValueError):worker._export(out,.2)
                self.assertEqual(out.read_bytes(),before)
            finally:
                if worker.handle:worker.handle.close()

    def test_job_queue_failure_restores_gui_buttons(self):
        window=MainWindow()
        try:
            with patch.object(window.worker,'command',side_effect=RuntimeError('busy queue')):
                window.begin_native_job('compare_native',('unused',.1))
            self.assertFalse(window.native_busy)
            self.assertTrue(window.native_batch_button.isEnabled())
            self.assertTrue(window.native_export_button.isEnabled())
            self.assertIn('busy queue',window.log.toPlainText())
        finally:window.close();QT.processEvents()

if __name__=='__main__':unittest.main()
