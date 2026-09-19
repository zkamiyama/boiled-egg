from test_helpers import close_window
"""Presentation-only localization tests, including a real native owner thread.

All preferences use temporary INI files; tests never change a user's language.
Raw SDK/renderer receipts and the existing audio acceptance criteria are untouched.
"""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import copy
from concurrent.futures import Future
from pathlib import Path
import re
from string import Formatter
import tempfile
import time
import unittest
from unittest.mock import patch
import numpy as np
import soundfile as sf
from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication, QLabel
from app import MainWindow
from i18n import CATALOG, I18n, Diagnostic, message
from native import Transport
import sdk_compare

QT = QApplication.instance() or QApplication([])


def until(predicate, events=True):
    deadline = time.monotonic() + 8
    while not predicate() and time.monotonic() < deadline:
        if events:
            QT.processEvents()
        time.sleep(.005)
    if not predicate():
        raise AssertionError('Expected worker/UI state not reached')


class LanguageTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.settings_path = str(Path(self.tmp.name) / 'language.ini')
        self.preferences = QSettings(self.settings_path, QSettings.Format.IniFormat)

    def window(self, language='ja'):
        w = MainWindow(language=language, preferences=self.preferences)
        def close():
            close_window(w)
            QT.processEvents()
        self.addCleanup(close)
        return w

    def test_catalog_pairs_have_identical_format_arguments(self):
        fmt = Formatter()
        for key, pair in CATALOG.items():
            self.assertEqual(len(pair), 2, key)
            fields = [{field for _, field, _, _ in fmt.parse(text) if field is not None} for text in pair]
            self.assertEqual(fields[0], fields[1], key)
            if key != 'empty':
                self.assertTrue(all(pair), key)
            self.assertIsNone(re.search('[\u3040-\u30ff\u3400-\u9fff]', pair[1]), key)
            for language in ('ja', 'en'):
                tr = I18n(language, self.preferences)
                rendered = tr.text(message(key, **{field: 1.25 for field in fields[0]}))
                self.assertIsInstance(rendered, str)
        with self.assertRaises(KeyError):
            I18n('ja', self.preferences).text(message('missing_internal_key'))

    def test_persistence_and_session_override_are_distinct(self):
        tr = I18n(preferences=self.preferences)
        self.assertEqual(tr.language, 'ja')
        self.assertFalse(self.preferences.contains('ui/language'))
        self.assertTrue(tr.select('en'))
        reread = QSettings(self.settings_path, QSettings.Format.IniFormat)
        self.assertEqual(I18n(preferences=reread).language, 'en')
        self.assertEqual(I18n('ja', reread).language, 'ja')
        self.assertEqual(reread.value('ui/language'), 'en')
        self.assertEqual(reread.allKeys(), ['ui/language'])

    def test_invalid_preference_fallback_and_invalid_selection(self):
        self.preferences.setValue('ui/language', 'invalid')
        self.preferences.setValue('unrelated', 'retain')
        tr = I18n(preferences=self.preferences)
        self.assertEqual(tr.language, 'ja')
        with self.assertRaises(ValueError):
            tr.select('fr')
        self.assertEqual(tr.language, 'ja')
        self.assertEqual(self.preferences.value('unrelated'), 'retain')
        with self.assertRaises(ValueError):
            I18n('fr', self.preferences)

    def test_in_app_selection_is_restored_by_new_window(self):
        first = self.window()
        first.language_combo.setCurrentIndex(first.language_combo.findData('en'))
        self.assertEqual(first.play_button.text(), '▶ Play')
        first.close()
        second = self.window(language=None)
        self.assertEqual(second.i18n.language, 'en')
        self.assertEqual(second.language_combo.currentData(), 'en')
        self.assertEqual(second.tabs.tabText(0), 'Native playback / freeze')

    def test_switch_preserves_controls_busy_flags_and_does_not_send_commands(self):
        w = self.window()
        w.policy.setCurrentIndex(w.policy.findData(1))
        w.formant.setValue(3.25); w.speed.setValue(0); w.pitch.setValue(7.25)
        w.volume.setValue(37); w.export_seconds.setValue(3.5)
        w.sdk_policy.setCurrentIndex(w.sdk_policy.findData('monophonic'))
        w.sdk_mode.setCurrentIndex(w.sdk_mode.findData(4))
        w.timer.stop(); w.debounce.stop()
        w.wave.position = 2.345; w.playing = True; w.native_busy = True
        w.native_export_button.setEnabled(False); w.native_batch_button.setEnabled(False)
        w.job = Future(); future = w.job
        expected = (w.mode.currentData(), w.policy.currentData(), w.sdk_mode.currentData(),
                    w.sdk_policy.currentData(), w.pitch.value(), w.formant.value(), w.volume.value(),
                    w.export_seconds.value(), w.wave.position, w.tabs.currentIndex())
        with patch.object(w.worker, 'command') as command, patch.object(w.pump, 'pause') as pause, patch.object(w.media, 'stop') as stop:
            for language in ('en', 'ja', 'en'):
                w.change_language(language)
                actual = (w.mode.currentData(), w.policy.currentData(), w.sdk_mode.currentData(),
                          w.sdk_policy.currentData(), w.pitch.value(), w.formant.value(), w.volume.value(),
                          w.export_seconds.value(), w.wave.position, w.tabs.currentIndex())
                self.assertEqual(actual, expected)
                self.assertTrue(w.playing); self.assertTrue(w.native_busy)
                self.assertFalse(w.native_batch_button.isEnabled())
                self.assertFalse(w.native_export_button.isEnabled())
                self.assertIs(w.job, future)
                self.assertFalse(w.cancel.is_set()); self.assertFalse(w.worker.render_cancel.is_set())
            command.assert_not_called(); pause.assert_not_called(); stop.assert_not_called()
        self.assertEqual(w.play_button.text(), 'Ⅱ Pause')
        self.assertEqual(w.freeze_button.text(), '▶ Unfreeze [F]')
        self.assertEqual(w.export_seconds.suffix(), ' s')
        for label in w.findChildren(QLabel):
            self.assertIsNone(re.search('[\u3040-\u30ff\u3400-\u9fff]', label.text()), label.text())
        future.cancel()

    def test_logs_and_telemetry_retranslate_without_changing_payloads(self):
        w = self.window(); w.timer.stop(); w.debounce.stop()
        raw = 'external/path/{pitch}/音声.wav: decoder code 99'
        w.show_error(raw)
        w.show_error('Time-domain formant policy unsupported; no fallback')
        state = dict(source_position=12000., output_frames=24000, speed=0., pitch_semitones=7., peak=1.2)
        before = copy.deepcopy(state); w.telemetry(state)
        w.change_language('en')
        self.assertIn('FREEZE — source anchor held', w.native_status.text())
        self.assertIn('Above 1.0', w.native_status.text())
        self.assertIn(raw, w.log.toPlainText())
        self.assertIn('Warning:', w.log.toPlainText())
        w.change_language('ja')
        self.assertIn('原音位置固定', w.native_status.text())
        self.assertIn('未対応', w.log.toPlainText())
        self.assertIn(raw, w.log.toPlainText())
        self.assertEqual(state, before)

    def test_translated_sdk_policy_submits_the_original_token(self):
        w = self.window(); w.timer.stop(); w.debounce.stop()
        w.source_path = Path(self.tmp.name) / 'source.wav'
        w.sdk_mode.setCurrentIndex(w.sdk_mode.findData(3))
        w.sdk_policy.setCurrentIndex(w.sdk_policy.findData('harmonic'))
        for language in ('ja', 'en'):
            w.change_language(language); w.job = None
            future = Future()
            with patch.object(w.pool, 'submit', return_value=future) as submit:
                w.render_sdk()
            args = submit.call_args.args
            self.assertIs(args[0], sdk_compare.render)
            self.assertEqual(args[3], 3)
            self.assertEqual(args[6], 'harmonic')
            self.assertEqual(w.sdk_policy.currentData(), 'harmonic')
            future.cancel(); w.job = None

    def test_comparison_retranslation_preserves_selected_file_and_raw_receipt(self):
        w = self.window(); w.timer.stop(); w.debounce.stop()
        root = Path(self.tmp.name)
        output = root / 'native-0.wav'; output.write_bytes(b'raw data unchanged')
        report = dict(source_name='Loaded source PCM', results=[
            dict(index=0, mode='PV Classic — native spectral hold', status='passed', output=output.name,
                 receipt=dict(output_frames=9600, peak=.1)),
            dict(index=3, mode='WSOLA — native time-domain hold', status='unsupported',
                 reason='Time-domain formant policy unsupported; no fallback')])
        before = copy.deepcopy(report)
        w.publish_comparison(report, root, 'Native: ')
        self.assertEqual(w.reference_path, output)
        with patch.object(w.media, 'stop') as stop:
            w.change_language('en')
            self.assertEqual(w.reference_path, output)
            self.assertIn('Complete', w.reference_label.text())
            self.assertIn('Loaded source PCM', w.reference_label.text())
            stop.assert_not_called()
        w.comparison_choice.setCurrentIndex(1)
        self.assertIsNone(w.reference_path)
        w.change_language('ja')
        self.assertEqual(w.comparison_choice.currentIndex(), 1)
        self.assertIn('未対応', w.reference_label.text())
        self.assertEqual(report, before)
        self.assertEqual(output.read_bytes(), b'raw data unchanged')

    def test_dialog_titles_follow_current_language(self):
        w = self.window(); w.timer.stop(); w.debounce.stop()
        for language, title in (('en', 'Open audio'), ('ja', '音声を開く')):
            w.change_language(language)
            with patch('app.QFileDialog.getOpenFileName', return_value=('', '')) as dialog:
                w.choose_file()
            self.assertEqual(dialog.call_args.args[1], title)
            self.assertIn('*.wav', dialog.call_args.args[3])

    def test_save_failure_keeps_session_language_and_reports_error(self):
        w = self.window(); w.timer.stop(); w.debounce.stop()
        with patch.object(w.i18n.preferences, 'status', return_value=QSettings.Status.AccessError):
            w.change_language('en')
        self.assertEqual(w.i18n.language, 'en')
        self.assertEqual(w.play_button.text(), '▶ Play')
        self.assertIn('Could not save', w.log.toPlainText())

    def test_real_frozen_worker_queue_and_pcm_are_unchanged_by_language(self):
        w = self.window()
        t = np.arange(24000) / 48000
        x = np.c_[.1*np.cos(2*np.pi*223*t), -.0375*np.cos(2*np.pi*223*t)].astype('float32')
        path = Path(self.tmp.name) / 'tone.wav'; sf.write(path, x, 48000, subtype='FLOAT')
        # Queue controls before loading so both reference and worker start with
        # the same native initial state, rather than different smoothing history.
        w.mode.setCurrentIndex(w.mode.findData(0)); w.speed.setValue(0); w.pitch.setValue(7)
        w.apply_settings(); w.debounce.stop(); w.load(path)
        until(lambda: w.source_path == path and w.native_ready)
        w.seek(.25); until(lambda: w.wave.position == .25)
        w.timer.stop(); w.debounce.stop(); w.worker.command('play')
        until(w.worker.audio.full, events=False)
        handle = w.worker.handle; epoch = w.worker.epoch
        with w.worker.audio.mutex:
            queued_before = list(w.worker.audio.queue)
        with patch.object(w.worker, 'command') as commands:
            for language in ('en', 'ja', 'en', 'ja'):
                w.change_language(language)
            commands.assert_not_called()
        with w.worker.audio.mutex:
            self.assertEqual(list(w.worker.audio.queue), queued_before)
        self.assertIs(w.worker.handle, handle); self.assertEqual(w.worker.epoch, epoch)
        actual = []
        for _ in range(4):
            packet = w.worker.audio.get(timeout=5)
            self.assertEqual(packet[2]['source_position'], 12000.)
            actual.append(np.frombuffer(packet[1], dtype='<f4').reshape(-1, 2))
        w.worker.command('pause')
        with Transport(x, 48000, 0) as reference:
            reference.set(0, 7); reference.seek(12000.)
            expected = np.concatenate([reference.render(1024) for _ in range(4)])
        np.testing.assert_array_equal(np.concatenate(actual), expected)
        self.assertGreater(float(np.max(np.abs(expected))), .01)


if __name__ == '__main__':
    unittest.main()
