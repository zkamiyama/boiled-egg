from test_helpers import close_window
"""App-owned output errors must switch languages; external diagnostics stay raw.

Exercise the actual no-device and failed-write paths. No sound hardware, DSP
changes, user preferences, or machine-local language settings are required.
"""
import ast
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from pathlib import Path
import re
import tempfile
import unittest
from PySide6.QtCore import QSettings
from PySide6.QtMultimedia import QAudioDevice
from PySide6.QtWidgets import QApplication
import audio_output
from app import MainWindow
from i18n import Diagnostic, I18n

QT = QApplication.instance() or QApplication([])
ERRORS = (
    ('選択デバイスはこのfloat32形式に未対応です。出力先・レートを変更してください。WAV書出しは利用できます。',
     'The selected device does not support this float32 format. Choose another output device or sample rate. WAV export remains available.'),
    ('音声デバイスを開始できません。', 'Could not start the audio device.'),
    ('音声デバイスが停止しました。出力先を選び直してください。原音は保持しています。',
     'The audio device stopped. Select an output device again. The source is retained.'),
    ('音声出力の書込みに失敗しました。', 'Writing to the audio output failed.'),
)


class AudioLanguageTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.preferences = QSettings(str(Path(self.tmp.name) / 'ui.ini'), QSettings.Format.IniFormat)

    def window(self):
        window = MainWindow(language='en', preferences=self.preferences)
        window.timer.stop(); window.debounce.stop()
        def close():
            close_window(window)
        self.addCleanup(close)
        return window

    def test_all_owned_output_errors_are_covered(self):
        tree = ast.parse(Path(audio_output.__file__).read_text())
        emitted = []
        for node in ast.walk(tree):
            if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                    and node.func.attr == 'emit' and isinstance(node.func.value, ast.Attribute)
                    and node.func.value.attr == 'error'):
                self.assertIsInstance(node.args[0], ast.Constant)
                emitted.append(node.args[0].value)
        self.assertCountEqual(emitted, [pair[0] for pair in ERRORS])
        tr = I18n('en', self.preferences)
        for original, expected in ERRORS:
            self.assertEqual(tr.text(Diagnostic(original)), expected)
            tr.select('ja', persist=False)
            self.assertEqual(tr.text(Diagnostic(original)), original)
            tr.select('en', persist=False)

    def test_owned_error_history_retranslates_without_raw_japanese_in_english(self):
        window = self.window()
        for original, _ in ERRORS:
            window.show_error(original)
        for language in ('ja', 'en', 'ja', 'en'):
            window.change_language(language)
            text = window.log.toPlainText()
            for original, expected in ERRORS:
                self.assertIn(original if language == 'ja' else expected, text)
            if language == 'en':
                self.assertIsNone(re.search('[\u3040-\u30ff\u3400-\u9fff]', text))

    def test_real_null_device_warning_is_english_then_japanese(self):
        window = self.window()
        self.assertFalse(window.pump.configure(QAudioDevice(), 48000, 2, 1))
        self.assertIn(ERRORS[0][1], window.log.toPlainText())
        window.change_language('ja')
        self.assertIn(ERRORS[0][0], window.log.toPlainText())
        self.assertIsNone(window.pump.sink)

    def test_write_failure_localizes_and_still_stops_output(self):
        class Sink:
            def bytesFree(self): return 32
            def suspend(self): pass
            def reset(self): pass
            def deleteLater(self): pass
        class Writer:
            def write(self, data): return -1
        window = self.window()
        window.playing = True
        window.pump.sink = Sink(); window.pump.io = Writer()
        window.pump.running = True; window.pump.pending = b'abcdefgh'
        window.pump.tick()
        self.assertFalse(window.playing)
        self.assertFalse(window.pump.running)
        self.assertIsNone(window.pump.io)
        self.assertIn(ERRORS[3][1], window.log.toPlainText())
        window.change_language('ja')
        self.assertIn(ERRORS[3][0], window.log.toPlainText())

    def test_unknown_external_text_is_not_rewritten(self):
        raw = 'decoder/音声.wav: code 99 {unexpanded}'
        for language in ('ja', 'en'):
            self.assertEqual(I18n(language, self.preferences).text(Diagnostic(raw)), raw)


if __name__ == '__main__':
    unittest.main()
