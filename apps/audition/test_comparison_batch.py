from test_helpers import close_window
"""Actual SDK batch rendering and GUI selection without audio hardware."""
import json
import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from pathlib import Path
import tempfile
import threading
import time
import unittest
import numpy as np
import soundfile as sf
from PySide6.QtWidgets import QApplication
from app import MainWindow
import comparison_batch as batch
import sdk_compare

QT=QApplication.instance() or QApplication([])

def write_tone(path):
    t=np.arange(12000)/48000
    x=(.1*np.cos(2*np.pi*223*t)).astype('float32')
    sf.write(path,np.c_[x,-.375*x],48000,subtype='FLOAT')

def until(predicate):
    deadline=time.monotonic()+6
    while not predicate() and time.monotonic()<deadline:
        QT.processEvents();time.sleep(.005)
    if not predicate():raise AssertionError('GUI operation did not complete')

class BatchTests(unittest.TestCase):
    def test_all_actual_modes_snapshot_and_preserved_raw_receipts(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'tone.wav';write_tone(p)
            r=batch.render_batch(p,Path(d)/'all',.8,0)
            self.assertTrue(r['all_passed']);self.assertEqual(len(r['results']),5)
            self.assertEqual([a['index'] for a in r['results']],list(range(5)))
            for row in r['results']:
                path=Path(d)/'all'/row['output']
                self.assertEqual(sf.info(path).frames,15000)
                self.assertEqual(row['receipt']['input_sha256'],sdk_compare.sha(p))
                self.assertEqual(row['receipt']['output_sha256'],sdk_compare.sha(path))
            stored=json.loads((Path(d)/'all/comparison.json').read_text())
            self.assertEqual(stored,r)
            with self.assertRaises(FileExistsError):batch.render_batch(p,Path(d)/'all',1,0)
    def test_unsupported_policies_are_retained_not_silently_changed(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'tone.wav';write_tone(p)
            r=batch.render_batch(p,Path(d)/'policies',1,7,'harmonic')
            self.assertEqual([a['status'] for a in r['results']],['unsupported']*3+['passed']*2)
            self.assertFalse(r['all_passed'])
            for row in r['results'][3:]:self.assertEqual(row['receipt']['policy'],'harmonic')
    def test_cancel_and_missing_engine_keep_full_failure_grid(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'tone.wav';write_tone(p);cancel=threading.Event();cancel.set()
            r=batch.render_batch(p,Path(d)/'cancel',1,0,cancel=cancel)
            self.assertEqual([a['status'] for a in r['results']],['cancelled']*5)
            r=batch.render_batch(p,Path(d)/'missing',1,0,executable=Path(d)/'missing-cli')
            self.assertEqual([a['status'] for a in r['results']],['failed']*5)
            self.assertFalse(list((Path(d)/'missing').glob('mode-*.wav')))
    def test_export_copy_checks_receipt_and_does_not_overwrite(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'source.wav';write_tone(p);out=Path(d)/'output.wav'
            receipt=sdk_compare.render(p,out,0,1,0)
            target=Path(d)/'saved.wav';batch.save_result(out,target)
            self.assertEqual(out.read_bytes(),target.read_bytes())
            self.assertEqual(json.loads(target.with_suffix('.wav.json').read_text()),receipt)
            with self.assertRaises(FileExistsError):batch.save_result(out,target)
            target2=Path(d)/'second.wav';target2.with_suffix('.wav.json').write_text('keep')
            with self.assertRaises(FileExistsError):batch.save_result(out,target2)
            self.assertFalse(target2.exists())
            out.write_bytes(b'changed')
            with self.assertRaises(ValueError):batch.save_result(out,Path(d)/'bad.wav')
            self.assertFalse((Path(d)/'bad.wav').exists())
    def test_export_cannot_disguise_compressed_audio_as_wav(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'external.flac';sf.write(p,np.zeros(128),48000)
            with self.assertRaises(ValueError):batch.save_result(p,Path(d)/'wrong.wav')
            self.assertFalse((Path(d)/'wrong.wav').exists())
    def test_nonfinite_batch_fails_before_directory_creation(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'tone.wav';write_tone(p);out=Path(d)/'invalid'
            with self.assertRaises(ValueError):batch.render_batch(p,out,float('nan'),0)
            self.assertFalse(out.exists())
    def test_paused_seek_updates_visible_anchor_without_audio_device(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'tone.wav';write_tone(p);w=MainWindow()
            try:
                w.load(p);until(lambda:w.native_ready and w.source_path==p)
                w.seek(.125);until(lambda:abs(w.wave.position-.125)<1e-9)
                self.assertFalse(w.playing)
            finally:close_window(w)
    def test_gui_batch_selection_and_raw_save(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'tone.wav';write_tone(p);w=MainWindow()
            try:
                w.load(p);until(lambda:w.native_ready and w.source_path==p)
                w.render_all_sdk();until(lambda:w.job is None and len(w.comparisons)==5)
                self.assertEqual(w.comparison_choice.count(),5)
                for index in range(5):
                    w.comparison_choice.setCurrentIndex(index)
                    self.assertTrue(w.reference_path.is_file())
                    self.assertIn(sdk_compare.SDK_MODES[index][0],w.reference_label.text())
                batch.save_result(w.reference_path,Path(d)/'selection.wav')
                self.assertTrue((Path(d)/'selection.wav.json').is_file())
                self.assertTrue(w.batch_button.isEnabled())
            finally:close_window(w)

if __name__=='__main__':unittest.main()
